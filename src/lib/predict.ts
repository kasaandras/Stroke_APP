import type { Features, PredictResponse } from "./types";

export async function fetchPredict(
  features: Features,
  signal?: AbortSignal,
): Promise<PredictResponse> {
  const r = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
    signal,
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`predict failed: HTTP ${r.status}`);
  return (await r.json()) as PredictResponse;
}
