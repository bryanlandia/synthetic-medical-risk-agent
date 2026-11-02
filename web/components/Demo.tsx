"use client";

import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";
import { AboutTab } from "./AboutTab";
import { trackResult } from "./Analytics";
import { CaseView } from "./CaseView";
import type { AssistantResult, Sent } from "./AssistantPanel";
import { EstimateView } from "./EstimateView";
import { ModelCardTab } from "./ModelCardTab";
import { QueueView } from "./QueueView";
import type { Outcome } from "./ReportCard";
import { ReviewProvider } from "./ReviewProvider";
import { DemoStrip, Row } from "./ui";
import { SUBTITLES } from "@/lib/copy";
import type { Analysis, CasesFile, ShownError } from "@/lib/types";

type View = { name: "queue" } | { name: "case"; id: string } | { name: "estimate" | "card" | "about" };
const BEHIND: { id: "card" | "about"; label: string; title: string }[] = [
  { id: "card", label: "Model card", title: "Model card" },
  { id: "about", label: "About this project", title: "About this project" },
];

/** One message in, one result out. Nothing is kept between sends: a new result replaces the last. */
async function send(message: string): Promise<Outcome> {
  try {
    const response = await fetch("/api/analyze", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message }) });
    const body = (await response.json()) as { analysis?: Analysis; error?: ShownError };
    if (response.ok && body.analysis) return { kind: "done", analysis: body.analysis };
    return { kind: "error", error: body.error ?? { code: "error", message: "Something went wrong. Please try again." } };
  } catch {
    return { kind: "error", error: { code: "network", message: "Could not reach the demo. Please check your connection and try again." } };
  }
}

const kindOf = (outcome: Outcome): string => (outcome.kind === "done" ? (outcome.analysis.declined ? "declined" : "scored") : "error");

export function Demo({ cases, cardBody, cardHash, about }: { cases: CasesFile; cardBody: string; cardHash: string | null; about: string }) {
  const [view, setView] = useState<View>({ name: "queue" });
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [result, setResult] = useState<AssistantResult>({ sent: null, outcome: { kind: "idle" } });
  const labNames = useMemo(() => Object.fromEntries(cases.cases[0].chart.labs.map((l) => [l.lab, l.name])), [cases]);
  const behind = BEHIND.find((b) => b.id === view.name);
  useEffect(() => { if (view.name !== "estimate") setResult({ sent: null, outcome: { kind: "idle" } }); }, [view.name]); // an answer is about the patient it was sent for

  /** One message in, one result out: the newest result replaces the last, whichever box it came from. */
  async function runSend(message: string, sent: Sent) {
    setResult({ sent, outcome: { kind: "loading" } });
    const outcome = await send(message);
    trackResult("free_text", kindOf(outcome));
    setResult({ sent, outcome });
  }

  return (
    <ReviewProvider casesHash={cases.cases_hash}>
      <DemoStrip />
      <AppBar position="static" color="inherit" className="no-print" sx={{ borderBottom: "1px solid #C4CBCB", boxShadow: "none" }}>
        <Toolbar sx={{ gap: 2, flexWrap: "wrap", py: 1 }}>
          <Box component="img" src="/vk-check-logo.svg" alt="" sx={{ height: 36, width: "auto" }} />
          <Box sx={{ flexGrow: 1, minWidth: 260 }}>
            <Typography variant="h1" component="h1">
              VK-Check<span data-testid="scenario-subtitle">: {SUBTITLES[view.name]}</span>
            </Typography>
            <Typography variant="body2" color="text.secondary">Decision support for Velorin-Kessler Syndrome diagnosis (fictional disease)</Typography>
          </Box>
          <Row spacing={1} component="nav" aria-label="Main">
            <Button data-track="nav:queue" variant={view.name === "queue" || view.name === "case" ? "contained" : "text"} onClick={() => setView({ name: "queue" })}>Review queue</Button>
            <Button data-track="nav:estimate" variant={view.name === "estimate" ? "contained" : "text"} onClick={() => setView({ name: "estimate" })}>Estimate a risk</Button>
            <Button data-track="menu:behind" variant={behind ? "contained" : "text"} aria-haspopup="menu" aria-expanded={Boolean(anchor)} onClick={(e) => setAnchor(e.currentTarget)}>Behind the demo</Button>
          </Row>
          <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
            {BEHIND.map((b) => (
              <MenuItem key={b.id} data-track={`nav:${b.id}`} selected={view.name === b.id} onClick={() => { setView({ name: b.id }); setAnchor(null); }}>{b.label}</MenuItem>
            ))}
          </Menu>
        </Toolbar>
      </AppBar>
      <Container component="main" maxWidth="xl" sx={{ py: 3 }}>
        {view.name === "queue" && <QueueView cases={cases.cases} onOpen={(id) => setView({ name: "case", id })} />}
        {view.name === "case" && <CaseView key={view.id} rec={cases.cases.find((c) => c.id === view.id)!} onBack={() => setView({ name: "queue" })} />}
        {view.name === "estimate" && <EstimateView onSend={runSend} result={result} labNames={labNames} />}
        {behind && (
          <Box component="section" aria-label={behind.title}>
            <Row spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
              <Button onClick={() => setView({ name: "queue" })}>Back to the queue</Button>
              <Typography variant="h2" component="h2">Behind the demo: {behind.title}</Typography>
            </Row>
            {view.name === "card" && <ModelCardTab body={cardBody} hash={cardHash} />}
            {view.name === "about" && <AboutTab body={about} />}
          </Box>
        )}
      </Container>
    </ReviewProvider>
  );
}
