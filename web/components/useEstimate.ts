"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createEstimator, type EstimateStatus, type Posted } from "@/lib/estimator";
import type { Estimate, EstimateContent, EstimateInputs, ShownError } from "@/lib/types";

async function post(inputs: EstimateInputs): Promise<Posted> {
  try {
    const response = await fetch("/api/estimate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(inputs) });
    return { status: response.status, body: await response.json().catch(() => null) };
  } catch {
    return { status: 0, body: null };
  }
}

const opening = (content: EstimateContent): Estimate => ({ ...content.estimate, request_id: "opening" });

/** The inputs a visitor sets and the estimate for them. Page state only: nothing is stored, and the opening estimate needs no request. */
export function useEstimate(content: EstimateContent) {
  const [inputs, setInputs] = useState<EstimateInputs>(content.start);
  const [estimate, setEstimate] = useState<Estimate>(() => opening(content));
  const [status, setStatus] = useState<EstimateStatus>("idle");
  const [error, setError] = useState<ShownError | undefined>();
  const remembered = useRef<Record<string, number>>(Object.fromEntries(Object.entries(content.start.labs).map(([k, v]) => [k, v as number])));
  const estimator = useMemo(
    () => createEstimator({ post, onResult: (e) => setEstimate(e), onStatus: (s, err) => { setStatus(s); setError(err); } }),
    [],
  );
  useEffect(() => () => estimator.cancel(), [estimator]);

  const change = useCallback((next: EstimateInputs) => {
    setInputs(next);
    estimator.request(next);
  }, [estimator]);

  return {
    inputs, estimate, status, error,
    setLab: (key: string, value: number) => { remembered.current[key] = value; change({ ...inputs, labs: { ...inputs.labs, [key]: value } }); },
    setDone: (key: string, done: boolean) => change({ ...inputs, labs: { ...inputs.labs, [key]: done ? remembered.current[key] : null } }),
    setSymptom: (key: string, state: "absent" | "possible" | "present") => change({ ...inputs, symptoms: { ...inputs.symptoms, [key]: state } }),
    reset: () => {
      estimator.cancel();
      remembered.current = Object.fromEntries(Object.entries(content.start.labs).map(([k, v]) => [k, v as number]));
      setInputs(content.start);
      setEstimate(opening(content));
      setStatus("idle");
      setError(undefined);
    },
  };
}
