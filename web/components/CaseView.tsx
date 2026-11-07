"use client";

import Alert from "@mui/material/Alert";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useRef, useState } from "react";
import policy from "@/content/pet_ct_policy.json";
import { criterionText, formatReceived } from "@/lib/copy";
import { requestPacket } from "@/lib/packet-client";
import { MIN_NOTE, MIN_RATIONALE, releaseBlock, statusOf } from "@/lib/store";
import type { Answer, AttestedId, CaseRecord, Packet, ShownError } from "@/lib/types";
import { HelpButton, ProducedKeyButton } from "./Intro";
import { RiskFigure } from "./RiskFigure";
import { ReleasedPacket } from "./ReleasedPacket";
import { useReview } from "./ReviewProvider";
import { CriterionChip, DemoNote, Produced, Row, SourceCell, StatusChip, Term } from "./ui";

const SOURCE_OF = Object.fromEntries(policy.criteria.map((c) => [c.id, c.source])) as Record<string, string>;
const WORDING = Object.fromEntries(policy.criteria.map((c) => [c.id, criterionText(c.id, c.text)])) as Record<string, string>;
const ANSWERS: AttestedId[] = ["C3", "C4", "C5", "C6"];
const ANSWER_LABEL: Record<Answer, string> = { yes: "Yes", no: "No", unanswered: "Not yet answered" };
const pct = (v: number) => `${Math.round(v * 100)}%`;

/** A small inline chevron for the disclosure (no icon package). */
function Chevron() {
  return <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 10l5 5 5-5z" fill="currentColor" /></svg>;
}

