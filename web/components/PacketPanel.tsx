"use client";

import { useState } from "react";
import policy from "@/content/pet_ct_policy.json";
import type { Answer, AttestedId, Packet, PacketDecline, ShownError } from "@/lib/types";

const ATTESTED: AttestedId[] = ["C3", "C4", "C5", "C6"];
const WORDING = Object.fromEntries(policy.criteria.map((c) => [c.id, c.text])) as Record<string, string>;
const STATUS_LABEL = { met: "Met", unmet: "Unmet", unknown: "Unknown" } as const;
const ANSWER_LABEL: Record<Answer, string> = { unanswered: "Not yet answered", yes: "Yes", no: "No" };
const MAX_RATIONALE = 1000;

type State = { kind: "idle" } | { kind: "loading" } | { kind: "error"; error: ShownError } | { kind: "done"; packet: Packet | PacketDecline };

async function request(message: string, attestations: Record<AttestedId, Answer>): Promise<State> {
  try {
    const response = await fetch("/api/packet", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, attestations }),
    });
    const body = (await response.json()) as { packet?: Packet | PacketDecline; error?: ShownError };
    if (response.ok && body.packet) return { kind: "done", packet: body.packet };
    return { kind: "error", error: body.error ?? { code: "error", message: "Something went wrong. Please try again." } };
  } catch {
    return { kind: "error", error: { code: "network", message: "Could not reach the demo. Please check your connection and try again." } };
  }
}

function plainText(packet: Packet, rationale: string): string {
  const evidence = new Map(packet.evidence.map((e) => [e.id, e.text]));
  const lines = ["PET-CT readiness packet (fictional policy; demo)", packet.notice, ""];
  for (const c of packet.criteria) {
    lines.push(`${c.id} ${STATUS_LABEL[c.status]}: ${c.text}`);
    for (const id of c.cites) lines.push(`  - ${evidence.get(id) ?? id}`);
  }
  lines.push("", "Still missing:", ...(packet.gaps.length ? packet.gaps.map((g) => `  - ${g.prompt}`) : ["  - nothing"]));
  lines.push("", "Summary:", ...packet.summary.map((s) => `  ${s.text}`));
  if (rationale.trim()) lines.push("", "Clinician's rationale (clinician's own words):", rationale.trim());
  lines.push("", "Drafted by tool, reviewed by clinician (demo).", packet.disclaimer);
  return lines.join("\n");
}

