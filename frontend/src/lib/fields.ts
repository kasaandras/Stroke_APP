import type { FieldKey } from "./types";

export type FieldSpec = {
  key: FieldKey;
  label: string;
  /** Hard UI bound. */
  min: number;
  max: number;
  step?: number;
  cohortMedian: number;
  /** A field whose realistic ceiling is below the hard max -- inputs above
   * this still validate but get a soft warning ("clinically allowed up to N"). */
  softMax?: number;
  hint?: string;
};

export const FIELDS: FieldSpec[] = [
  { key: "age", label: "Age", min: 38, max: 97, cohortMedian: 68.5 },
  {
    key: "days_ps",
    label: "Days post-stroke",
    min: 1,
    max: 82,
    cohortMedian: 6,
    hint: "Time from stroke onset to admission",
  },
  {
    key: "nihss",
    label: "NIHSS",
    min: 0,
    max: 42,
    cohortMedian: 4,
    softMax: 19,
    hint: "Trained on 0–19; allowed up to 42",
  },
  {
    key: "Barthel_bl",
    label: "Barthel (admission)",
    min: 0,
    max: 100,
    cohortMedian: 58,
  },
  {
    key: "Fim Total_bl",
    label: "FIM Total (admission)",
    min: 18,
    max: 126,
    cohortMedian: 80,
  },
  {
    key: "Fim Motor_bl",
    label: "FIM Motor (admission)",
    min: 13,
    max: 91,
    cohortMedian: 52,
  },
  {
    key: "VLX Marxa_bl",
    label: "Gait velocity (admission)",
    min: 0,
    max: 3,
    step: 0.01,
    cohortMedian: 0.29,
    hint: "m/s",
  },
  {
    key: "Mrs_bl",
    label: "mRS (admission)",
    min: 0,
    max: 6,
    cohortMedian: 3,
  },
  {
    key: "los",
    label: "Planned/expected LOS",
    min: 2,
    max: 60,
    cohortMedian: 14,
    hint: "Days",
  },
];

export const FIELD_BY_KEY: Record<FieldKey, FieldSpec> =
  Object.fromEntries(FIELDS.map((f) => [f.key, f])) as Record<FieldKey, FieldSpec>;

export type FieldGroup = { title: string; keys: FieldKey[] };

export const FIELD_GROUPS: FieldGroup[] = [
  { title: "Demographics", keys: ["age", "days_ps"] },
  { title: "Severity", keys: ["nihss"] },
  {
    title: "Baseline scores",
    keys: ["Barthel_bl", "Fim Total_bl", "Fim Motor_bl", "VLX Marxa_bl", "Mrs_bl"],
  },
  { title: "Care", keys: ["los"] },
];

/** Threshold beyond which days_ps is outside the training cohort. */
export const DAYS_PS_EXTRAPOLATION_THRESHOLD = 30;
