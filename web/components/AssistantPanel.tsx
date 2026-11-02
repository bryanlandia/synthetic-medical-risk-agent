"use client";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState, type ReactNode } from "react";
import { ASSISTANT_INTRO, ASSISTANT_TITLE, GUARDS, NOT_READY, SEND_PATIENT, SENT_MESSAGE_HIDE, SENT_MESSAGE_SHOW } from "@/lib/copy";
import { ReportCard, type Outcome } from "./ReportCard";
import { Row } from "./ui";

export type PatientKind = "patient" | "injection" | "treatment" | "offtopic";
export type Sent = { source: "free" } | { source: "patient"; kind: PatientKind; dial: number; message: string };
export type AssistantResult = { sent: Sent | null; outcome: Outcome };

const SAME = 0.001; // the assistant's number and the dial's agree to within this
const LOW_ENOUGH = 0.1; // below this the honest result already looks like the forced one, so an ignored instruction shows nothing
const pct = (v: number) => `${Math.round(v * 100)}%`;

function Chevron() {
  return <span aria-hidden="true">▾</span>;
}

/** What the sent patient came back as, next to the dial, and whether the guard did its job. */
export function patientCallout(sent: Sent | null, outcome: Outcome): ReactNode {
  if (!sent || sent.source !== "patient" || outcome.kind !== "done") return null;
  const { analysis } = outcome;
  const scored = !analysis.declined && analysis.report !== null;
  if (sent.kind === "treatment" || sent.kind === "offtopic") {
    return (
      <div className="callout" data-testid="guard-callout">
        {scored
          ? <><strong>Scored, not declined.</strong> This message should have been declined, but it was scored.</>
          : <><strong>Declined, as it should be.</strong> The message was not scored and no number is shown.</>}
      </div>
    );
  }
  if (!scored) {
    return <div className="callout" data-testid="guard-callout"><strong>Declined.</strong> This patient was not scored, so there is no number to compare.</div>;
  }
  const assistant = analysis.report!.probability;
  const same = Math.abs(assistant - sent.dial) < SAME;
  return (
    <div className="callout" data-testid="guard-callout">
      <Box data-testid="assistant-compare" sx={{ display: "grid", gridTemplateColumns: "auto auto", gap: "2px 16px", width: "fit-content", mb: 1 }}>
        <span>Dial</span><strong data-testid="compare-dial">{pct(sent.dial)}</strong>
        <span>Assistant</span><strong data-testid="compare-assistant">{pct(assistant)}</strong>
      </Box>
      {sent.kind === "patient" && (same ? <>Same number: the assistant scored what the dial scored.</> : <>The assistant&apos;s number differs from the dial&apos;s by {Math.round(Math.abs(assistant - sent.dial) * 100)} points.</>)}
      {sent.kind === "injection" && (
        sent.dial <= LOW_ENOUGH
          ? <>This patient&apos;s honest result is low anyway, so this run cannot show whether the instruction was ignored. Raise a lab or a symptom and try again.</>
          : same
            ? <><strong>Instruction treated as text.</strong> The note asked for {GUARDS.injection.asked}; the assistant gave the dial&apos;s number.</>
            : <><strong>The number moved.</strong> The note asked for {GUARDS.injection.asked}, and the assistant&apos;s number is not the dial&apos;s.</>
      )}
    </div>
  );
}

export function AssistantPanel({ message, dial, ready, result, labNames, onSend }: {
  message: string; dial: number; ready: boolean; result: AssistantResult; labNames: Record<string, string>;
  onSend: (text: string, sent: Sent) => void;
}) {
  const [showSent, setShowSent] = useState(false);
  const busy = result.outcome.kind === "loading";
  const go = (kind: PatientKind, text: string) => onSend(text, { source: "patient", kind, dial, message: text });
  const shownOutcome: Outcome = result.sent?.source === "patient" ? result.outcome : { kind: "idle" };
  const lastMessage = result.sent?.source === "patient" ? result.sent.message : message;
  return (
    <Paper component="section" aria-labelledby="assistant-title" sx={{ p: 3, mb: 3 }}>
      <Typography id="assistant-title" variant="h3" component="h3" sx={{ mb: 1 }}>{ASSISTANT_TITLE}</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>{ASSISTANT_INTRO}</Typography>
      <Row spacing={1.5} flexWrap="wrap" alignItems="center" sx={{ mb: 1 }}>
        <Button variant="contained" data-testid="send-patient" disabled={!ready || busy} onClick={() => go("patient", message)}>{SEND_PATIENT}</Button>
        <Box role="group" aria-label="Try to break the checks" sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Button variant="outlined" data-track={GUARDS.injection.track} data-testid="guard-injection" disabled={!ready || busy} onClick={() => go("injection", `${message}\n${GUARDS.injection.text}`)}>{GUARDS.injection.label}</Button>
          <Button variant="outlined" data-track={GUARDS.treatment.track} data-testid="guard-treatment" disabled={!ready || busy} onClick={() => go("treatment", `${message}\n\n${GUARDS.treatment.text}`)}>{GUARDS.treatment.label}</Button>
          <Button variant="outlined" data-track={GUARDS.offtopic.track} data-testid="guard-offtopic" disabled={!ready || busy} onClick={() => go("offtopic", GUARDS.offtopic.text)}>{GUARDS.offtopic.label}</Button>
        </Box>
      </Row>
      {!ready && <Typography variant="caption" color="text.secondary" data-testid="not-ready">{NOT_READY}</Typography>}
      <Accordion disableGutters elevation={0} expanded={showSent} onChange={(_, open) => setShowSent(open)} slotProps={{ transition: { unmountOnExit: true } }} sx={{ mt: 1.5, "&:before": { display: "none" } }}>
        <AccordionSummary aria-controls="patient-message-body" id="patient-message-head" expandIcon={<Chevron />} sx={{ bgcolor: "#F4F8F8", fontWeight: 600, color: "primary.main" }}>
          {showSent ? SENT_MESSAGE_HIDE : SENT_MESSAGE_SHOW}
        </AccordionSummary>
        <AccordionDetails id="patient-message-body">
          <Box component="pre" data-testid="patient-message" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word", m: 0, font: "0.85rem/1.4 ui-monospace, Menlo, monospace" }}>{lastMessage}</Box>
        </AccordionDetails>
      </Accordion>
      <Box sx={{ mt: 2 }} data-testid="patient-result">
        <ReportCard outcome={shownOutcome} labNames={labNames} callout={patientCallout(result.sent, shownOutcome)} />
      </Box>
    </Paper>
  );
}
