"use client";
import { useState } from "react";
import { ENDPOINTS } from "@/lib/types";
import type { EndpointKey, PredictResponse } from "@/lib/types";
import ShapWaterfall from "./ShapWaterfall";

type Props = {
  predictions: PredictResponse | undefined;
};

export default function ShapPanel({ predictions }: Props) {
  const [active, setActive] = useState<EndpointKey>("Barthel");
  const spec = ENDPOINTS.find((e) => e.key === active)!;
  const result = predictions?.[active];

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
      {/* Endpoint sub-tabs */}
      <nav
        aria-label="SHAP endpoint sub-tabs"
        className="-mx-2 mb-4 flex flex-wrap gap-1 border-b border-slate-200 pb-2"
      >
        {ENDPOINTS.map((e) => {
          const isActive = e.key === active;
          return (
            <button
              key={e.key}
              type="button"
              onClick={() => setActive(e.key)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                isActive
                  ? "bg-teal-50 text-teal-800 ring-1 ring-teal-200"
                  : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {e.short}
            </button>
          );
        })}
      </nav>

      <header className="mb-4">
        <h3 className="text-sm font-semibold text-slate-800">{spec.title}</h3>
        {spec.subtitle ? (
          <p className="mt-0.5 text-[11px] text-slate-500">{spec.subtitle}</p>
        ) : null}
      </header>

      {result ? (
        <>
          {result.status === "locked" ? (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-[11px] text-amber-800">
              Hard-required fields are imputed from cohort medians for this
              SHAP view. The Predictions tab still shows this endpoint as
              locked until you fill them in.
            </div>
          ) : result.imputed_fields.length > 0 ? (
            <p className="mb-3 text-[11px] text-amber-700">
              Imputed from cohort medians: {result.imputed_fields.join(", ")}
            </p>
          ) : null}
          <ShapWaterfall spec={spec} shap={result.shap} />
        </>
      ) : (
        <p className="text-xs text-slate-400">Loading…</p>
      )}
    </div>
  );
}
