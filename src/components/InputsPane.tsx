"use client";
import {
  DAYS_PS_EXTRAPOLATION_THRESHOLD,
  FIELDS,
  FIELD_BY_KEY,
  FIELD_GROUPS,
} from "@/lib/fields";
import type { FieldKey } from "@/lib/types";
import NumberInput from "./NumberInput";

type Props = {
  features: Partial<Record<FieldKey, number>>;
  onChange: (key: FieldKey, value: number | undefined) => void;
  onUseCohortMedian: () => void;
  onReset: () => void;
};

export default function InputsPane({
  features,
  onChange,
  onUseCohortMedian,
  onReset,
}: Props) {
  const warningFor = (key: FieldKey): string | undefined => {
    const v = features[key];
    if (v === undefined) return undefined;
    const f = FIELD_BY_KEY[key];
    if (key === "days_ps" && v > DAYS_PS_EXTRAPOLATION_THRESHOLD) {
      return `Outside training range (>${DAYS_PS_EXTRAPOLATION_THRESHOLD} days post-stroke)`;
    }
    if (f.softMax !== undefined && v > f.softMax) {
      return `Above the trained range (${f.label.split(" ")[0]} ≤ ${f.softMax})`;
    }
    return undefined;
  };

  return (
    <div className="flex flex-col gap-6">
      {FIELD_GROUPS.map((group) => (
        <section key={group.title} className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {group.title}
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {group.keys.map((key) => (
              <NumberInput
                key={key}
                field={FIELD_BY_KEY[key]}
                value={features[key]}
                onChange={(v) => onChange(key, v)}
                warning={warningFor(key)}
              />
            ))}
          </div>
        </section>
      ))}

      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={onUseCohortMedian}
          className="rounded-md border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-medium text-teal-800 transition hover:bg-teal-100"
        >
          Use cohort median for empty fields
        </button>
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Reset
        </button>
      </div>

      <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
        Cohort medians (Hospital del Mar, n≈208 acute): age {FIELDS.find((f) => f.key === "age")?.cohortMedian},
        days post-stroke 6 (IQR 4–11.5), NIHSS 4, LOS 14, Barthel 58, FIM Total 80, FIM Motor 52,
        gait velocity 0.29 m/s, mRS 3.
      </p>
    </div>
  );
}
