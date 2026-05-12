"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Banner from "@/components/Banner";
import EndpointCard from "@/components/EndpointCard";
import InputsPane from "@/components/InputsPane";
import MobileChipStrip from "@/components/MobileChipStrip";
import { FIELDS } from "@/lib/fields";
import { useDebounced } from "@/lib/hooks";
import { fetchPredict } from "@/lib/predict";
import { ENDPOINTS } from "@/lib/types";
import type { Features, FieldKey, PredictResponse } from "@/lib/types";

const EMPTY_FEATURES: Features = {};

export default function Page() {
  const [features, setFeatures] = useState<Features>(EMPTY_FEATURES);
  const [predictions, setPredictions] = useState<PredictResponse | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const debounced = useDebounced(features, 300);

  // Cancel stale requests so a fast typist's earlier fetch doesn't overwrite
  // a later one.
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(undefined);
    fetchPredict(debounced, ctrl.signal)
      .then((r) => {
        if (!ctrl.signal.aborted) setPredictions(r);
      })
      .catch((e: unknown) => {
        if ((e as { name?: string } | undefined)?.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Prediction failed");
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debounced]);

  const handleChange = useCallback((key: FieldKey, value: number | undefined) => {
    setFeatures((prev) => {
      if (value === undefined) {
        const { [key]: _, ...rest } = prev;
        void _;
        return rest;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  const handleUseCohortMedian = useCallback(() => {
    setFeatures((prev) => {
      const next = { ...prev };
      for (const f of FIELDS) {
        if (next[f.key] === undefined) next[f.key] = f.cohortMedian;
      }
      return next;
    });
  }, []);

  const handleReset = useCallback(() => {
    setFeatures(EMPTY_FEATURES);
  }, []);

  const cards = useMemo(
    () =>
      ENDPOINTS.map((spec) => (
        <div key={spec.key} id={`card-${spec.key}`} className="scroll-mt-32">
          <EndpointCard
            spec={spec}
            result={predictions?.[spec.key]}
            features={features}
            loading={loading}
          />
        </div>
      )),
    [predictions, features, loading],
  );

  return (
    <>
      <Banner />
      <MobileChipStrip predictions={predictions} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] lg:gap-10">
          {/* Inputs pane */}
          <section
            aria-label="Patient inputs"
            className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto lg:pr-2 scrollbar-thin"
          >
            <div className="mb-4">
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">
                Patient at admission
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                Live predictions update as you type. Fields with grey bounds
                show the clinically allowed range.
              </p>
            </div>
            <InputsPane
              features={features}
              onChange={handleChange}
              onUseCohortMedian={handleUseCohortMedian}
              onReset={handleReset}
            />
          </section>

          {/* Prediction cards */}
          <section aria-label="Predicted discharge outcomes" className="flex flex-col gap-4">
            <div className="mb-1 flex items-baseline justify-between">
              <h2 className="text-xl font-semibold tracking-tight text-slate-900">
                Predicted at discharge
              </h2>
              {error ? (
                <span className="text-xs text-red-600">{error}</span>
              ) : null}
            </div>
            {cards}
          </section>
        </div>

        <footer className="mt-12 border-t border-slate-200 pt-4 text-[11px] leading-relaxed text-slate-400">
          Research prototype for the TARGET Master&apos;s thesis (UPC
          Barcelona). Not for clinical decision-making outside the supervised
          feedback loop with Dr Nevajda.
        </footer>
      </main>
    </>
  );
}
