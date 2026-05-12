"""
FastAPI entry point for the TARGET clinical prediction app.

One POST /api/predict route. Takes a sparse `features` dict from the UI,
computes status per endpoint (locked / imputed / complete), median-fills
recommended-but-missing fields with cohort medians, and returns posterior
predictive summaries (median, 50% CrI, 95% CrI) for the five endpoints.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from _core import (
    COHORT_MEDIANS,
    ENDPOINTS,
    HARD_REQUIRED,
    RECOMMENDED,
    predict,
)

app = FastAPI(title="TARGET BCN — clinical prediction API")

# Open CORS for local dev. Tighten before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    features: dict[str, float | int | None]


def _has(features: dict[str, Any], key: str) -> bool:
    """A field is considered present if it's in the dict and not None / NaN."""
    if key not in features or features[key] is None:
        return False
    try:
        return not np.isnan(float(features[key]))
    except (TypeError, ValueError):
        return False


def _endpoint_result(endpoint: str, features: dict[str, Any]) -> dict[str, Any]:
    required = HARD_REQUIRED[endpoint]
    missing_required = [k for k in required if not _has(features, k)]

    if missing_required:
        return {
            "status": "locked",
            "missing_required": missing_required,
            "imputed_fields": [],
        }

    filled = {k: float(features[k]) for k in features if _has(features, k)}
    imputed_fields: list[str] = []
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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/predict")
def predict_route(req: PredictRequest) -> dict[str, dict[str, Any]]:
    features = req.features or {}
    return {ep: _endpoint_result(ep, features) for ep in ENDPOINTS}
