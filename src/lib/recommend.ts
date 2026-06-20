import type { Features } from "./types";

export type RankedTreatment = {
  treatment: string;
  predicted_delta_mps: number;
  ci_lo: number;
  ci_hi: number;
  ci_method: "between-arm" | "within-arm-only" | "no-data";
  n_arms: number;
  n_patients: number;
  /** baseline + Δ, raw (may exceed the 2.5 m/s physiological ceiling). */
  predicted_discharge_mps: number | null;
  discharge_above_ceiling: boolean;
  /** (min, max) of baselines across arms contributing to this row. */
  studied_baseline_range: [number, number] | null;
  /** Query baseline > max studied baseline for this row's arms. */
  baseline_above_studied_range: boolean;
};

export type NoGaitEntry = {
  treatment: string;
  scales: string[];
  n_arms: number;
};

export type CellFiring = {
  sev_band: "Mild" | "Moderate" | "Severe";
  age_band: "Young" | "Old";
  firing: number;
};

export type RecommendResponse = {
  chronicity: "Acute" | "Subacute" | "Chronic";
  severity: number;
  severity_scales_used: string[];
  severity_memberships: Record<"Mild" | "Moderate" | "Severe", number>;
  age_memberships: Record<"Young" | "Old", number>;
  cell_firings: CellFiring[];
  ranked: RankedTreatment[];
  no_gait: NoGaitEntry[];
  top3_all_overlap: boolean | null;
  pairs_nonoverlap: { a: string; b: string }[];
  query_gait_mps: number;
  /** Physiological reference (2.5 m/s). Above this, discharge_above_ceiling fires. */
  ceiling_mps: number;
};

export type RecommendInput = {
  gait_mps: number;
  age: number;
  days_ps: number;
  barthel?: number;
  fim_motor?: number;
  fim_total?: number;
};

/** Build a recommend request body from the Features dict the inputs pane uses.
 * Returns null when required fields for the ranker (gait, age, days_ps) are
 * missing -- the caller should render an empty / instructional state. */
export function buildRecommendInput(features: Features): RecommendInput | null {
  const gait = features["VLX Marxa_bl"];
  const age = features.age;
  const days = features.days_ps;
  if (gait === undefined || age === undefined || days === undefined) return null;
  return {
    gait_mps: gait,
    age,
    days_ps: days,
    barthel: features.Barthel_bl,
    fim_motor: features["Fim Motor_bl"],
    fim_total: features["Fim Total_bl"],
  };
}

export async function fetchRecommend(
  input: RecommendInput,
  signal?: AbortSignal,
): Promise<RecommendResponse> {
  const r = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal,
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`recommend failed: HTTP ${r.status}`);
  return (await r.json()) as RecommendResponse;
}
