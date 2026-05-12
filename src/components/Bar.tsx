"use client";

type Props = {
  lo: number;
  hi: number;
  median: number;
  ci50_low: number;
  ci50_high: number;
  ci95_low: number;
  ci95_high: number;
  /** Admission/baseline value -- rendered as a small grey diamond on the
   * same axis to visualise the predicted change. Continuous endpoints only. */
  admission?: number;
  /** How to render a numeric value (e.g. integer for scores, percent for probs). */
  format: (v: number) => string;
  /** Muted styling for the imputed state. */
  muted?: boolean;
};

function clampPct(value: number, lo: number, hi: number): number {
  const pct = ((value - lo) / (hi - lo)) * 100;
  return Math.max(0, Math.min(100, pct));
}

export default function Bar({
  lo,
  hi,
  median,
  ci50_low,
  ci50_high,
  ci95_low,
  ci95_high,
  admission,
  format,
  muted = false,
}: Props) {
  const medP = clampPct(median, lo, hi);
  const lo95 = clampPct(ci95_low, lo, hi);
  const hi95 = clampPct(ci95_high, lo, hi);
  const lo50 = clampPct(ci50_low, lo, hi);
  const hi50 = clampPct(ci50_high, lo, hi);
  const admP =
    admission !== undefined ? clampPct(admission, lo, hi) : undefined;

  const ci95 = muted ? "bg-teal-50" : "bg-teal-100";
  const ci50 = muted ? "bg-teal-200" : "bg-teal-300";
  const medianColor = muted ? "bg-teal-700/60" : "bg-teal-800";
  const medianText = muted ? "text-slate-500" : "text-teal-900";

  return (
    <div className="flex flex-col gap-1">
      {/* Median value floating above its tick */}
      <div className="relative h-5">
        <div
          className={`absolute -translate-x-1/2 text-base font-semibold tabular-nums leading-none ${medianText}`}
          style={{ left: `${medP}%` }}
        >
          {format(median)}
        </div>
      </div>

      {/* The bar itself */}
      <div className="relative h-6">
        {/* axis track */}
        <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-slate-200" />
        {/* 95% CrI band */}
        <div
          className={`absolute top-1/2 h-3.5 -translate-y-1/2 rounded-full ${ci95}`}
          style={{ left: `${lo95}%`, width: `${Math.max(hi95 - lo95, 0.5)}%` }}
        />
        {/* 50% CrI band */}
        <div
          className={`absolute top-1/2 h-3.5 -translate-y-1/2 rounded-full ${ci50}`}
          style={{ left: `${lo50}%`, width: `${Math.max(hi50 - lo50, 0.5)}%` }}
        />
        {/* admission diamond (continuous only) */}
        {admP !== undefined ? (
          <div
            className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rotate-45 border border-slate-400 bg-stone-50"
            style={{ left: `${admP}%` }}
            aria-label="admission value"
          />
        ) : null}
        {/* median tick */}
        <div
          className={`absolute top-1/2 h-5 w-0.5 -translate-x-1/2 -translate-y-1/2 ${medianColor}`}
          style={{ left: `${medP}%` }}
        />
      </div>

      {/* Axis end labels */}
      <div className="flex justify-between text-[11px] tabular-nums text-slate-400">
        <span>{format(lo)}</span>
        <span>{format(hi)}</span>
      </div>
    </div>
  );
}
