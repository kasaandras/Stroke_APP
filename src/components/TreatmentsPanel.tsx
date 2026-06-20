"use client";
import { useEffect, useRef, useState } from "react";
import { useDebounced } from "@/lib/hooks";
import {
  buildRecommendInput,
  fetchRecommend,
} from "@/lib/recommend";
import type { RecommendResponse } from "@/lib/recommend";
import type { Features } from "@/lib/types";

type Props = {
  features: Features;
};

function severityBandLabel(
  m: Record<"Mild" | "Moderate" | "Severe", number>,
): string {
  const entries = Object.entries(m) as ["Mild" | "Moderate" | "Severe", number][];
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}
function ageBandLabel(m: Record<"Young" | "Old", number>): string {
  return m.Young >= m.Old ? "Young" : "Old";
}
function fmtScalesLabel(used: string[]): string {
  // "gait" + Barthel/FIM_Total etc. -> human-readable
  const map: Record<string, string> = {
    gait: "gait",
    Barthel: "Barthel",
    FIM_Motor: "FIM Motor",
    FIM_Total: "FIM Total",
    mBarthel: "modified Barthel",
  };
  return used.map((u) => map[u] ?? u).join(" + ");
}
function fmt3(v: number): string {
  return (v >= 0 ? "+" : "") + v.toFixed(3);
}

