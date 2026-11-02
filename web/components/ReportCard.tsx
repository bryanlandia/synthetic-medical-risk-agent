import type { ReactNode } from "react";
import type { Analysis, Gap, Report, ShownError } from "@/lib/types";

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

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function ReportCard({ outcome, labNames, callout }: { outcome: Outcome; labNames: Record<string, string>; callout?: ReactNode }) {
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
        {callout}
        <p className="muted">This looked like {REASONS[analysis.decline_reason ?? "other"] ?? REASONS.other}, so no risk was estimated.</p>
        <p data-testid="reply">{analysis.reply}</p>
      </section>
    );
  }
  const { report } = analysis;
  return (
    <section className="card" aria-live="polite">
      <h2>Risk estimate</h2>
      {callout}
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
      {report.interval && <RangeBlock report={report} labNames={labNames} />}
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

const MAX_GAPS = 5;

function RangeBlock({ report, labNames }: { report: Report; labNames: Record<string, string> }) {
  const [lo, hi] = report.interval!;
  const gaps = report.gaps ?? [];
  const name = (g: Gap) => (g.kind === "lab" ? labNames[g.key] ?? g.key : SYMPTOMS[g.key] ?? g.key);
  if (gaps.length === 0) {
    return <p className="muted" data-testid="range">Nothing on the chart or in the note is missing, so the estimate has no range.</p>;
  }
  return (
    <div>
      <p data-testid="range">Range if the missing results are obtained: <strong>{pct(lo)} to {pct(hi)}</strong></p>
      <p className="muted small">Covers only findings that are not on the record. It does not include uncertainty in the model itself.</p>
      <h3>Missing findings that could change the result</h3>
      <ul data-testid="gaps">
        {gaps.slice(0, MAX_GAPS).map((g) => (
          <li key={`${g.kind}-${g.key}`}>
            <strong>{name(g)}</strong>: {pct(g.low)} to {pct(g.high)}
            {g.changes_routing && <span className="badge warn"> could change the band</span>}
          </li>
        ))}
      </ul>
      {gaps.length > MAX_GAPS && <p className="muted small">and {gaps.length - MAX_GAPS} more with smaller effects</p>}
    </div>
  );
}
