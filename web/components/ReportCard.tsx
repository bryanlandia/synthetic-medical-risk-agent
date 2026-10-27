import type { Analysis, ShownError } from "@/lib/types";

export type Outcome = { kind: "idle" } | { kind: "loading" } | { kind: "error"; error: ShownError } | { kind: "done"; analysis: Analysis };

const REASONS: Record<string, string> = {
  treatment_request: "a treatment request",
  real_disease: "a question about a real disease",
  phi: "personal details",
  out_of_scope: "something outside this demo",
  other: "something this demo can't help with",
};
const WARNINGS: Record<string, string> = {
  missing_value: "Missing value",
  unit_mismatch: "Unit mismatch",
  contradiction: "Note and panel disagree",
  impossible_value: "Impossible value",
  note_flag_disagreement: "Note flag disagreement",
};
const SYMPTOMS: Record<string, string> = {
  tremor: "Tremor",
  fatigue: "Fatigue",
  photophobia: "Light sensitivity",
  joint_stiffness: "Joint stiffness",
  dizziness: "Dizziness",
};

export function ReportCard({ outcome, labNames }: { outcome: Outcome; labNames: Record<string, string> }) {
  if (outcome.kind === "idle") return <section className="card" aria-live="polite"><p className="muted">The result appears here.</p></section>;
  if (outcome.kind === "loading") return <section className="card" aria-live="polite"><p>Working on it… the first request can take a few seconds.</p></section>;
  if (outcome.kind === "error") {
    return (
      <section className="card error" role="alert">
        <h2>Could not run the check</h2>
        <p data-testid="error-message">{outcome.error.message}</p>
      </section>
    );
  }
  const { analysis } = outcome;
  if (analysis.declined || !analysis.report) {
    return (
      <section className="card declined" aria-live="polite">
        <h2>Declined</h2>
        <p className="muted">This looked like {REASONS[analysis.decline_reason ?? "other"] ?? REASONS.other}, so no risk was estimated.</p>
        <p data-testid="reply">{analysis.reply}</p>
      </section>
    );
  }
  const { report } = analysis;
  return (
    <section className="card" aria-live="polite">
      <h2>Risk estimate</h2>
      <p className="big" data-testid="probability">{Math.round(report.probability * 100)}%</p>
      <p>
        {report.uncertain ? <span className="badge warn" data-testid="uncertain">Uncertain: close to the line</span> : <span className="badge" data-testid="certain">Not in the uncertain band</span>}
      </p>
      {report.data_quality.length > 0 && (
        <div data-testid="warnings">
          <h3>Data-quality warnings</h3>
          <ul>
            {report.data_quality.map((w, i) => (
              <li key={i}>
                <strong>{WARNINGS[w.type] ?? w.type}</strong>
                {w.lab ? `: ${labNames[w.lab] ?? w.lab}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      <h3>What drove it</h3>
      <ul data-testid="evidence">{report.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
      <h3>Symptoms read from the note</h3>
      <p className="muted">{Object.entries(report.symptoms).map(([k, v]) => `${SYMPTOMS[k] ?? k}: ${v.replace("_", " ")}`).join(" · ")}</p>
      <h3>Reply</h3>
      <p data-testid="reply" className="reply">{analysis.reply}</p>
      <p className="muted small">
        {analysis.reply_source === "template" ? "Reply written by a template (the model's draft failed a check). " : ""}
        {analysis.usage.input_tokens + analysis.usage.output_tokens} tokens, ${analysis.usage.cost_usd.toFixed(4)} for this request.
      </p>
    </section>
  );
}
