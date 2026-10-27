"use client";

import { useMemo, useState } from "react";
import { Banner } from "./Banner";
import { AboutTab } from "./AboutTab";
import { ChartTab } from "./ChartTab";
import { FreeTextTab } from "./FreeTextTab";
import { ModelCardTab } from "./ModelCardTab";
import type { Outcome } from "./ReportCard";
import type { Analysis, DemoPatient, ShownError } from "@/lib/types";

type Tab = "chart" | "free" | "card" | "about";
const TABS: { id: Tab; label: string }[] = [
  { id: "chart", label: "Patient chart" },
  { id: "free", label: "Try the agent" },
  { id: "card", label: "Model card" },
  { id: "about", label: "About this project" },
];

/** One message in, one result out. Nothing is kept between sends: a new result replaces the last. */
async function send(message: string): Promise<Outcome> {
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const body = (await response.json()) as { analysis?: Analysis; error?: ShownError };
    if (response.ok && body.analysis) return { kind: "done", analysis: body.analysis };
    return { kind: "error", error: body.error ?? { code: "error", message: "Something went wrong. Please try again." } };
  } catch {
    return { kind: "error", error: { code: "network", message: "Could not reach the demo. Please check your connection and try again." } };
  }
}

export function Demo({ patients, cardBody, cardHash, about }: { patients: DemoPatient[]; cardBody: string; cardHash: string | null; about: string }) {
  const [tab, setTab] = useState<Tab>("chart");
  const [slug, setSlug] = useState(patients[0].slug);
  const [chartOutcome, setChartOutcome] = useState<Outcome>({ kind: "idle" });
  const [freeOutcome, setFreeOutcome] = useState<Outcome>({ kind: "idle" });
  const labNames = useMemo(() => Object.fromEntries(patients[0].chart.labs.map((l) => [l.lab, l.name])), [patients]);
  const patient = patients.find((p) => p.slug === slug) ?? patients[0];

  async function runCheck() {
    setChartOutcome({ kind: "loading" });
    setChartOutcome(await send(patient.message));
  }
  async function runFree(message: string) {
    setFreeOutcome({ kind: "loading" });
    setFreeOutcome(await send(message));
  }

  return (
    <>
      <Banner />
      <main>
        <h1>VK-Check <span className="muted">Decision support for Velorin-Kessler Syndrome diagnosis</span></h1>
        <div role="tablist" aria-label="Demo sections" className="tabs">
          {TABS.map((t) => (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === "chart" && (
            <ChartTab
              patients={patients}
              patient={patient}
              onSelect={(s) => { setSlug(s); setChartOutcome({ kind: "idle" }); }}
              onRun={runCheck}
              outcome={chartOutcome}
              labNames={labNames}
            />
          )}
          {tab === "free" && <FreeTextTab onSend={runFree} outcome={freeOutcome} labNames={labNames} />}
          {tab === "card" && <ModelCardTab body={cardBody} hash={cardHash} />}
          {tab === "about" && <AboutTab body={about} />}
        </div>
      </main>
    </>
  );
}
