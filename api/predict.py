"""
TARGET clinical prediction — FastAPI app + posterior sampler in one file.

Combined into a single module so Vercel's Python runtime doesn't have to
chase an underscore-prefixed helper import during the build. The route is
POST /api/predict; it returns, per endpoint, either a `locked` status
(when hard-required inputs are missing) or median/CrI summaries computed
from the posterior pickles in `data/`.
"""
from __future__ import annotations

import pickle
from functools import lru_cache
from math import factorial
from pathlib import Path
from typing import Iterable

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scipy.special import expit
from scipy.stats import norm, truncnorm


# ── posterior sampler ────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "data"

# Thresholds defining the 4-level age × days_ps intercept grid at training time.
AGE_CUT, DAYS_CUT = 68, 10

ENDPOINTS = {
    "Barthel":   {"file": "barthel.pkl",   "kind": "continuous"},
    "FIM_Total": {"file": "fim_total.pkl", "kind": "continuous"},
    "FIM_Motor": {"file": "fim_motor.pkl", "kind": "continuous"},
    "Gait":      {"file": "gait.pkl",      "kind": "binary"},
    "MRS":       {"file": "mrs.pkl",       "kind": "binary"},
}

COHORT_MEDIANS = {
    "age": 68.5,
    "days_ps": 6,
    "nihss": 4,
    "los": 14,
    "Barthel_bl": 58,
    "Fim Total_bl": 80,
    "Fim Motor_bl": 52,
    "VLX Marxa_bl": 0.29,
    "Mrs_bl": 3,
}

HARD_REQUIRED = {
    "Barthel":   ["Barthel_bl", "age", "days_ps", "los", "nihss"],
    "FIM_Total": ["Fim Total_bl", "age", "days_ps", "los", "nihss"],
    "FIM_Motor": ["Fim Motor_bl", "age", "days_ps", "los", "nihss"],
    "Gait":      ["age", "days_ps", "nihss"],
    "MRS":       ["Mrs_bl", "age", "days_ps", "nihss"],
}

RECOMMENDED = {
    "Barthel":   ["VLX Marxa_bl", "Fim Motor_bl"],
    "FIM_Total": ["VLX Marxa_bl", "Fim Motor_bl"],
    "FIM_Motor": ["VLX Marxa_bl"],
    "Gait":      ["Fim Motor_bl", "VLX Marxa_bl"],
    "MRS":       ["Barthel_bl"],
}


@lru_cache(maxsize=8)
def _load(endpoint: str) -> dict:
    with open(DATA_DIR / ENDPOINTS[endpoint]["file"], "rb") as f:
        return pickle.load(f)


def _group_idx(age: float, days_ps: float) -> int:
    age_group = 1 if age >= AGE_CUT else 0
    days_group = 1 if days_ps >= DAYS_CUT else 0
    return age_group * 2 + days_group


def _build_x_continuous(features: dict, base_cols: Iterable[str]) -> np.ndarray:
    return np.array([float(features[col]) for col in base_cols])


def _build_x_binary(endpoint: str, features: dict) -> np.ndarray:
    if endpoint == "Gait":
        baseline_walker = 1.0 if features.get("VLX Marxa_bl", 0.0) >= 0.4 else 0.0
        return np.array([
            baseline_walker,
            float(features["age"]),
            float(features["days_ps"]),
            float(features["Fim Motor_bl"]),
            float(features["nihss"]),
        ])
    baseline_mrs_good = 1.0 if float(features["Mrs_bl"]) <= 2 else 0.0
    return np.array([
        baseline_mrs_good,
        float(features["age"]),
        float(features["days_ps"]),
        float(features["Barthel_bl"]),
        float(features["nihss"]),
    ])


def _linpred_continuous(endpoint: str, features: dict):
    d = _load(endpoint)
    X = _build_x_continuous(features, d["base_cols"]) - d["means"]
    gi = _group_idx(float(features["age"]), float(features["days_ps"]))
    mu = d["alpha"][:, gi] + X @ d["beta"].T
    return mu, d["sigma"], tuple(d["bounds"])


def _linpred_binary(endpoint: str, features: dict) -> np.ndarray:
    d = _load(endpoint)
    feats = _build_x_binary(endpoint, features) - d["means"]
    X = np.concatenate([[1.0], feats])
    return X @ d["beta"].T


def predict(endpoint: str, features: dict, rng=None) -> np.ndarray:
    """4000 posterior predictive samples for one endpoint."""
    if endpoint not in ENDPOINTS:
        raise ValueError(f"Unknown endpoint: {endpoint!r}")
    if rng is None:
        rng = np.random.default_rng(20240416)

    if ENDPOINTS[endpoint]["kind"] == "continuous":
        mu, sigma, (lo, hi) = _linpred_continuous(endpoint, features)
        a = (lo - mu) / sigma
        b = (hi - mu) / sigma
        return truncnorm.rvs(a, b, loc=mu, scale=sigma, random_state=rng)

    return expit(_linpred_binary(endpoint, features))


