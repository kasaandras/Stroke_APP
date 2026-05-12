"use client";
import { ENDPOINTS } from "@/lib/types";
import type { EndpointKey, PredictResponse } from "@/lib/types";

type Props = {
  predictions: PredictResponse | undefined;
};

function formatFor(key: EndpointKey, v: number): string {
  return key === "Gait" || key === "MRS"
    ? `${(v * 100).toFixed(0)}%`
    : v.toFixed(0);
}

export default function MobileChipStrip({ predictions }: Props) {
  return (
    <nav
      aria-label="Endpoint predictions summary"
      className="sticky top-0 z-30 w-full overflow-x-auto border-b border-slate-200 bg-stone-50/95 backdrop-blur lg:hidden"
    >
      <ul className="flex gap-2 whitespace-nowrap px-4 py-2">
        {ENDPOINTS.map((spec) => {
          const result = predictions?.[spec.key];
          let label = "—";
          let cls = "bg-slate-100 text-slate-500 border-slate-200";
          if (result?.status === "imputed" || result?.status === "complete") {
            label = formatFor(spec.key, result.median);
            cls =
              result.status === "complete"
                ? "bg-teal-50 text-teal-800 border-teal-200"
                : "bg-amber-50 text-amber-800 border-amber-200";
          }
          return (
            <li key={spec.key}>
              <a
                href={`#card-${spec.key}`}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${cls}`}
              >
                <span>{spec.short}</span>
                <span className="tabular-nums">{label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
