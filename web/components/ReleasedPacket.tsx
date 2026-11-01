"use client";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { STRIP_TEXT } from "@/lib/copy";
import type { CaseState } from "@/lib/store";
import type { CaseRecord, Packet } from "@/lib/types";
import { clock, CriterionChip, DemoNote, Row } from "./ui";

const STUDY = "K-17 tracer PET-CT (fictional)";
const EVENT_LABEL = { prepared: "Prepared", opened: "Opened by you", reopened: "Reopened by you", returned: "Returned by you", released: "Released by you", closed: "Closed by you" } as const;

export function plainText(rec: CaseRecord, packet: Packet, state: CaseState): string {
  const evidence = new Map(packet.evidence.map((e) => [e.id, e.text]));
  const lines = [
    "PET-CT request packet (demo)", STRIP_TEXT, "",
    `Insurer (fictional): ${rec.insurer}`, `Request code (fictional): ${rec.request_code}`, `Patient: ${rec.patient_id}`, `Requested study: ${STUDY}`, "",
  ];
  for (const c of packet.criteria) {
    lines.push(`${c.id} ${c.status.toUpperCase()}: ${c.text}`);
    for (const id of c.cites) lines.push(`  - ${evidence.get(id) ?? id}`);
  }
  lines.push("", "Still missing:", ...(packet.gaps.length ? packet.gaps.map((g) => `  - ${g.prompt}`) : ["  - nothing"]));
  lines.push("", "Summary:", ...packet.summary.map((s) => `  ${s.text}`));
  if (state.rationale) lines.push("", "Supervisor's rationale (their own words):", state.rationale);
  lines.push("", "Audit trail:", ...state.events.map((e) => `  ${clock(e.at)} ${e.text ?? EVENT_LABEL[e.kind]}`), "", packet.disclaimer);
  return lines.join("\n");
}

/** The packet as it would go to the insurer: a cover sheet, the checklist with its evidence, the summary and the audit trail. */
export function ReleasedPacket({ rec, packet, state }: { rec: CaseRecord; packet: Packet; state: CaseState }) {
  const evidence = new Map(packet.evidence.map((e) => [e.id, e.text]));
  const released = state.events.find((e) => e.kind === "released");
  const rows: [string, string][] = [
    ["Insurer (fictional)", rec.insurer], ["Request code (fictional)", rec.request_code], ["Patient", rec.patient_id], ["Requested study", STUDY],
    ["Prepared by", `${rec.preparer} (simulated)`], ["Released by", `You, neurology supervisor (demo), ${released ? clock(released.at) : ""}`],
  ];
  return (
    <Box data-testid="released-packet" className="print-area">
      <Paper data-testid="cover-sheet" sx={{ p: 3, mb: 2 }}>
        <Typography variant="h2" component="h2" sx={{ mb: 1.5 }}>Prior authorization request: cover sheet</Typography>
        <Box component="dl" sx={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px", m: 0 }}>
          {rows.map(([k, v]) => (<Box key={k} sx={{ display: "contents" }}><Typography component="dt" color="text.secondary">{k}</Typography><Typography component="dd" sx={{ m: 0, fontWeight: 600 }}>{v}</Typography></Box>))}
        </Box>
        <Box className="no-print"><DemoNote note="cover" /></Box>
      </Paper>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Criteria and evidence</Typography>
        <Table size="small" aria-label="Criteria and evidence">
          <TableHead><TableRow><TableCell>Criterion</TableCell><TableCell>Status</TableCell><TableCell>Evidence</TableCell></TableRow></TableHead>
          <TableBody>
            {packet.criteria.map((c) => (
              <TableRow key={c.id}>
                <TableCell><strong>{c.id}</strong> {c.text}</TableCell>
                <TableCell><CriterionChip status={c.status} /></TableCell>
                <TableCell>{c.cites.map((id) => <Typography key={id} variant="body2">{evidence.get(id) ?? id}</Typography>)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Typography variant="h3" component="h3" sx={{ mt: 2, mb: 0.5 }}>Still missing</Typography>
        <Typography variant="body2">{packet.gaps.length ? packet.gaps.map((g) => g.prompt).join(" ") : "Nothing is missing."}</Typography>
        <Typography variant="h3" component="h3" sx={{ mt: 2, mb: 0.5 }}>Summary</Typography>
        {packet.summary.map((s) => <Typography key={s.criterion} variant="body2" sx={{ mb: 0.5 }}>{s.text}</Typography>)}
        {state.rationale && (
          <>
            <Typography variant="h3" component="h3" sx={{ mt: 2, mb: 0.5 }}>Supervisor&apos;s rationale</Typography>
            <Typography variant="caption" color="text.secondary">In the supervisor&apos;s own words; not written by the tool.</Typography>
            <Typography data-testid="released-rationale" sx={{ whiteSpace: "pre-wrap" }}>{state.rationale}</Typography>
          </>
        )}
      </Paper>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Audit trail</Typography>
        <Box component="ol" data-testid="audit-timeline" sx={{ m: 0, pl: 2.5 }}>
          {state.events.map((e, i) => (<li key={i}><Typography variant="body2"><strong>{clock(e.at)}</strong> {e.text ?? EVENT_LABEL[e.kind]}</Typography></li>))}
        </Box>
        <Divider sx={{ my: 1.5 }} />
        <Box className="no-print"><DemoNote note="next" /></Box>
        <Typography variant="caption" color="text.secondary" data-testid="print-notice">{STRIP_TEXT} {packet.disclaimer}</Typography>
      </Paper>
      <Row spacing={1} className="no-print">
        <Button variant="outlined" data-track="packet_copy" onClick={() => navigator.clipboard?.writeText(plainText(rec, packet, state))}>Copy</Button>
        <Button variant="contained" data-track="packet_print" onClick={() => window.print()}>Print</Button>
      </Row>
    </Box>
  );
}
