"use client";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import content from "@/content/estimate.json";
import { ESTIMATE_PARAGRAPHS, ESTIMATE_TITLE, FREE_TEXT_CLOSE, FREE_TEXT_OPEN } from "@/lib/copy";
import type { EstimateContent } from "@/lib/types";
import { AssistantPanel, type AssistantResult, type Sent } from "./AssistantPanel";
import { EstimateControls, EstimateResult } from "./EstimatePanel";
import { FreeTextTab } from "./FreeTextTab";
import type { Outcome } from "./ReportCard";
import { useEstimate } from "./useEstimate";

const CONTENT = content as unknown as EstimateContent;

function Chevron() {
  return <span aria-hidden="true">▾</span>;
}

/** The second scenario: an invented patient whose labs and symptoms the visitor sets, the model's estimate for them, and the assistant's checks on that patient. */
export function EstimateView({ onSend, result, labNames }: { onSend: (message: string, sent: Sent) => void; result: AssistantResult; labNames: Record<string, string> }) {
  const [typing, setTyping] = useState(false);
  const est = useEstimate(CONTENT);
  const freeOutcome: Outcome = result.sent?.source === "free" ? result.outcome : { kind: "idle" };
  return (
    <>
      <Paper component="section" aria-labelledby="estimate-title" data-testid="estimate-intro" sx={{ p: 3, mb: 3, bgcolor: "#EAF3F3" }}>
        <Typography id="estimate-title" variant="h2" component="h2" sx={{ mb: 1.5 }}>{ESTIMATE_TITLE}</Typography>
        {ESTIMATE_PARAGRAPHS.map((p, i) => <Typography key={i} variant="body1" sx={{ mb: 1.25 }}>{p}</Typography>)}
      </Paper>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start", mb: 3 }}>
        <EstimateControls content={CONTENT} api={est} />
        <EstimateResult content={CONTENT} estimate={est.estimate} inputs={est.inputs} status={est.status} error={est.error} />
      </Box>
      <AssistantPanel message={est.estimate.message} dial={est.estimate.probability} ready={est.status === "idle"} result={result} labNames={labNames} onSend={onSend} />
      <Accordion disableGutters elevation={0} expanded={typing} onChange={(_, open) => setTyping(open)} slotProps={{ transition: { unmountOnExit: true } }} sx={{ "&:before": { display: "none" } }}>
        <AccordionSummary aria-controls="free-text-body" id="free-text-head" expandIcon={<Chevron />} sx={{ bgcolor: "#F4F8F8", fontWeight: 600, color: "primary.main" }}>
          {typing ? FREE_TEXT_CLOSE : FREE_TEXT_OPEN}
        </AccordionSummary>
        <AccordionDetails id="free-text-body">
          <FreeTextTab onSend={(text) => onSend(text, { source: "free" })} outcome={freeOutcome} labNames={labNames} />
        </AccordionDetails>
      </Accordion>
    </>
  );
}
