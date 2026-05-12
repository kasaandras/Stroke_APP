"use client";
import { FIELD_BY_KEY } from "@/lib/fields";
import type { EndpointResult, EndpointSpec, FieldKey, Features } from "@/lib/types";
import Bar from "./Bar";

type Props = {
  spec: EndpointSpec;
  result: EndpointResult | undefined;
  features: Features;
  loading: boolean;
};

function formatScore(v: number): string {
  return v.toFixed(0);
}
function formatProb(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}
function fieldLabel(key: string): string {
  return FIELD_BY_KEY[key as FieldKey]?.label ?? key;
}

export default function EndpointCard({ spec, result, features, loading }: Props) {
  // Locked state
  if (!result || result.status === "locked") {
    const missing = result?.missing_required ?? [];
    return (
      <article className="rounded-xl border border-slate-200 bg-slate-100/70 px-5 py-4">
        <header className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-500">{spec.title}</h3>
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Locked
          </span>
        </header>
        {spec.subtitle ? (
          <p className="mt-0.5 text-[11px] text-slate-400">{spec.subtitle}</p>
        ) : null}
        {missing.length > 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            Needs:{" "}
            <span className="text-slate-700">
              {missing.map(fieldLabel).join(", ")}
            </span>
          </p>
        ) : (
          <p className="mt-2 text-xs text-slate-500">
            Fill the required fields on the left to unlock this prediction.
          </p>
        )}
      </article>
    );
  }

  const muted = result.status === "imputed";
  const cardClass = muted
    ? "border-amber-200/70 bg-amber-50/40"
    : "border-teal-200/70 bg-white";

  const isContinuous = spec.kind === "continuous";
  const fmt = isContinuous ? formatScore : formatProb;
  const lo = isContinuous ? spec.axis!.lo : 0;
  const hi = isContinuous ? spec.axis!.hi : 1;
  const admission =
    isContinuous && features[spec.axis!.baseline] !== undefined
      ? (features[spec.axis!.baseline] as number)
      : undefined;

  return (
    <article
      className={`relative rounded-xl border px-5 py-4 transition ${cardClass}`}
    >
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800">{spec.title}</h3>
        {muted ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-800">
            Imputed
          </span>
        ) : (
          <span className="text-[11px] uppercase tracking-wider text-teal-700">
            Complete
          </span>
        )}
      </header>
      {spec.subtitle ? (
        <p className="mt-0.5 text-[11px] text-slate-500">{spec.subtitle}</p>
      ) : null}

      <div className="mt-4">
        <Bar
          lo={lo}
          hi={hi}
          median={result.median}
          ci50_low={result.ci_50_low}
          ci50_high={result.ci_50_high}
          ci95_low={result.ci_95_low}
          ci95_high={result.ci_95_high}
          admission={admission}
          format={fmt}
          muted={muted}
        />
      </div>

      <footer className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11px] text-slate-500">
        <span className="tabular-nums">
          50% CrI {fmt(result.ci_50_low)}–{fmt(result.ci_50_high)} · 95% CrI{" "}
          {fmt(result.ci_95_low)}–{fmt(result.ci_95_high)}
        </span>
        {muted && result.imputed_fields.length > 0 ? (
          <span className="text-amber-700">
            Imputed: {result.imputed_fields.map(fieldLabel).join(", ")}
          </span>
        ) : null}
      </footer>

      {loading ? (
        <span className="pointer-events-none absolute right-3 top-3 inline-block h-2 w-2 animate-pulse rounded-full bg-teal-400" />
      ) : null}
    </article>
  );
}
