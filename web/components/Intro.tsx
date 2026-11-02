"use client";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { PRODUCED, PRODUCED_INTRO, PRODUCED_TITLE, PURPOSE_PARAGRAPHS, PURPOSE_TITLE, type ProducedKind } from "@/lib/copy";
import { useReview } from "./ReviewProvider";
import { Produced, Row, withTerms } from "./ui";

/** The first thing on the queue: what the packet is for, in plain words. */
export function IntroCard() {
  const { saved, dispatch, hydrated } = useReview();
  if (hydrated && saved.introDismissed) return null;
  return (
    <Paper component="section" aria-labelledby="purpose-title" data-testid="intro-card" sx={{ p: 3, mb: 3, bgcolor: "#EAF3F3" }}>
      <Typography id="purpose-title" variant="h2" component="h2" sx={{ mb: 1.5 }}>{PURPOSE_TITLE}</Typography>
      {withTerms(PURPOSE_PARAGRAPHS)}
      <Row justifyContent="flex-end" sx={{ mt: 1 }}>
        <Button data-track="intro_dismiss" onClick={() => dispatch({ type: "dismissIntro" })}>Got it, hide this</Button>
      </Row>
    </Paper>
  );
}

/** The same text, from every case. */
export function HelpButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="small" variant="outlined" data-track="help" onClick={() => setOpen(true)}>{PURPOSE_TITLE}</Button>
      <Dialog open={open} onClose={() => setOpen(false)} aria-labelledby="help-title" maxWidth="sm" fullWidth>
        <DialogTitle id="help-title">{PURPOSE_TITLE}</DialogTitle>
        <DialogContent data-testid="help-dialog">
          {PURPOSE_PARAGRAPHS.map((p, i) => <Typography key={i} sx={{ mb: 1.25 }}>{p}</Typography>)}
        </DialogContent>
        <DialogActions><Button onClick={() => setOpen(false)} autoFocus>Close</Button></DialogActions>
      </Dialog>
    </>
  );
}

const KEY_ORDER: ProducedKind[] = ["classifier", "reader", "rules", "llm", "template", "agent", "preparer", "you"];

/** The key to the labels on each part of a case: what is a model, what is plain code, what is simulated, and what is yours. */
export function ProducedKeyButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="small" variant="outlined" data-track="help" onClick={() => setOpen(true)}>{PRODUCED_TITLE}</Button>
      <Dialog open={open} onClose={() => setOpen(false)} aria-labelledby="produced-title" maxWidth="sm" fullWidth>
        <DialogTitle id="produced-title">{PRODUCED_TITLE}</DialogTitle>
        <DialogContent data-testid="produced-key">
          <Typography sx={{ mb: 1.5 }}>{PRODUCED_INTRO}</Typography>
          {KEY_ORDER.map((k) => (
            <Row key={k} spacing={1} alignItems="flex-start" sx={{ mb: 1 }}>
              <Box sx={{ minWidth: 190 }}><Produced kind={k} testId={`key-${k}`} /></Box>
              <Typography variant="body2">{PRODUCED[k].text}</Typography>
            </Row>
          ))}
        </DialogContent>
        <DialogActions><Button onClick={() => setOpen(false)} autoFocus>Close</Button></DialogActions>
      </Dialog>
    </>
  );
}
