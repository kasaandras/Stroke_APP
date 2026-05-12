"""
Self-consistency tests for predict.py against the stored Stan draws.

For every endpoint we pick a real training row from the pickle, reconstruct
the raw (uncentred) feature dict, push it back through predict._linpred_*,
and confirm the deterministic linear predictor matches what we get by
computing it directly from the pickle's stored design matrix. This catches
any error in column ordering, centring means, group_idx logic, or the
intercept handling for binary endpoints.

It also runs the full predict() once per endpoint to sanity-check that
samples fall inside the clinical bounds (continuous) or [0,1] (binary).
"""
import numpy as np

from _core import (
    ENDPOINTS,
    _linpred_continuous,
    _linpred_binary,
    _load,
    _group_idx,
    predict,
)


def _build_raw_features(d: dict, row: int) -> dict:
    """Reconstruct an uncentred feature dict from one training row.

    Works for both continuous (X has K columns matching base_cols) and binary
    (X has 1+K columns: intercept then features matching `feat`).
    """
    means = d["means"]
    if "base_cols" in d:  # continuous
        cols = d["base_cols"]
        raw = d["X"][row] + means
        feats = {col: float(val) for col, val in zip(cols, raw)}
        # FIM_Total and FIM_Motor don't have days_ps in base_cols, but the
        # stored gi[row] was computed from the patient's true days_ps.
        # Synthesise a value that reproduces the same group_idx (1 = late
        # bucket, days_ps >= 10; 0 = early, days_ps < 10).
        if "days_ps" not in feats:
            days_group = int(d["gi"][row]) % 2
            feats["days_ps"] = 15.0 if days_group == 1 else 5.0
        return feats
    # binary: X[row,0] is the intercept, X[row,1:] are centred features
    raw = d["X"][row, 1:] + means
    feat_map = dict(zip(d["feat"], raw))
    # Round-trip the derived predictors (baseline_walker, baseline_mrs_good,
    # fim_bl, barthel_bl) into the public feature names so predict() can
    # reconstruct them. The 1/0 derived flag must round-trip exactly.
    if "baseline_walker" in feat_map:
        # baseline_walker = 1 iff VLX Marxa_bl >= 0.4; pick a synthesising
        # value so predict() reproduces the same flag.
        return {
            "VLX Marxa_bl": 1.0 if feat_map["baseline_walker"] >= 0.5 else 0.0,
            "age": feat_map["age"],
            "days_ps": feat_map["days_ps"],
            "Fim Motor_bl": feat_map["fim_bl"],
            "nihss": feat_map["nihss"],
        }
    # MRS
    return {
        "Mrs_bl": 0.0 if feat_map["baseline_mrs_good"] >= 0.5 else 6.0,
        "age": feat_map["age"],
        "days_ps": feat_map["days_ps"],
        "Barthel_bl": feat_map["barthel_bl"],
        "nihss": feat_map["nihss"],
    }


def test_continuous(endpoint: str, row: int = 0) -> None:
    d = _load(endpoint)
    features = _build_raw_features(d, row)
    # 1) group_idx reconstruction matches the stored gi (gi was saved 0-based)
    gi_expected = int(d["gi"][row])
    gi_actual = _group_idx(features["age"], features["days_ps"])
    assert gi_actual == gi_expected, (
        f"{endpoint} row{row} group_idx mismatch: {gi_actual} vs {gi_expected}"
    )
    # 2) Deterministic linpred matches direct computation
    mu_actual, _, _ = _linpred_continuous(endpoint, features)
    mu_expected = d["alpha"][:, gi_expected] + d["X"][row] @ d["beta"].T
    np.testing.assert_allclose(mu_actual, mu_expected, rtol=1e-10, atol=1e-10)
    # 3) Full predict() returns samples inside bounds
    samples = predict(endpoint, features)
    lo, hi = d["bounds"]
    assert samples.shape == (d["alpha"].shape[0],)
    assert samples.min() >= lo - 1e-9 and samples.max() <= hi + 1e-9
    print(
        f"  [OK] {endpoint:<10} row {row}: group={gi_expected}, "
        f"mu mean={mu_expected.mean():7.2f}, "
        f"pred median={np.median(samples):6.2f}, true y={d['y'][row]:6.2f}"
    )


def test_binary(endpoint: str, row: int = 0) -> None:
    d = _load(endpoint)
    features = _build_raw_features(d, row)
    # 1) Deterministic eta matches direct computation
    eta_actual = _linpred_binary(endpoint, features)
    eta_expected = d["X"][row] @ d["beta"].T
    np.testing.assert_allclose(eta_actual, eta_expected, rtol=1e-10, atol=1e-10)
    # 2) Full predict() returns probabilities in [0,1]
    samples = predict(endpoint, features)
    assert samples.shape == (d["beta"].shape[0],)
    assert samples.min() >= 0.0 and samples.max() <= 1.0
    print(
        f"  [OK] {endpoint:<10} row {row}: eta mean={eta_expected.mean():+6.3f}, "
        f"p median={np.median(samples):.3f}, true y={int(d['y'][row])}"
    )


def main() -> None:
    print("Self-consistency tests for predict.py")
    print("-" * 60)
    # Spread across rows to catch indexing bugs
    for ep in ["Barthel", "FIM_Total", "FIM_Motor"]:
        for row in (0, 17, -1):
            test_continuous(ep, row)
    for ep in ["Gait", "MRS"]:
        for row in (0, 17, -1):
            test_binary(ep, row)
    print("-" * 60)
    print("All tests passed.")


if __name__ == "__main__":
    main()
