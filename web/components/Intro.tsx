"use client";

import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { PURPOSE_PARAGRAPHS, PURPOSE_TITLE } from "@/lib/copy";
import { useReview } from "./ReviewProvider";
import { Row, withTerms } from "./ui";

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