function PacketView({ packet, signed, rationale, onRationale, onSign }: {
  packet: Packet; signed: boolean; rationale: string; onRationale: (v: string) => void; onSign: () => void;
}) {
  const evidence = new Map(packet.evidence.map((e) => [e.id, e.text]));
  const unmet = packet.criteria.filter((c) => c.status === "unmet");
  const risk = packet.report;
  return (
    <div data-testid="packet">
      <table>
        <caption>Criteria in the fictional K-17 PET-CT policy</caption>
        <thead><tr><th>Criterion</th><th>Status</th><th>Evidence</th></tr></thead>
        <tbody>
          {packet.criteria.map((c) => (
            <tr key={c.id} data-testid={`criterion-${c.id}`}>
              <td><strong>{c.id}</strong> {c.text}</td>
              <td data-testid={`status-${c.id}`}>{STATUS_LABEL[c.status]}</td>
              <td>{c.cites.map((id) => <div key={id} className="small">{evidence.get(id) ?? id}</div>)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Still missing</h3>
      <ul data-testid="packet-gaps">
        {packet.gaps.length ? packet.gaps.map((g) => <li key={g.criterion}>{g.prompt}</li>) : <li>Nothing is missing.</li>}
      </ul>
      <h3>Summary</h3>
      <p className="muted small" data-testid="summary-source">
        {packet.summary_source === "model"
          ? "Drafted by the language model; every sentence was checked by code against the table and its evidence."
          : "Written from a fixed template: the model's draft did not pass the checks, or the model was unavailable."}
      </p>
      <ul data-testid="packet-summary">{packet.summary.map((s) => <li key={s.criterion}>{s.text}</li>)}</ul>
      {risk && (
        <p className="muted small" data-testid="packet-context">
          Why this patient was flagged (context only; it decides no criterion): the model estimates {Math.round(risk.probability * 100)}%
          {risk.interval ? `, a range of ${Math.round(risk.interval[0] * 100)}% to ${Math.round(risk.interval[1] * 100)}% if missing results are obtained` : ""}.
        </p>
      )}
      {unmet.length > 0 && (
        <div>
          <h3>Unmet criteria</h3>
          <p className="small">{unmet.map((c) => c.id).join(", ")} {unmet.length === 1 ? "is" : "are"} unmet on the evidence above.
            To request the scan anyway, the clinician may add a rationale in their own words. This tool never writes or changes it.</p>
          <label>
            <span className="small">Clinician&apos;s rationale (your own words; the tool never writes this)</span>
            <textarea data-testid="rationale" value={rationale} maxLength={MAX_RATIONALE} readOnly={signed} rows={4}
              onChange={(e) => onRationale(e.target.value)} />
          </label>
        </div>
      )}
      <p className="small" data-testid="packet-notice">{packet.notice} {packet.disclaimer}</p>
      {signed ? (
        <div data-testid="signed">
          <p><strong>Drafted by tool, reviewed by clinician (demo)</strong></p>
          <div className="no-print">
            <button data-track="packet_copy" onClick={() => navigator.clipboard?.writeText(plainText(packet, rationale))}>Copy</button>{" "}
            <button data-track="packet_print" onClick={() => window.print()}>Print</button>
          </div>
        </div>
      ) : (
        <button className="primary no-print" data-track="packet_signoff" onClick={onSign}>Demo sign-off (nothing is submitted)</button>
      )}
    </div>
  );
}

/** The scan-readiness packet for the selected patient. Answers and the rationale live only in this component's state. */
export function PacketPanel({ message }: { message: string }) {
  const [answers, setAnswers] = useState<Record<AttestedId, Answer>>({ C3: "unanswered", C4: "unanswered", C5: "unanswered", C6: "unanswered" });
  const [state, setState] = useState<State>({ kind: "idle" });
  const [rationale, setRationale] = useState("");
  const [signed, setSigned] = useState(false);

  function answer(id: AttestedId, value: Answer) {
    setAnswers({ ...answers, [id]: value });
    setState({ kind: "idle" }); // the packet on screen no longer matches the answers
  }
  async function prepare() {
    setSigned(false);
    setState({ kind: "loading" });
    setState(await request(message, answers));
  }

  return (
    <section className="chart packet-panel" aria-label="PET-CT readiness packet">
      <h2>PET-CT readiness packet <span className="muted small">(fictional policy)</span></h2>
      <p className="muted small no-print">Assembles the evidence for each criterion, lists what is still missing, and decides nothing. A person answers the attestations below; nothing is filled in from the note.</p>
      <fieldset disabled={signed} className="no-print">
        <legend>Clinician attestations</legend>
        {ATTESTED.map((id) => (
          <div key={id} className="attest">
            <span className="small">{id}. {WORDING[id]}</span>{" "}
            <select aria-label={`${id}: ${WORDING[id]}`} value={answers[id]} onChange={(e) => answer(id, e.target.value as Answer)}>
              {(Object.keys(ANSWER_LABEL) as Answer[]).map((a) => <option key={a} value={a}>{ANSWER_LABEL[a]}</option>)}
            </select>
          </div>
        ))}
      </fieldset>
      <button className="primary no-print" data-track="prepare_packet" onClick={prepare} disabled={state.kind === "loading" || signed}>Prepare PET-CT packet</button>
      {state.kind === "loading" && <p aria-live="polite">Working on it…</p>}
      {state.kind === "error" && <p role="alert" data-testid="packet-error">{state.error.message}</p>}
      {state.kind === "done" && state.packet.declined && <p role="alert" data-testid="packet-declined">{state.packet.message}</p>}
      {state.kind === "done" && !state.packet.declined && (
        <PacketView packet={state.packet} signed={signed} rationale={rationale} onRationale={setRationale} onSign={() => setSigned(true)} />
      )}
      {state.kind !== "done" && <p className="small" data-testid="packet-notice-idle">All data is synthetic and the disease is fictional. This is not medical advice.</p>}
    </section>
  );
}