export default function TreatmentsPanel({ features }: Props) {
  const debounced = useDebounced(features, 300);
  const [data, setData] = useState<RecommendResponse | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const abortRef = useRef<AbortController | null>(null);

  const input = buildRecommendInput(debounced);

  const inputKey = input ? JSON.stringify(input) : "";
  /* eslint-disable react-hooks/set-state-in-effect --
     Identical fetch/abort/setState pattern to src/app/page.tsx; the rule
     only fires here because of the inputKey early return guard. */
  useEffect(() => {
    if (!inputKey) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(undefined);
    const reqInput = JSON.parse(inputKey) as typeof input & object;
    fetchRecommend(reqInput, ctrl.signal)
      .then((r) => {
        if (!ctrl.signal.aborted) setData(r);
      })
      .catch((e: unknown) => {
        if ((e as { name?: string } | undefined)?.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Recommend failed");
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [inputKey]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // When the required inputs aren't filled, render the empty state and don't
  // show any cached recommendations from a previous valid input.
  if (!input) {
    return (
      <article className="rounded-xl border border-slate-200 bg-slate-100/70 px-5 py-4">
        <header className="mb-1 text-sm font-semibold text-slate-500">
          Treatment evidence
        </header>
        <p className="text-xs text-slate-500">
          Enter <strong>gait velocity (admission)</strong>, <strong>age</strong>,
          and <strong>days post-stroke</strong> on the left to surface the
          ranked treatment evidence for this patient profile.
        </p>
      </article>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Framing block — must remain visible. */}
      <section className="rounded-xl border border-slate-200 bg-stone-100/80 px-5 py-3 text-[12px] leading-relaxed text-slate-600">
        <p className="font-medium text-slate-800">
          Observational evidence surfacing, not causal treatment selection.
        </p>
        <p className="mt-1">
          Rankings reflect <em>average gait change</em> reported in published
          trials for similar patients. They are NOT predictions of an individual
          patient&apos;s outcome and do NOT establish that one treatment is
          superior to another.
        </p>
      </section>

      {data ? (
        <>
          {/* Patient-context bar */}
          <section className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-[12px] text-slate-700">
            <p>
              <span className="font-medium">Severity:</span>{" "}
              <span className="tabular-nums">{data.severity.toFixed(3)}</span>{" "}
              ({severityBandLabel(data.severity_memberships)}, from{" "}
              {fmtScalesLabel(data.severity_scales_used)})
              <span className="px-2 text-slate-300">·</span>
              <span className="font-medium">Age:</span>{" "}
              <span className="tabular-nums">{input.age.toFixed(0)}</span>{" "}
              ({ageBandLabel(data.age_memberships)})
              <span className="px-2 text-slate-300">·</span>
              <span className="font-medium">Chronicity:</span> {data.chronicity}{" "}
              (day {input.days_ps.toFixed(0)})
            </p>
          </section>

          {/* Top-3 overlap banner — prominent when true. */}
          {data.top3_all_overlap === true ? (
            <section className="rounded-xl border-l-4 border-l-amber-400 border border-amber-200 bg-amber-50 px-5 py-3 text-[12px] leading-relaxed text-amber-900">
              <p className="font-semibold">
                On the available evidence, the top 3 treatments are NOT
                statistically distinguishable.
              </p>
              <p className="mt-1">
                All three 95 % CIs overlap. Treat this as suggestive central
                tendencies, not selection of a superior treatment.
              </p>
            </section>
          ) : null}

          {/* Ranked table */}
          <section className="rounded-xl border border-slate-200 bg-white">
            <header className="border-b border-slate-200 px-5 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Ranked treatments — {data.chronicity} system{" "}
              {loading ? (
                <span className="ml-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-teal-400" />
              ) : null}
            </header>
            {data.ranked.length === 0 ? (
              <p className="px-5 py-3 text-xs text-slate-500">
                No treatments with gait Δ data in the firing cells for this
                profile.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-[12px]">
                  <thead>
                    <tr className="text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
                      <th className="px-5 py-2 text-right">#</th>
                      <th className="py-2 pr-3">Treatment</th>
                      <th className="py-2 pr-3 text-right">Δ m/s [95 % CI]</th>
                      <th className="py-2 pr-3 text-right">Evidence</th>
                      <th className="py-2 pr-5 text-left">Flags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.ranked.map((r, i) => {
                      const isThin = r.ci_method === "within-arm-only";
                      const aboveCeiling = r.discharge_above_ceiling;
                      const aboveStudied = r.baseline_above_studied_range;
                      const sbr = r.studied_baseline_range;
                      const studiedRangeTooltip =
                        sbr !== null
                          ? `Trials behind this row studied baselines ${sbr[0].toFixed(2)}–${sbr[1].toFixed(2)} m/s; this patient's baseline is higher. Recommendation is observational extrapolation.`
                          : "";
                      return (
                        <tr key={r.treatment} className="align-top">
                          <td className="px-5 py-2 text-right tabular-nums text-slate-500">
                            {i + 1}
                          </td>
                          <td className="py-2 pr-3 font-medium text-slate-800">
                            {r.treatment}
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums text-slate-800">
                            <div>
                              <span className="font-semibold">
                                {fmt3(r.predicted_delta_mps)}
                              </span>
                              {r.predicted_discharge_mps !== null ? (
                                <span className="text-slate-500">
                                  {" "}→ {r.predicted_discharge_mps.toFixed(2)} m/s
                                </span>
                              ) : null}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              [{fmt3(r.ci_lo)}, {fmt3(r.ci_hi)}]
                            </div>
                          </td>
                          <td className="py-2 pr-3 text-right text-slate-500 tabular-nums">
                            {r.n_arms} arm{r.n_arms === 1 ? "" : "s"}, {r.n_patients} pts
                          </td>
                          <td className="py-2 pr-5">
                            <div className="flex flex-wrap gap-1">
                              {isThin ? (
                                <span
                                  title="CI based only on within-trial patient variability; understates true uncertainty by 5–10×"
                                  className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-900"
                                >
                                  ⚠ single trial — uncertainty understated
                                </span>
                              ) : (
                                <span className="text-[10px] uppercase tracking-wider text-slate-400">
                                  between-arm
                                </span>
                              )}
                              {aboveCeiling ? (
                                <span
                                  title={`Healthy elderly comfortable walking is ~1.3 m/s, max walking ~2.0–2.5 m/s. Interpret the predicted Δ with caution. Implied discharge ${r.predicted_discharge_mps?.toFixed(2)} m/s > ${data.ceiling_mps} m/s.`}
                                  className="inline-flex items-center rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-900"
                                >
                                  ⚠ discharge above ceiling ({data.ceiling_mps} m/s)
                                </span>
                              ) : null}
                              {aboveStudied ? (
                                <span
                                  title={studiedRangeTooltip}
                                  className="inline-flex items-center rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-900"
                                >
                                  ⚠ baseline above trial-evidence range
                                  {sbr !== null
                                    ? ` (${sbr[0].toFixed(2)}–${sbr[1].toFixed(2)})`
                                    : ""}
                                </span>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="border-t border-slate-100 px-5 py-2 text-[10px] leading-relaxed text-slate-400">
              Single-arm rows are based on one trial only; their CIs reflect
              within-trial patient variability and understate true uncertainty.
            </p>
          </section>

          {/* No-gait list */}
          {data.no_gait.length > 0 ? (
            <section className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-[12px] text-slate-700">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Also studied in this profile with non-gait outcomes
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Cannot be ranked by gait Δ.
              </p>
              <ul className="mt-2 space-y-0.5">
                {data.no_gait.map((e) => (
                  <li key={e.treatment} className="text-[12px]">
                    <span className="font-medium text-slate-800">{e.treatment}</span>{" "}
                    <span className="text-slate-500">
                      — {e.n_arms} arm{e.n_arms === 1 ? "" : "s"}{" "}
                      {e.scales.length > 0 ? `(scales: ${e.scales.join(", ")})` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {error ? <p className="text-xs text-red-600">{error}</p> : null}
        </>
      ) : loading ? (
        <p className="text-xs text-slate-400">Loading…</p>
      ) : null}
    </div>
  );
}
