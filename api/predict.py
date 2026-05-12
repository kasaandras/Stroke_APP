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
from pathlib import Path
from typing import Iterable

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scipy.special import expit
from scipy.stats import truncnorm


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

    if missing_required:
        return {
            "status": "locked",
            "missing_required": missing_required,
            "imputed_fields": [],
        }

    filled = {k: float(features[k]) for k in features if _has(features, k)}
    imputed_fields = []
    for rec in RECOMMENDED[endpoint]:
        if rec not in filled:
            filled[rec] = float(COHORT_MEDIANS[rec])
            imputed_fields.append(rec)

    samples = predict(endpoint, filled)
    return {
        "status": "imputed" if imputed_fields else "complete",
        "median": float(np.median(samples)),
        "ci_50_low": float(np.quantile(samples, 0.25)),
        "ci_50_high": float(np.quantile(samples, 0.75)),
        "ci_95_low": float(np.quantile(samples, 0.025)),
        "ci_95_high": float(np.quantile(samples, 0.975)),
        "imputed_fields": imputed_fields,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/predict")
def predict_route(req: PredictRequest):
    features = req.features or {}
    return {ep: _endpoint_result(ep, features) for ep in ENDPOINTS}
