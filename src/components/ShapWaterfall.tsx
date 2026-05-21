"use client";
import type { EndpointSpec, ShapBlock } from "@/lib/types";

type Props = {
  spec: EndpointSpec;
  shap: ShapBlock;
};

function formatValue(spec: EndpointSpec, v: number): string {
  return spec.kind === "binary" ? `${(v * 100).toFixed(0)}%` : v.toFixed(1);
}

function formatDelta(spec: EndpointSpec, v: number): string {
  const sign = v >= 0 ? "+" : "−";
  const abs = Math.abs(v);
  return spec.kind === "binary"
    ? `${sign}${(abs * 100).toFixed(1)} pp`
    : `${sign}${abs.toFixed(1)}`;
}

export default function ShapWaterfall({ spec, shap }: Props) {
  // Order features by |mean SHAP| descending. Sorting on the frontend keeps
  // the backend output canonical and lets us swap orderings later if needed.
  const ordered = [...shap.features].sort(
    (a, b) => Math.abs(b.mean) - Math.abs(a.mean),
  );

  // Cumulative SHAP per row, starting at baseline.
  let cum = shap.baseline_mean;
  const rows = ordered.map((f) => {
    const start = cum;
    const end = cum + f.mean;
    cum = end;
    return { ...f, start, end };
  });

  // Auto-zoom x-axis to the actual data range with 15% padding, clipped to
  // the endpoint's clinical bounds. Using the full 0-100 (or 0-1) axis hides
  // most of the action when inputs are close to cohort medians and SHAP
  // contributions are all sub-unit.
  const clinicalLo = spec.kind === "binary" ? 0 : spec.axis!.lo;
  const clinicalHi = spec.kind === "binary" ? 1 : spec.axis!.hi;
  const xValues: number[] = [shap.baseline_mean, shap.prediction_mean];
  for (const r of rows) {
    xValues.push(r.start, r.end, r.start + r.ci_low, r.start + r.ci_high);
  }
  const dataLo = Math.min(...xValues);
  const dataHi = Math.max(...xValues);
  const dataSpan = Math.max(dataHi - dataLo, spec.kind === "binary" ? 0.02 : 1);
  const pad = dataSpan * 0.2;
  const axisLo = Math.max(clinicalLo, dataLo - pad);
  const axisHi = Math.min(clinicalHi, dataHi + pad);
  const toPct = (v: number) =>
    Math.max(0, Math.min(100, ((v - axisLo) / (axisHi - axisLo)) * 100));

  const baselinePct = toPct(shap.baseline_mean);
  const predictionPct = toPct(shap.prediction_mean);
  // Stack the two top markers vertically when they're close enough that the
  // text would otherwise collide (~15% of axis width).
  const markersClose = Math.abs(predictionPct - baselinePct) < 18;

  return (
    <div className="flex flex-col gap-3">
      {/* axis header. When the two markers would collide, stack them vertically
       * (baseline on the top row, prediction on the bottom row) so the labels
       * never overlap. */}
      <div className={`relative ${markersClose ? "h-10" : "h-7"} text-[11px] text-slate-500`}>
        <div
          className="absolute -translate-x-1/2 whitespace-nowrap"
          style={{ left: `${baselinePct}%`, top: 0 }}
        >
          <div className="leading-none">baseline</div>
          <div className="tabular-nums leading-none text-slate-400">
            {formatValue(spec, shap.baseline_mean)}
          </div>
        </div>
        <div
          className="absolute -translate-x-1/2 whitespace-nowrap text-teal-800"
          style={{
            left: `${predictionPct}%`,
            top: markersClose ? 22 : 0,
          }}
        >
          <div className="leading-none font-medium">prediction</div>
          <div className="tabular-nums leading-none">
            {formatValue(spec, shap.prediction_mean)}
          </div>
        </div>
      </div>

      <div className="relative flex flex-col gap-1.5">
        {/* baseline + prediction vertical guides spanning the whole stack */}
        <div
          className="pointer-events-none absolute inset-y-0 w-px bg-slate-300"
          style={{ left: `${baselinePct}%` }}
        />
        <div
          className="pointer-events-none absolute inset-y-0 w-px bg-teal-600"
          style={{ left: `${predictionPct}%` }}
        />

        {rows.map((r) => {
          const positive = r.mean >= 0;
          const left = Math.min(toPct(r.start), toPct(r.end));
          const width = Math.abs(toPct(r.end) - toPct(r.start));
          const ciLeft = toPct(r.start + r.ci_low);
          const ciRight = toPct(r.start + r.ci_high);
          const ciWidth = Math.max(ciRight - ciLeft, 0.4);
          const barColor = positive ? "bg-teal-500/80" : "bg-rose-500/80";
          return (
            <div key={r.key} className="grid grid-cols-[170px_1fr_90px] items-center gap-2 text-[11px]">
              <div className="truncate text-slate-600">
                <span className="font-medium text-slate-800">{r.label}</span>{" "}
                <span className="tabular-nums text-slate-400">
                  = {r.value.toFixed(r.value % 1 === 0 ? 0 : 2)}
                </span>
              </div>
              <div className="relative h-5">
                {/* 95% CI band around this feature's contribution */}
                <div
                  className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-slate-200"
                  style={{ left: `${ciLeft}%`, width: `${Math.max(ciWidth, 0.4)}%` }}
                />
                {/* SHAP bar */}
                <div
                  className={`absolute top-1/2 h-3.5 -translate-y-1/2 rounded ${barColor}`}
                  style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%` }}
                />
              </div>
              <div className="text-right tabular-nums text-slate-600">
                {formatDelta(spec, r.mean)}
              </div>
            </div>
          );
        })}

        {/* axis ticks */}
        <div className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-400">
          <span>{formatValue(spec, axisLo)}</span>
          <span>{formatValue(spec, axisHi)}</span>
        </div>
      </div>

      <p className="text-[10px] leading-relaxed text-slate-400">
        Each bar is the feature&apos;s Shapley contribution to the prediction
        on the {spec.kind === "binary" ? "probability" : "score"} scale,
        placed at its cumulative position between the stratum baseline and the
        full prediction. Light grey 95 % posterior CrI band per feature.
      </p>
    </div>
  );
}
