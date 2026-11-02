"use client";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { STATUS_FILTERS } from "@/lib/analytics";
import { statusOf } from "@/lib/store";
import { STATUS_CHIPS, type StatusKey } from "@/lib/theme";
import type { CaseRecord } from "@/lib/types";
import { IntroCard, ProducedKeyButton } from "./Intro";
import { useReview } from "./ReviewProvider";
import { formatReceived } from "@/lib/copy";
import { DemoNote, Row, StatusChip, Term } from "./ui";

const FILTER_LABEL: Record<(typeof STATUS_FILTERS)[number], string> = { all: "All", ...Object.fromEntries(Object.entries(STATUS_CHIPS).map(([k, v]) => [k, v.label])) } as never;

const flags = (c: CaseRecord) => c.chart.labs.filter((l) => l.flag).length;
const answered = (c: CaseRecord) => Object.values(c.answers).filter((a) => a !== "unanswered").length;
const firstLine = (c: CaseRecord) => c.chart.note.split("\n").find((l) => l.trim())?.trim() ?? "";

export function QueueView({ cases, onOpen }: { cases: CaseRecord[]; onOpen: (id: string) => void }) {
  const { saved, dispatch, casesHash, policyId } = useReview();
  const [filter, setFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [confirmReset, setConfirmReset] = useState(false);
  const shown = cases.filter((c) => filter === "all" || statusOf(saved, c.id) === filter);
  const count = (s: StatusKey) => cases.filter((c) => statusOf(saved, c.id) === s).length;

  return (
    <Box component="section" aria-label="Review queue">
      <IntroCard />
      <Row alignItems="baseline" justifyContent="space-between" flexWrap="wrap" spacing={1} sx={{ mb: 1 }}>
        <Typography variant="h2" component="h2">Requests waiting for review</Typography>
        <Typography variant="body2" color="text.secondary" data-testid="queue-counts">
          {cases.length} requests · {count("new")} new · {count("in-review")} in review · {count("returned")} returned · {count("released")} released · {count("closed")} closed
        </Typography>
        <ProducedKeyButton />
      </Row>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
        Each request is a <Term term="packet" /> for a <Term term="PET-CT" /> scan, prepared by a clinician for an insurer.
      </Typography>
      <DemoNote note="role" />
      <Row spacing={1} role="group" aria-label="Filter by status" flexWrap="wrap" sx={{ my: 1.5 }}>
        {STATUS_FILTERS.map((f) => (
          <Chip key={f} label={FILTER_LABEL[f]} clickable data-track={`filter:${f}`} aria-pressed={filter === f} variant={filter === f ? "filled" : "outlined"}
            color={filter === f ? "primary" : "default"} onClick={() => setFilter(f)} />
        ))}
      </Row>
      <TableContainer component={Paper}>
        <Table size="small" aria-label="Requests" data-testid="queue">
          <TableHead>
            <TableRow>
              <TableCell>Request</TableCell><TableCell>Patient</TableCell><TableCell>Insurer (fictional)</TableCell><TableCell>Prepared by</TableCell>
              <TableCell>Received</TableCell><TableCell align="right">Lab flags</TableCell><TableCell>Preparer answers</TableCell><TableCell>First line of the note</TableCell><TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((c) => (
              <TableRow key={c.id} hover data-testid={`row-${c.ordinal}`}>
                <TableCell>
                  <Button size="small" data-track={`case:${c.ordinal}`} onClick={() => onOpen(c.id)} sx={{ fontWeight: 700 }}>{c.request_code}</Button>
                </TableCell>
                <TableCell>{c.patient_id}</TableCell>
                <TableCell>{c.insurer}</TableCell>
                <TableCell>{c.preparer}</TableCell>
                <TableCell>{formatReceived(c.received)}</TableCell>
                <TableCell align="right">{flags(c)}</TableCell>
                <TableCell>{answered(c)} of 4 answered</TableCell>
                <TableCell sx={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={firstLine(c)}>{firstLine(c)}</TableCell>
                <TableCell><StatusChip status={statusOf(saved, c.id)} testId={`chip-${c.ordinal}`} /></TableCell>
              </TableRow>
            ))}
            {shown.length === 0 && <TableRow><TableCell colSpan={9}><Typography color="text.secondary">No requests with this status.</Typography></TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ mt: 1.5 }}>
        <DemoNote note="queue" />
        <DemoNote note="storage" />
        <Button size="small" variant="outlined" data-track="reset_demo" onClick={() => setConfirmReset(true)}>Reset demo</Button>
      </Box>
      <Dialog open={confirmReset} onClose={() => setConfirmReset(false)} aria-labelledby="reset-title">
        <DialogTitle id="reset-title">Reset the demo?</DialogTitle>
        <DialogContent><DialogContentText>This clears everything saved in this browser (statuses, notes, rationales) and restores all {cases.length} requests to New.</DialogContentText></DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmReset(false)} autoFocus>Cancel</Button>
          <Button color="primary" variant="contained" data-track="confirm" onClick={() => { dispatch({ type: "reset", casesHash, policyId }); setFilter("all"); setConfirmReset(false); }}>Reset</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
