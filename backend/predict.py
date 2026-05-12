"""
Posterior predictive samples for the 5 TARGET endpoints.

Each pickle in data/ contains the fitted Stan draws plus the centring means
and column order used at training time (run_regimputed.py / fit_one.py in the
thesis repo). Continuous endpoints (Barthel, FIM Total, FIM Motor) are
multilevel truncated-normal with 4 age x days_ps intercepts; binary endpoints
(Gait, MRS) are Bayesian logistic regression with an intercept column.

NOTE: although the v3 *original* fit logit-transformed Barthel, the regimputed
pickles store y on the raw 0-100 scale (verified: y in [16, 100], sigma ~24,
alpha ~95-135). predict() therefore samples directly from a truncated normal
on the Barthel scale -- no logit-to-Barthel back-transform is applied.
"""
from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.special import expit
from scipy.stats import truncnorm

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Thresholds defining the 4-level age x days_ps intercept grid at training time.
AGE_CUT, DAYS_CUT = 68, 10

ENDPOINTS: dict[str, dict] = {
    "Barthel":   {"file": "barthel.pkl",   "kind": "continuous"},
    "FIM_Total": {"file": "fim_total.pkl", "kind": "continuous"},
    "FIM_Motor": {"file": "fim_motor.pkl", "kind": "continuous"},
    "Gait":      {"file": "gait.pkl",      "kind": "binary"},
    "MRS":       {"file": "mrs.pkl",       "kind": "binary"},
}

# Cohort medians used by the UI's "Use cohort median" button and by the
# imputation logic in main.py. Means used internally for centring come from
# each pickle's `means` field (training-cohort means, slightly different).
COHORT_MEDIANS: dict[str, float] = {
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

# Hard-required inputs per endpoint. Missing any of these -> locked card.
HARD_REQUIRED: dict[str, list[str]] = {
    "Barthel":   ["Barthel_bl", "age", "days_ps", "los", "nihss"],
    "FIM_Total": ["Fim Total_bl", "age", "days_ps", "los", "nihss"],
    "FIM_Motor": ["Fim Motor_bl", "age", "days_ps", "los", "nihss"],
    "Gait":      ["age", "days_ps", "nihss"],
    "MRS":       ["Mrs_bl", "age", "days_ps", "nihss"],
}

# Recommended (median-fillable) predictors per endpoint. If any are missing
# but all hard-required are present -> imputed status.
RECOMMENDED: dict[str, list[str]] = {
    "Barthel":   ["VLX Marxa_bl", "Fim Motor_bl"],
    "FIM_Total": ["VLX Marxa_bl", "Fim Motor_bl"],
    "FIM_Motor": ["VLX Marxa_bl"],
    "Gait":      ["Fim Motor_bl", "VLX Marxa_bl"],
    "MRS":       ["Barthel_bl"],
}


@lru_cache(maxsize=8)
def _load(endpoint: str) -> dict:
    cfg = ENDPOINTS[endpoint]
    with open(DATA_DIR / cfg["file"], "rb") as f:
        return pickle.load(f)


def _group_idx(age: float, days_ps: float) -> int:
    age_group = 1 if age >= AGE_CUT else 0
    days_group = 1 if days_ps >= DAYS_CUT else 0
    return age_group * 2 + days_group


def _build_x_continuous(features: dict, base_cols: Iterable[str]) -> np.ndarray:
    """Map a flat features dict to the (K,) base_cols vector.

    A column name may appear twice (FIM_Motor's base_cols has 'Fim Motor_bl'
    in both position 0 and position 2). Both slots receive the same value;
    that's how the Stan fit was parameterised.
    """
    return np.array([float(features[col]) for col in base_cols])


def _build_x_binary(endpoint: str, features: dict) -> np.ndarray:
    """Build the uncentred (5,) predictor vector for a binary endpoint."""
    if endpoint == "Gait":
        baseline_walker = 1.0 if features.get("VLX Marxa_bl", 0.0) >= 0.4 else 0.0
        return np.array([
            baseline_walker,
            float(features["age"]),
            float(features["days_ps"]),
            float(features["Fim Motor_bl"]),
            float(features["nihss"]),
        ])
    # MRS
    baseline_mrs_good = 1.0 if float(features["Mrs_bl"]) <= 2 else 0.0
    return np.array([
        baseline_mrs_good,
        float(features["age"]),
        float(features["days_ps"]),
        float(features["Barthel_bl"]),
        float(features["nihss"]),
    ])


def _linpred_continuous(endpoint: str, features: dict) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
    """Return (mu_samples, sigma_samples, bounds) for a continuous endpoint.
    Deterministic given features + stored draws -- separated out so the
    unit test can compare against the pickle directly without RNG noise.
    """
    d = _load(endpoint)
    X = _build_x_continuous(features, d["base_cols"]) - d["means"]
    gi = _group_idx(float(features["age"]), float(features["days_ps"]))
    mu = d["alpha"][:, gi] + X @ d["beta"].T
    return mu, d["sigma"], tuple(d["bounds"])


def _linpred_binary(endpoint: str, features: dict) -> np.ndarray:
    """Return eta samples (4000,) for a binary endpoint."""
    d = _load(endpoint)
    feats = _build_x_binary(endpoint, features) - d["means"]
    X = np.concatenate([[1.0], feats])
    return X @ d["beta"].T


def predict(endpoint: str, features: dict, rng: np.random.Generator | None = None) -> np.ndarray:
    """Return 4000 posterior predictive samples for ``endpoint``.

    Continuous endpoints: samples on the original score scale, truncated to
    that scale's clinical bounds. Binary endpoints: posterior samples of the
    discharge probability in [0,1] (one sample per posterior draw, so the
    output captures parameter uncertainty rather than Bernoulli noise).
    """
    if endpoint not in ENDPOINTS:
        raise ValueError(f"Unknown endpoint: {endpoint!r}")
    rng = rng if rng is not None else np.random.default_rng(20240416)

    if ENDPOINTS[endpoint]["kind"] == "continuous":
        mu, sigma, (lo, hi) = _linpred_continuous(endpoint, features)
        a = (lo - mu) / sigma
        b = (hi - mu) / sigma
        return truncnorm.rvs(a, b, loc=mu, scale=sigma, random_state=rng)

    return expit(_linpred_binary(endpoint, features))