# ── exact Bayesian SHAP (adapted from thesis run_shap.py) ────────────────────
#
# For each posterior draw, enumerate 2^K coalitions of features. For continuous
# endpoints the prediction at coalition S is the truncated-normal mean
# E[Y | Y ∈ [lo, hi], μ_S, σ]; for binary it is the sigmoid of the linear
# predictor. Shapley values then satisfy the efficiency axiom:
#   sum_j φ_j  =  prediction  −  stratum_baseline   (per draw, exactly)
# We report posterior mean ± 95% CrI of each φ_j.

def _truncnorm_mean(mu: np.ndarray, sigma: np.ndarray, lo: float, hi: float) -> np.ndarray:
    a = (lo - mu) / sigma
    b = (hi - mu) / sigma
    Z = np.maximum(norm.cdf(b) - norm.cdf(a), 1e-300)
    return mu + sigma * (norm.pdf(a) - norm.pdf(b)) / Z


def _coalition_mask(K: int) -> np.ndarray:
    n = 1 << K
    bits = np.arange(K)
    return ((np.arange(n)[:, None] >> bits) & 1).astype(np.int8)


def _shapley_weights(K: int) -> np.ndarray:
    return np.array([factorial(s) * factorial(K - s - 1) / factorial(K)
                     for s in range(K)])


def _shap_continuous_one(d: dict, X_centred: np.ndarray, gi: int):
    """SHAP for one patient on a continuous endpoint.

    X_centred: (K,) -- features minus training cohort means.
    Returns shap (K, S), baseline (S,), prediction (S,) all on the score scale.
    """
    alpha, beta, sigma = d["alpha"], d["beta"], d["sigma"]
    lo, hi = d["bounds"]
    K = X_centred.shape[0]
    S = beta.shape[0]
    M = _coalition_mask(K)
    coal_sizes = M.sum(axis=1)
    w_table = _shapley_weights(K)

    contribs = beta * X_centred[None, :]      # (S, K)
    agg = M @ contribs.T                       # (n_coal, S)
    alpha_i = alpha[:, gi]                     # (S,)
    mu = alpha_i[None, :] + agg                # (n_coal, S)
    g = _truncnorm_mean(mu, sigma[None, :], lo, hi)  # (n_coal, S)

    baseline = g[0]
    prediction = g[-1]
    shap = np.zeros((K, S))
    for j in range(K):
        no_j = np.where(M[:, j] == 0)[0]
        with_j = no_j + (1 << j)
        w = w_table[coal_sizes[no_j]]
        shap[j, :] = (w[:, None] * (g[with_j] - g[no_j])).sum(axis=0)
    return shap, baseline, prediction


def _shap_binary_one(d: dict, X_with_intercept: np.ndarray):
    """SHAP for one patient on a binary endpoint, on the probability scale.

    X_with_intercept: (1 + K,) where the first entry is 1.0 and the rest are
    centred features. The Shapley sum is over the K non-intercept features.
    Returns shap (K, S), baseline (S,), prediction (S,).
    """
    beta = d["beta"]
    S = beta.shape[0]
    K = X_with_intercept.shape[0] - 1
    M = _coalition_mask(K)
    coal_sizes = M.sum(axis=1)
    w_table = _shapley_weights(K)
    beta_int = beta[:, 0]                      # (S,)
    beta_feat = beta[:, 1:]                    # (S, K)
    X_feat = X_with_intercept[1:]              # (K,)

    contribs = beta_feat * X_feat[None, :]     # (S, K)
    agg = M @ contribs.T                       # (n_coal, S)
    eta = beta_int[None, :] + agg              # (n_coal, S)
    p = expit(eta)                             # (n_coal, S)

    baseline = p[0]
    prediction = p[-1]
    shap = np.zeros((K, S))
    for j in range(K):
        no_j = np.where(M[:, j] == 0)[0]
        with_j = no_j + (1 << j)
        w = w_table[coal_sizes[no_j]]
        shap[j, :] = (w[:, None] * (p[with_j] - p[no_j])).sum(axis=0)
    return shap, baseline, prediction


# Display-friendly feature labels (UI labels, in case base_cols uses the raw
# training column names).
SHAP_FEATURE_LABELS = {
    "Barthel_bl":      "Barthel (admission)",
    "Fim Total_bl":    "FIM Total (admission)",
    "Fim Motor_bl":    "FIM Motor (admission)",
    "VLX Marxa_bl":    "Gait velocity (admission)",
    "Mrs_bl":          "mRS (admission)",
    "nihss":           "NIHSS",
    "los":             "Planned LOS",
    "age":             "Age",
    "days_ps":         "Days post-stroke",
    # Binary-model derived features
    "baseline_walker": "Walking at admission",
    "fim_bl":          "FIM Motor (admission)",
    "baseline_mrs_good": "mRS ≤ 2 at admission",
    "barthel_bl":      "Barthel (admission)",
}