function Chart({ rec }: { rec: CaseRecord }) {
  const [showSent, setShowSent] = useState(false);
  return (
    <Paper component="section" aria-label="Patient chart" data-testid="chart" sx={{ p: 2.5 }}>
      <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Chart for {rec.patient_id}</Typography>
      <Table size="small" aria-label="Labs on the chart">
        <TableHead><TableRow><TableCell>Lab</TableCell><TableCell>Value</TableCell><TableCell>Unit</TableCell><TableCell>Reference range</TableCell></TableRow></TableHead>
        <TableBody>
          {rec.chart.labs.map((l) => (
            <TableRow key={l.lab}>
              <TableCell>{l.name} ({l.abbr})</TableCell>
              <TableCell>{l.value === null ? <Typography component="span" color="text.secondary">not reported</Typography> : l.value}</TableCell>
              <TableCell>{l.value === null ? "" : l.unit}</TableCell>
              <TableCell data-testid={`range-${l.lab}`}>
                {l.ref_lo}–{l.ref_hi} {l.ref_unit}
                {l.flag && <Chip size="small" label={l.flag === "H" ? "H (high)" : "L (low)"} data-testid={`flag-${l.lab}`} sx={{ ml: 1, bgcolor: "#FFE7B0", color: "#5C4300", height: 22 }} />}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Typography variant="h4" component="h4" sx={{ mt: 2, mb: 0.5 }}>Clinical note</Typography>
      <Box component="pre" data-testid="note" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word", bgcolor: "#F4F8F8", border: "1px solid #C4CBCB", borderRadius: 2, p: 1.5, m: 0, font: "0.88rem/1.45 ui-monospace, Menlo, monospace" }}>{rec.chart.note}</Box>
      <Accordion disableGutters elevation={0} expanded={showSent} onChange={(_, open) => setShowSent(open)} sx={{ mt: 1.5, "&:before": { display: "none" } }}>
        <AccordionSummary data-track="sent_message_expander" aria-controls="sent-message-body" id="sent-message-head" expandIcon={<Chevron />} sx={{ bgcolor: "#F4F8F8", fontWeight: 600, color: "primary.main" }}>
          {showSent ? "Hide the message sent to the service" : "Show the message sent to the service"}
        </AccordionSummary>
        <AccordionDetails id="sent-message-body">
          <Typography variant="caption" color="text.secondary">The check sends exactly this text, built from the chart&apos;s labs and note, and the four preparer answers. Nothing else.</Typography>
          <Box component="pre" data-testid="sent-message" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word", m: 0, mt: 0.5, font: "0.85rem/1.4 ui-monospace, Menlo, monospace" }}>{rec.message}</Box>
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
}

function PreparerAnswers({ rec }: { rec: CaseRecord }) {
  return (
    <Box data-testid="answers" sx={{ mb: 2 }}>
      <Typography variant="h4" component="h4">Answers entered by the preparing clinician ({rec.preparer}, simulated)<Produced kind="preparer" testId="answers" /></Typography>
      <Table size="small" aria-label="Preparer answers">
        <TableBody>
          {ANSWERS.map((id) => (
            <TableRow key={id}><TableCell><strong>{id}</strong> {WORDING[id]}</TableCell><TableCell data-testid={`answer-${id}`}>{ANSWER_LABEL[rec.answers[id]]}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function Checklist({ packet }: { packet: Packet }) {
  const evidence = new Map(packet.evidence.map((e) => [e.id, e.text]));
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="h4" component="h4">Checklist against the insurer&apos;s coverage criteria<Produced kind="rules" testId="checklist" /></Typography>
      <DemoNote note="policy" />
      <Table size="small" aria-label="Criteria" data-testid="packet-checklist">
        <TableHead><TableRow><TableCell>Criterion</TableCell><TableCell>Source</TableCell><TableCell>Status</TableCell><TableCell>Evidence</TableCell></TableRow></TableHead>
        <TableBody>
          {packet.criteria.map((c) => (
            <TableRow key={c.id} data-testid={`criterion-${c.id}`}>
              <TableCell><strong>{c.id}</strong> {criterionText(c.id, c.text)}</TableCell>
              <SourceCell source={SOURCE_OF[c.id]} testId={c.id} />
              <TableCell><CriterionChip status={c.status} testId={`crit-status-${c.id}`} /></TableCell>
              <TableCell>{c.cites.map((id) => <Typography key={id} variant="body2">{evidence.get(id) ?? id}</Typography>)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Typography variant="h4" component="h4" sx={{ mt: 1.5 }}>Still missing</Typography>
      <Box component="ul" data-testid="packet-gaps" sx={{ my: 0.5, pl: 2.5 }}>
        {packet.gaps.length ? packet.gaps.map((g) => <li key={g.criterion}><Typography variant="body2">{g.prompt}</Typography></li>) : <li><Typography variant="body2">Nothing is missing.</Typography></li>}
      </Box>
    </Box>
  );
}

function PacketBody({ rec, packet }: { rec: CaseRecord; packet: Packet }) {
  const r = packet.report;
  return (
    <>
      {r && (
        <Box sx={{ mb: 2 }} data-testid="estimate">
          <Typography variant="h4" component="h4">Why this patient was flagged (context only)<Produced kind="classifier" testId="estimate" /></Typography>
          <RiskFigure probability={r.probability} testId="estimate-figure" />
          <Typography variant="body2">
            {r.interval ? `The range is ${pct(r.interval[0])} to ${pct(r.interval[1])} if the missing results are obtained. ` : ""}Context only; it decides no criterion.
          </Typography>
          <DemoNote note="estimate" />
        </Box>
      )}
      <PreparerAnswers rec={rec} />
      <Checklist packet={packet} />
      <Typography variant="h4" component="h4">Summary<Produced kind={packet.summary_source === "model" ? "llm" : "template"} testId="summary" /></Typography>
      <Typography variant="caption" color="text.secondary" data-testid="summary-source">
        {packet.summary_source === "model"
          ? "Drafted by the language model; every sentence was checked by code against the table and its evidence."
          : "Written from a fixed template: the model's draft did not pass the checks, or the model was unavailable."}
      </Typography>
      <DemoNote note="summary" />
      <Box component="ul" data-testid="packet-summary" sx={{ my: 0.5, pl: 2.5 }}>{packet.summary.map((s) => <li key={s.criterion}><Typography variant="body2">{s.text}</Typography></li>)}</Box>
    </>
  );
}

type Dlg = null | "release" | "return" | "close";

export function CaseView({ rec, onBack }: { rec: CaseRecord; onBack: () => void }) {
  const { saved, dispatch, hydrated } = useReview();
  const state = saved.cases[rec.id];
  const status = statusOf(saved, rec.id);
  const packet = state?.packet;
  const [error, setError] = useState<ShownError | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [rationale, setRationale] = useState("");
  const [note, setNote] = useState("");
  const [dlg, setDlg] = useState<Dlg>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    if (hydrated && statusOf(saved, rec.id) === "new") {
      dispatch({ type: "open", id: rec.id, at: new Date().toISOString(), preparedAt: rec.received, preparer: rec.preparer });
    }
    // opening happens once per visit to the case
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, rec.id]);

  useEffect(() => {
    if (!hydrated || packet || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    requestPacket(rec.message, rec.answers).then((result) => {
      inFlight.current = false;
      setLoading(false);
      if (result.kind === "done") dispatch({ type: "packet", id: rec.id, packet: result.packet });
      else setError(result.error);
    });
    // a retry bumps `attempt`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, rec.id, packet, attempt]);

  const live = packet && !packet.declined ? packet : null;
  const block = releaseBlock(packet, rationale);
  const hasUnknown = live ? live.criteria.some((c) => c.status === "unknown") : false;
  const hasUnmet = live ? live.criteria.some((c) => c.status === "unmet") : false;
  const now = () => new Date().toISOString();
  const noteOk = note.trim().length >= MIN_NOTE;

  if (status === "released" && live && state) {
    return (
      <Box component="section" aria-label="Released packet">
        <Row spacing={1.5} alignItems="center" className="no-print" sx={{ mb: 2 }}>
          <Button onClick={onBack}>Back to the queue</Button>
          <Typography variant="h2" component="h2" data-testid="case-title">{rec.request_code}</Typography>
          <StatusChip status={status} testId="case-status" />
          <Box sx={{ flexGrow: 1 }} /><HelpButton />
        </Row>
        <ReleasedPacket rec={rec} packet={live} state={state} />
      </Box>
    );
  }

  return (
    <Box component="section" aria-label={`Case ${rec.request_code}`}>
      <Row spacing={1.5} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <Button onClick={onBack}>Back to the queue</Button>
        <Typography variant="h2" component="h2" data-testid="case-title">{rec.request_code}</Typography>
        <StatusChip status={status} testId="case-status" />
        <Typography variant="body2" color="text.secondary">{rec.insurer} (fictional) · received {formatReceived(rec.received)}</Typography>
        <Box sx={{ flexGrow: 1 }} /><ProducedKeyButton /><HelpButton />
      </Row>
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,5fr) minmax(0,6fr)" }, alignItems: "start" }}>
        <Chart rec={rec} />
        <Paper component="section" aria-label="Request packet" sx={{ p: 2.5 }}>
          <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Request <Term term="packet" /> for a <Term term="PET-CT" /> scan</Typography>
          {loading && <Row spacing={1} alignItems="center" aria-live="polite"><CircularProgress size={18} /><Typography>Checking the chart against the criteria…</Typography></Row>}
          {error && (
            <Alert severity="error" data-testid="packet-error" action={<Button color="inherit" size="small" onClick={() => setAttempt((n) => n + 1)}>Try again</Button>}>{error.message}</Alert>
          )}
          {packet?.declined && <Alert severity="warning" data-testid="packet-declined">{packet.message}</Alert>}
          {live && <PacketBody rec={rec} packet={live} />}
          {status === "returned" && state?.note && (
            <Box data-testid="return-note-shown" sx={{ mt: 2 }}>
              <Alert severity="info">Returned to {rec.preparer} (pretend) with your note: <Box component="span" sx={{ whiteSpace: "pre-wrap" }}>{state.note}</Box></Alert>
              <DemoNote note="returnNote" />
              <Button sx={{ mt: 1 }} variant="outlined" data-track="confirm" onClick={() => dispatch({ type: "reopen", id: rec.id, at: now() })}>Reopen this request</Button>
            </Box>
          )}
          {status === "closed" && <Alert severity="info" sx={{ mt: 2 }} data-testid="closed-note">Closed: the criteria are not met. Nothing was sent.</Alert>}
          {status === "in-review" && live && (
            <Box sx={{ mt: 2, pt: 2, borderTop: "1px solid #C4CBCB" }} data-testid="decision-bar">
              <Typography variant="h4" component="h4" sx={{ mb: 1 }}>Your decision<Produced kind="you" testId="decision" /></Typography>
              {hasUnmet && !hasUnknown && (
                <>
                  <TextField label="Your rationale, in your own words" multiline minRows={3} fullWidth value={rationale} onChange={(e) => setRationale(e.target.value)}
                    helperText={`Needed to release with an unmet criterion (at least ${MIN_RATIONALE} characters).`} slotProps={{ htmlInput: { "data-testid": "rationale" } }} />
                  <DemoNote note="rationale" />
                </>
              )}
              {block && <Alert severity="info" sx={{ my: 1 }} data-testid="release-block">{block}</Alert>}
              <Row spacing={1} sx={{ mt: 1 }} flexWrap="wrap">
                <Button variant="contained" data-track="release" disabled={block !== null} onClick={() => setDlg("release")}>Release</Button>
                <Button variant="outlined" data-track="return" onClick={() => setDlg("return")}>Return with a note</Button>
                <Button variant="outlined" color="inherit" data-track="close" onClick={() => setDlg("close")}>Close, criteria not met</Button>
              </Row>
            </Box>
          )}
        </Paper>
      </Box>

      <Dialog open={dlg === "release"} onClose={() => setDlg(null)} aria-labelledby="release-title">
        <DialogTitle id="release-title">Release this request?</DialogTitle>
        <DialogContent>
          <DialogContentText>This marks the packet as ready to send to {rec.insurer} (fictional). Nothing is transmitted.</DialogContentText>
          <DemoNote note="release" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlg(null)} autoFocus>Cancel</Button>
          <Button variant="contained" data-track="confirm" onClick={() => { dispatch({ type: "release", id: rec.id, at: now(), rationale }); setDlg(null); }}>Release</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={dlg === "return"} onClose={() => setDlg(null)} aria-labelledby="return-title" fullWidth maxWidth="sm">
        <DialogTitle id="return-title">Return with a note</DialogTitle>
        <DialogContent>
          <TextField autoFocus label="Your note to the preparing clinician" multiline minRows={3} fullWidth margin="dense" value={note} onChange={(e) => setNote(e.target.value)}
            helperText={`At least ${MIN_NOTE} characters, in your own words.`} slotProps={{ htmlInput: { "data-testid": "return-note" } }} />
          <DemoNote note="returnNote" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDlg(null)}>Cancel</Button>
          <Button variant="contained" disabled={!noteOk} data-track="confirm" onClick={() => { dispatch({ type: "return", id: rec.id, at: now(), note }); setDlg(null); }}>Return</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={dlg === "close"} onClose={() => setDlg(null)} aria-labelledby="close-title">
        <DialogTitle id="close-title">Close this request?</DialogTitle>
        <DialogContent><DialogContentText>The criteria are not met, so no packet goes to the insurer. Nothing is transmitted.</DialogContentText></DialogContent>
        <DialogActions>
          <Button onClick={() => setDlg(null)} autoFocus>Cancel</Button>
          <Button variant="contained" data-track="confirm" onClick={() => { dispatch({ type: "close", id: rec.id, at: now() }); setDlg(null); }}>Close request</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
