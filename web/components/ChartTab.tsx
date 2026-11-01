import { PacketPanel } from "./PacketPanel";
import { ReportCard, type Outcome } from "./ReportCard";
import type { DemoPatient } from "@/lib/types";

type Props = {
  patients: DemoPatient[];
  patient: DemoPatient;
  onSelect: (slug: string) => void;
  onRun: () => void;
  outcome: Outcome;
  labNames: Record<string, string>;
};

export function ChartTab({ patients, patient, onSelect, onRun, outcome, labNames }: Props) {
  return (
    <>
    <div className="two">
      <section className="chart" aria-label="Patient chart">
        <div className="picker" role="group" aria-label="Demo patients">
          {patients.map((p) => (
            <button key={p.slug} data-track={`patient:${p.slug}`} aria-pressed={p.slug === patient.slug} onClick={() => onSelect(p.slug)}>{p.title}</button>
          ))}
        </div>
        <p className="muted small">Demo patient {patient.patient_id} (invented). {patient.look_for}</p>
        <table>
          <caption>Labs on the chart</caption>
          <thead><tr><th>Lab</th><th>Value</th><th>Unit</th><th>Reference range</th></tr></thead>
          <tbody>
            {patient.chart.labs.map((l) => (
              <tr key={l.lab}>
                <td>{l.name} ({l.abbr})</td>
                <td>{l.value === null ? <span className="muted">not reported</span> : l.value}</td>
                <td>{l.value === null ? "" : l.unit}</td>
                <td data-testid={`range-${l.lab}`}>
                  {l.ref_lo}–{l.ref_hi} {l.ref_unit}
                  {l.flag && <span className={`flag flag-${l.flag}`} data-testid={`flag-${l.lab}`} aria-label={l.flag === "H" ? "high" : "low"} title={l.flag === "H" ? "Above the reference range" : "Below the reference range"}>{l.flag}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <h2>Note</h2>
        <pre className="note" data-testid="note">{patient.chart.note}</pre>
        <details>
          <summary data-track="sent_message_expander">Message sent to the agent</summary>
          <p className="muted small">The check sends exactly this text, built from the chart&apos;s labs and note, and nothing else.</p>
          <pre className="note" data-testid="sent-message">{patient.message}</pre>
        </details>
        <button className="primary" data-track="run_check" onClick={onRun} disabled={outcome.kind === "loading"}>Run V-K check</button>
      </section>
      <ReportCard outcome={outcome} labNames={labNames} />
    </div>
    <PacketPanel key={patient.slug} message={patient.message} />
    </>
  );
}