def _shap_for_endpoint(endpoint: str, features: dict) -> dict:
    """Compute SHAP on the prediction scale for one patient + one endpoint.

    Returns a dict with `baseline` (mean/CI of the empty-coalition prediction)
    and `features` (list of per-feature {key, label, value, shap mean, shap CI}).
    FIM_Motor has 'Fim Motor_bl' in base_cols twice (positions 0 and 2); the
    two contributions are summed into a single display row.
    """
    d = _load(endpoint)
    kind = ENDPOINTS[endpoint]["kind"]

    if kind == "continuous":
        base_cols = d["base_cols"]
        X_raw = np.array([float(features[col]) for col in base_cols])
        X_c = X_raw - d["means"]
        gi = _group_idx(float(features["age"]), float(features["days_ps"]))
        shap_arr, baseline_s, pred_s = _shap_continuous_one(d, X_c, gi)
        cols = list(base_cols)
        raw_values_per_col = X_raw
    else:
        feat_names = d["feat"]
        X_uncentered = _build_x_binary(endpoint, features)
        X_c = X_uncentered - d["means"]
        X = np.concatenate([[1.0], X_c])
        shap_arr, baseline_s, pred_s = _shap_binary_one(d, X)
        cols = list(feat_names)
        raw_values_per_col = X_uncentered

    # Merge duplicate columns (FIM_Motor has 'Fim Motor_bl' at idx 0 and 2):
    # collapse to one row per unique feature name, summing SHAP contributions.
    seen: dict[str, int] = {}
    merged_rows = []
    for j, name in enumerate(cols):
        if name in seen:
            row = merged_rows[seen[name]]
            row["_shap"] = row["_shap"] + shap_arr[j]
        else:
            seen[name] = len(merged_rows)
            merged_rows.append({
                "key": name,
                "label": SHAP_FEATURE_LABELS.get(name, name),
                "value": float(raw_values_per_col[j]),
                "_shap": shap_arr[j].copy(),
            })

    features_out = []
    for row in merged_rows:
        sv = row["_shap"]
        features_out.append({
            "key": row["key"],
            "label": row["label"],
            "value": row["value"],
            "mean": float(sv.mean()),
            "ci_low": float(np.percentile(sv, 2.5)),
            "ci_high": float(np.percentile(sv, 97.5)),
        })

    return {
        "baseline_mean": float(baseline_s.mean()),
        "baseline_ci_low": float(np.percentile(baseline_s, 2.5)),
        "baseline_ci_high": float(np.percentile(baseline_s, 97.5)),
        "prediction_mean": float(pred_s.mean()),
        "features": features_out,
    }


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="TARGET BCN — clinical prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    features: dict


def _has(features: dict, key: str) -> bool:
    if key not in features or features[key] is None:
        return False
    try:
        return not np.isnan(float(features[key]))
    except (TypeError, ValueError):
        return False


def _endpoint_result(endpoint: str, features: dict) -> dict:
    required = HARD_REQUIRED[endpoint]
    missing_required = [k for k in required if not _has(features, k)]

    # Fill every missing field (hard-required + recommended) with the cohort
    # median so we can always compute a prediction + SHAP. The card UI still
    # shows the locked state when hard-required fields were missing -- the
    # prediction/SHAP values are then only available in the SHAP tab.
    filled = {k: float(features[k]) for k in features if _has(features, k)}
    imputed_fields: list[str] = []
    for k in HARD_REQUIRED[endpoint] + RECOMMENDED[endpoint]:
        if k not in filled and k in COHORT_MEDIANS:
            filled[k] = float(COHORT_MEDIANS[k])
            imputed_fields.append(k)

    samples = predict(endpoint, filled)
    shap = _shap_for_endpoint(endpoint, filled)

    if missing_required:
        status = "locked"
    elif any(k in imputed_fields for k in RECOMMENDED[endpoint]):
        status = "imputed"
    else:
        status = "complete"

    out = {
        "status": status,
        "median": float(np.median(samples)),
        "ci_50_low": float(np.quantile(samples, 0.25)),
        "ci_50_high": float(np.quantile(samples, 0.75)),
        "ci_95_low": float(np.quantile(samples, 0.025)),
        "ci_95_high": float(np.quantile(samples, 0.975)),
        "imputed_fields": imputed_fields,
        "shap": shap,
    }
    if missing_required:
        out["missing_required"] = missing_required
    return out


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/predict")
def predict_route(req: PredictRequest):
    features = req.features or {}
    return {ep: _endpoint_result(ep, features) for ep in ENDPOINTS}
