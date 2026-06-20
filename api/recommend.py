"""
Fuzzy treatment ranker — Vercel serverless function at /api/recommend.

Self-contained port of treatment_ranker.py from the thesis repo:
results/fuzzy_treatment_ranker/treatment_ranker.py. The module is inlined
(no underscore-helper imports) so Vercel's Python runtime registers it
reliably -- the same pattern that fixed /api/predict earlier in the project.

Observational evidence surfacing, NOT a per-patient predictor and NOT a
causal selector. The frontend is responsible for the framing language;
this endpoint just returns the ranked output + diagnostics so the UI can
render them.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scipy import stats as _stats


DATA_DIR = Path(__file__).resolve().parent / "data"


# ─── continuous functional scales (severity inputs) ──────────────────────────
# (scale_name, arm_summary_csv column, lo, hi, assumed_SD).
SCALE_DEFS = [
    ("Barthel",   "barthel_base",   0,   100, 20.0),
    ("mBarthel",  "mBarthel_base",  0,   100, 20.0),
    ("FIM_Total", "fim_base",       18,  126, 25.0),
    ("Motricity", "motricity_base", 0,   100, 25.0),
    ("BBS",       "BBS_base",       0,   56,  12.0),
    ("BBT",       "BBT_base",       0,   60,  15.0),
    ("SIS",       "sis_base",       33,  165, 25.0),
    ("Rivermead", "rivermead_base", 0,   15,  4.0),
]
GAIT_RANGE = 2.0
GAIT_SD_FALLBACK = 0.20


def severity_score(gait_mps: float, n_for_prec: int,
                   base_sd_gait: float | None,
                   other_scales: dict | None = None) -> tuple:
    n = max(int(n_for_prec or 1), 1)
    other_scales = other_scales or {}

    gait_norm = float(np.clip(1.0 - gait_mps / GAIT_RANGE, 0.0, 1.0))
    sd_g = base_sd_gait if (base_sd_gait and base_sd_gait > 0) else GAIT_SD_FALLBACK
    prec_g = n * (GAIT_RANGE ** 2) / (sd_g ** 2)
    contributions = [(prec_g, gait_norm, "gait")]
    used = ["gait"]

    for name, _col, lo, hi, sd in SCALE_DEFS:
        if name not in other_scales:
            continue
        v = other_scales[name]
        if v is None or pd.isna(v):
            continue
        try:
            v = float(v)
        except (ValueError, TypeError):
            continue
        norm = float(np.clip(1.0 - (v - lo) / (hi - lo), 0.0, 1.0))
        prec = n * (hi - lo) ** 2 / sd ** 2
        contributions.append((prec, norm, name))
        used.append(name)

    if len(contributions) == 1:
        return gait_norm, ["gait"], {"gait": prec_g}

    tot = sum(p for p, _, _ in contributions)
    weighted = sum(p * s for p, s, _ in contributions) / tot
    precisions = {name: p for p, _, name in contributions}
    return float(weighted), used, precisions


# ─── fuzzy membership functions ──────────────────────────────────────────────
def trap_mf(x: float, a: float, b: float, c: float, d: float) -> float:
    # Strict inequalities at the outer edges so shouldered MFs (a == b
    # left-shouldered, c == d right-shouldered) return μ = 1 at their boundary
    # rather than 0. The previous `x <= a or x >= d` form silently zeroed Mild
    # at x=0, Severe at x=1, and Old at x=100 -- the bug fix moves arms with
    # severity = 1.0 exactly from Mild × Old to Severe × Old.
    if x < a or x > d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b > a else 1.0
    if x > c:
        return (d - x) / (d - c) if d > c else 1.0
    return 0.0


SEVERITY_MF = {
    "Mild":     (0.00, 0.00, 0.55, 0.65),
    "Moderate": (0.55, 0.65, 0.75, 0.85),
    "Severe":   (0.75, 0.85, 1.00, 1.00),
}
AGE_MF = {
    "Young": (18.0, 18.0, 55.0, 65.0),
    "Old":   (55.0, 65.0, 100.0, 100.0),
}


def memberships(x: float, mf_dict: dict) -> dict:
    return {label: trap_mf(x, *corners) for label, corners in mf_dict.items()}


def chronicity_band(days_ps: float) -> str:
    if days_ps < 90:
        return "Acute"
    if days_ps <= 180:
        return "Subacute"
    return "Chronic"


# ─── arm-level data loading & cell assignment ────────────────────────────────
def _load_arms() -> pd.DataFrame:
    arms = pd.read_csv(DATA_DIR / "arm_summary.csv")
    syn = pd.read_csv(DATA_DIR / "synthetic_trials_r07.csv")
    gs = syn[syn["baseline_scale"] == "Gait_speed"].copy()
    gs["_delta"] = gs["follow_up_score"] - gs["baseline_score"]
    delta = (gs.groupby("arm_group_id")
                .agg(baseline_mps=("baseline_score", "mean"),
                     followup_mps=("follow_up_score", "mean"),
                     n_patients=("patient_id", "count"),
                     within_delta_sd=("_delta", "std"))
                .reset_index())
    delta["delta_mps"] = delta["followup_mps"] - delta["baseline_mps"]
    arms = arms.merge(delta, left_on="group_id", right_on="arm_group_id", how="left")

    def arm_gait_mps(r):
        if r["final_scale"] != "Gait_speed":
            return None
        if r["unit_role"] == "time":
            return float(r["implied_dist_m"]) / float(r["base_m"])
        return float(r["base_m"])

    arms["arm_gait_mps"] = arms.apply(arm_gait_mps, axis=1)

    sevs, used_lists = [], []
    for _, r in arms.iterrows():
        if r["arm_gait_mps"] is None:
            scale = r["final_scale"]
            v = r["base_m"]
            if scale == "Barthel":
                norm = float(np.clip(1 - v / 100, 0, 1))
            elif scale == "FIM_Motor":
                norm = float(np.clip(1 - (v - 13) / (91 - 13), 0, 1))
            elif scale == "FIM_Total":
                norm = float(np.clip(1 - (v - 18) / (126 - 18), 0, 1))
            elif scale == "Gait_FAC":
                norm = float(np.clip(1 - v / 5, 0, 1))
            else:
                norm = 0.5
            sevs.append(norm)
            used_lists.append([scale])
            continue
        others = {}
        for name, col, *_ in SCALE_DEFS:
            v = r.get(col)
            if v is not None and pd.notna(v):
                try:
                    others[name] = float(v)
                except (ValueError, TypeError):
                    pass
        sev, used, _ = severity_score(
            r["arm_gait_mps"], int(r["base_n"]),
            float(r["base_sd"]) if pd.notna(r["base_sd"]) else None,
            others,
        )
        sevs.append(sev)
        used_lists.append(used)

    arms["severity"] = sevs
    arms["sev_scales_used"] = ["|".join(u) for u in used_lists]
    arms["chronicity"] = arms["days_ps"].apply(chronicity_band)
    arms["sev_band"] = arms["severity"].apply(
        lambda s: max(memberships(s, SEVERITY_MF), key=memberships(s, SEVERITY_MF).get))
    arms["age_band"] = arms["age_base"].apply(
        lambda a: max(memberships(a, AGE_MF), key=memberships(a, AGE_MF).get))
    return arms


def _build_systems(arms: pd.DataFrame) -> dict:
    systems = {}
    for chron in ["Acute", "Subacute", "Chronic"]:
        sub = arms[arms["chronicity"] == chron]
        cells = {}
        for sev_b in ["Mild", "Moderate", "Severe"]:
            for age_b in ["Young", "Old"]:
                in_cell = sub[(sub["sev_band"] == sev_b) & (sub["age_band"] == age_b)]
                gait = in_cell[in_cell["final_scale"] == "Gait_speed"]
                t_data = {}
                for t in gait["therapy_bucket"].unique():
                    tt = gait[gait["therapy_bucket"] == t]
                    arm_details = []
                    for _, row in tt.iterrows():
                        arm_details.append(dict(
                            delta=float(row["delta_mps"]),
                            n=int(row["n_patients"]),
                            within_delta_sd=(float(row["within_delta_sd"])
                                              if pd.notna(row["within_delta_sd"]) else None),
                            arm_baseline_mps=float(row["baseline_mps"]),
                        ))
                    total_n = sum(a["n"] for a in arm_details)
                    nw_mean = (sum(a["delta"] * a["n"] for a in arm_details) / total_n
                                if total_n > 0 else float("nan"))
                    t_data[t] = dict(mean_delta=nw_mean,
                                      arm_details=arm_details,
                                      n_arms=len(arm_details),
                                      n_patients=int(total_n))
                non_gait = in_cell[in_cell["final_scale"] != "Gait_speed"]
                no_gait_list = []
                for t in non_gait["therapy_bucket"].unique():
                    if t in t_data:
                        continue
                    tt = non_gait[non_gait["therapy_bucket"] == t]
                    no_gait_list.append(dict(treatment=t,
                                              scales=sorted(tt["final_scale"].unique().tolist()),
                                              n_arms=int(len(tt))))
                cells[(sev_b, age_b)] = dict(treatments=t_data,
                                              no_gait=no_gait_list,
                                              n_arms_in_cell=int(len(in_cell)))
        systems[chron] = cells
    return systems


@lru_cache(maxsize=1)
def get_systems() -> dict:
    """Load arms + build chronicity-stratified rule systems. Cached for the
    lifetime of a warm function instance."""
    return _build_systems(_load_arms())


def _compute_treatment_ci(arm_details: list, alpha: float = 0.05) -> dict:
    K = len(arm_details)
    total_n = sum(a["n"] for a in arm_details)
    if total_n <= 0 or K == 0:
        return dict(mean=float("nan"), ci_lo=None, ci_hi=None,
                    method="no-data", K=K, n=int(total_n))
    nw_mean = sum(a["delta"] * a["n"] for a in arm_details) / total_n

    if K >= 2:
        deltas = np.array([a["delta"] for a in arm_details], dtype=float)
        s = float(np.std(deltas, ddof=1))
        se = s / np.sqrt(K)
        t_crit = float(_stats.t.ppf(1 - alpha / 2, df=K - 1))
        return dict(mean=nw_mean, ci_lo=nw_mean - t_crit * se,
                    ci_hi=nw_mean + t_crit * se,
                    method="between-arm", K=K, n=int(total_n), se=se)
    a = arm_details[0]
    sd = a["within_delta_sd"] if (a["within_delta_sd"] and a["within_delta_sd"] > 0) else 0.10
    se = sd / np.sqrt(max(a["n"], 1))
    z = 1.96
    return dict(mean=nw_mean, ci_lo=nw_mean - z * se,
                ci_hi=nw_mean + z * se,
                method="within-arm-only", K=1, n=int(a["n"]), se=se)


def _cis_overlap(ci_a: tuple, ci_b: tuple) -> bool:
    return max(ci_a[0], ci_b[0]) <= min(ci_a[1], ci_b[1])


# ─── Soft warnings: physiological ceiling + studied-baseline-range ──────────
# Both are FLAGS only. Predicted Δ and CIs are returned UNMODIFIED. The UI
# decides how to display the warnings.
GAIT_DISCHARGE_CEILING_MPS = 2.5  # synthesis Gait_speed scale ceiling


def _apply_ceiling_and_range(row: dict, query_baseline_mps: float | None,
                              arm_details: list) -> dict:
    """Add diagnostic fields without modifying predicted_delta_mps or its CIs:
       - predicted_discharge_mps          = baseline + Δ  (may exceed 2.5)
       - discharge_above_ceiling          = True if discharge > 2.5 m/s
       - studied_baseline_range           = (min, max) of arm baselines for
                                             arms contributing to this row
       - baseline_above_studied_range     = baseline > max studied baseline
    """
    out = dict(row)
    arm_baselines = [a["arm_baseline_mps"] for a in arm_details
                     if a.get("arm_baseline_mps") is not None]
    if arm_baselines:
        out["studied_baseline_range"] = (float(min(arm_baselines)),
                                          float(max(arm_baselines)))
    else:
        out["studied_baseline_range"] = None

    if query_baseline_mps is None:
        out["predicted_discharge_mps"] = None
        out["discharge_above_ceiling"] = False
        out["baseline_above_studied_range"] = False
        return out

    b = float(query_baseline_mps)
    disch = b + float(row["predicted_delta_mps"])
    out["predicted_discharge_mps"] = float(disch)
    out["discharge_above_ceiling"] = bool(disch > GAIT_DISCHARGE_CEILING_MPS + 1e-9)
    if out["studied_baseline_range"] is not None:
        out["baseline_above_studied_range"] = bool(
            b > out["studied_baseline_range"][1] + 1e-9
        )
    else:
        out["baseline_above_studied_range"] = False
    return out


def rank_treatments(severity: float, age: float, days_ps: float,
                    systems: dict,
                    query_gait_mps: float | None = None) -> dict:
    chron = chronicity_band(days_ps)
    system = systems[chron]
    sev_mu = memberships(severity, SEVERITY_MF)
    age_mu = memberships(age, AGE_MF)

    agg = defaultdict(lambda: dict(arm_details=[], cells=[]))
    no_gait_agg = defaultdict(lambda: dict(scales=set(), n_arms=0))
    cell_firings = {}

    for (sev_b, age_b), cell in system.items():
        firing = min(sev_mu[sev_b], age_mu[age_b])
        cell_firings[(sev_b, age_b)] = firing
        if firing <= 0:
            continue
        for t, info in cell["treatments"].items():
            d = agg[t]
            d["arm_details"].extend(info["arm_details"])
            d["cells"].append((sev_b, age_b, firing, info["mean_delta"]))
        for entry in cell["no_gait"]:
            if entry["treatment"] in agg:
                continue
            no_gait_agg[entry["treatment"]]["scales"].update(entry["scales"])
            no_gait_agg[entry["treatment"]]["n_arms"] += entry["n_arms"]

    ranked = []
    for t, d in agg.items():
        ci = _compute_treatment_ci(d["arm_details"])
        if np.isnan(ci["mean"]):
            continue
        row = dict(treatment=t,
                    predicted_delta_mps=ci["mean"],
                    ci_lo=ci["ci_lo"], ci_hi=ci["ci_hi"],
                    ci_method=ci["method"],
                    n_arms=ci["K"],
                    n_patients=ci["n"])
        row = _apply_ceiling_and_range(row, query_gait_mps, d["arm_details"])
        ranked.append(row)
    ranked.sort(key=lambda r: -r["predicted_delta_mps"])

    pairs_nonoverlap = []
    if len(ranked) >= 2:
        for i in range(len(ranked)):
            for j in range(i + 1, len(ranked)):
                a = (ranked[i]["ci_lo"], ranked[i]["ci_hi"])
                b = (ranked[j]["ci_lo"], ranked[j]["ci_hi"])
                if not _cis_overlap(a, b):
                    pairs_nonoverlap.append((ranked[i]["treatment"], ranked[j]["treatment"]))
    top3_all_overlap = None
    if len(ranked) >= 2:
        top_n = min(3, len(ranked))
        all_overlap = True
        for i in range(top_n):
            for j in range(i + 1, top_n):
                a = (ranked[i]["ci_lo"], ranked[i]["ci_hi"])
                b = (ranked[j]["ci_lo"], ranked[j]["ci_hi"])
                if not _cis_overlap(a, b):
                    all_overlap = False
        top3_all_overlap = all_overlap

    no_gait_list = [dict(treatment=t,
                          scales=sorted(d["scales"]),
                          n_arms=d["n_arms"]) for t, d in no_gait_agg.items()]

    return dict(chronicity=chron, cell_firings=cell_firings,
                ranked=ranked, no_gait=no_gait_list,
                top3_all_overlap=top3_all_overlap,
                pairs_nonoverlap=pairs_nonoverlap,
                query_gait_mps=query_gait_mps,
                ceiling_mps=GAIT_DISCHARGE_CEILING_MPS)


# ─── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(title="TARGET BCN — fuzzy treatment ranker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    gait_mps: float
    age: float
    days_ps: float
    barthel: float | None = None
    fim_motor: float | None = None
    fim_total: float | None = None


@app.post("/api/recommend")
def recommend_route(req: RecommendRequest):
    other_scales = {}
    if req.barthel is not None:
        other_scales["Barthel"] = req.barthel
    if req.fim_motor is not None:
        other_scales["FIM_Motor"] = req.fim_motor
    if req.fim_total is not None:
        other_scales["FIM_Total"] = req.fim_total

    sev, used, _ = severity_score(req.gait_mps, 1, None, other_scales)
    res = rank_treatments(sev, req.age, req.days_ps, get_systems(),
                          query_gait_mps=req.gait_mps)

    sev_mu = memberships(sev, SEVERITY_MF)
    age_mu = memberships(req.age, AGE_MF)

    # JSON-serialise the cell_firings tuple keys.
    cell_firings_dict = [
        {"sev_band": k[0], "age_band": k[1], "firing": float(v)}
        for k, v in res["cell_firings"].items()
    ]
    pairs = [{"a": a, "b": b} for a, b in res["pairs_nonoverlap"]]

    ranked_json = []
    for r in res["ranked"]:
        sbr = r.get("studied_baseline_range")
        ranked_json.append({
            "treatment": r["treatment"],
            "predicted_delta_mps": float(r["predicted_delta_mps"]),
            "ci_lo": float(r["ci_lo"]) if r["ci_lo"] is not None else None,
            "ci_hi": float(r["ci_hi"]) if r["ci_hi"] is not None else None,
            "ci_method": r["ci_method"],
            "n_arms": r["n_arms"],
            "n_patients": r["n_patients"],
            # New diagnostic fields. Raw values, never clipped.
            "predicted_discharge_mps": (float(r["predicted_discharge_mps"])
                                        if r.get("predicted_discharge_mps") is not None else None),
            "discharge_above_ceiling": bool(r.get("discharge_above_ceiling", False)),
            "studied_baseline_range": ([float(sbr[0]), float(sbr[1])]
                                        if sbr is not None else None),
            "baseline_above_studied_range": bool(r.get("baseline_above_studied_range", False)),
        })

    return {
        "chronicity": res["chronicity"],
        "severity": float(sev),
        "severity_scales_used": used,
        "severity_memberships": {k: float(v) for k, v in sev_mu.items()},
        "age_memberships": {k: float(v) for k, v in age_mu.items()},
        "cell_firings": cell_firings_dict,
        "ranked": ranked_json,
        "no_gait": [
            {"treatment": e["treatment"], "scales": e["scales"], "n_arms": e["n_arms"]}
            for e in res["no_gait"]
        ],
        "top3_all_overlap": res["top3_all_overlap"],
        "pairs_nonoverlap": pairs,
        "query_gait_mps": float(req.gait_mps),
        "ceiling_mps": float(res["ceiling_mps"]),
    }
