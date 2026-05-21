export type FieldKey =
  | "age"
  | "days_ps"
  | "nihss"
  | "los"
  | "Barthel_bl"
  | "Fim Total_bl"
  | "Fim Motor_bl"
  | "VLX Marxa_bl"
  | "Mrs_bl";

export type Features = Partial<Record<FieldKey, number>>;

export type EndpointKey = "Barthel" | "FIM_Total" | "FIM_Motor" | "Gait" | "MRS";

export type ShapFeature = {
  key: string;
  label: string;
  /** Raw (uncentred) input value used in this SHAP calculation. */
  value: number;
  /** Posterior mean Shapley value on the prediction scale (score for
   * continuous endpoints, probability in [0,1] for binary). */
  mean: number;
  ci_low: number;
  ci_high: number;
};

export type ShapBlock = {
  baseline_mean: number;
  baseline_ci_low: number;
  baseline_ci_high: number;
  prediction_mean: number;
  features: ShapFeature[];
};

export type LockedResult = {
  status: "locked";
  missing_required: string[];
  imputed_fields: string[];
  median: number;
  ci_50_low: number;
  ci_50_high: number;
  ci_95_low: number;
  ci_95_high: number;
  shap: ShapBlock;
};

export type ScoredResult = {
  status: "imputed" | "complete";
  median: number;
  ci_50_low: number;
  ci_50_high: number;
  ci_95_low: number;
  ci_95_high: number;
  imputed_fields: string[];
  shap: ShapBlock;
};

export type EndpointResult = LockedResult | ScoredResult;

export type PredictResponse = Record<EndpointKey, EndpointResult>;

/** UI metadata for each endpoint. */
export type EndpointSpec = {
  key: EndpointKey;
  title: string;
  /** Short label used in the mobile chip strip. */
  short: string;
  /** Small clarifying line under the title. Used on binary endpoints to
   * spell out exactly what the percentage refers to. */
  subtitle?: string;
  kind: "continuous" | "binary";
  /** For continuous endpoints: the axis range and which field holds the
   * admission baseline (rendered as a small diamond on the same axis). */
  axis?: { lo: number; hi: number; baseline: FieldKey };
};

export const ENDPOINTS: EndpointSpec[] = [
  {
    key: "Barthel",
    title: "Barthel Index at discharge",
    short: "Barthel",
    kind: "continuous",
    axis: { lo: 0, hi: 100, baseline: "Barthel_bl" },
  },
  {
    key: "FIM_Total",
    title: "FIM Total at discharge",
    short: "FIM Total",
    kind: "continuous",
    axis: { lo: 18, hi: 126, baseline: "Fim Total_bl" },
  },
  {
    key: "FIM_Motor",
    title: "FIM Motor at discharge",
    short: "FIM Motor",
    kind: "continuous",
    axis: { lo: 13, hi: 91, baseline: "Fim Motor_bl" },
  },
  {
    key: "Gait",
    title: "Walking at discharge",
    short: "Walking",
    subtitle: "Probability of gait velocity ≥ 0.4 m/s at discharge",
    kind: "binary",
  },
  {
    key: "MRS",
    title: "Good outcome (mRS ≤ 2)",
    short: "mRS ≤ 2",
    subtitle: "Probability of mRS ≤ 2 at discharge",
    kind: "binary",
  },
];
