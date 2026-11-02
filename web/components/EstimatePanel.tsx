"use client";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import Switch from "@mui/material/Switch";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { BAND_TEXT, BREAKDOWN_NOTE, ESTIMATE_STATUS_TEXT, SYMPTOM_LABELS, SYMPTOM_STATES } from "@/lib/copy";
import type { EstimateStatus } from "@/lib/estimator";
import type { Estimate, EstimateContent, EstimateInputs, EstimateLab, ShownError } from "@/lib/types";
import { Row } from "./ui";

type Api = {
  inputs: EstimateInputs;
  setLab: (key: string, value: number) => void;
  setDone: (key: string, done: boolean) => void;
  setSymptom: (key: string, state: "absent" | "possible" | "present") => void;
  reset: () => void;
};

const shown = (lab: EstimateLab, v: number) => `${v.toFixed(lab.decimals)} ${lab.unit}`;

function LabControl({ lab, value, api }: { lab: EstimateLab; value: number | null; api: Api }) {
  const done = value !== null;
  const outside = done && (value < lab.ref_lo ? "below" : value > lab.ref_hi ? "above" : null);
  return (
    <Box data-testid={`lab-${lab.key}`} sx={{ mb: 2 }}>
      <Row justifyContent="space-between" alignItems="center" flexWrap="wrap">
        <Typography id={`lab-${lab.key}-label`} variant="body1" sx={{ fontWeight: 600 }}>{lab.name} ({lab.abbr})</Typography>
        <FormControlLabel
          control={<Switch size="small" checked={!done} onChange={(_, notDone) => api.setDone(lab.key, !notDone)} slotProps={{ input: { "aria-label": `${lab.name} not done` } }} />}
          label="Not done"
        />
      </Row>
      <Slider
        aria-labelledby={`lab-${lab.key}-label`}
        getAriaValueText={(v) => shown(lab, v)}
        value={value ?? (lab.ref_lo + lab.ref_hi) / 2}
        min={lab.min} max={lab.max} step={lab.step}
        disabled={!done}
        onChange={(_, v) => api.setLab(lab.key, v as number)}
        sx={{ mt: 0.5, "& .MuiSlider-thumb": { display: done ? undefined : "none" } }}
      />
      <Typography variant="caption" color="text.secondary" data-testid={`lab-${lab.key}-value`}>
        {done ? `${shown(lab, value)}${outside ? ` (${outside} the reference range ${lab.ref_lo} to ${lab.ref_hi})` : ""}` : "Not done: the model treats this result as missing"}
      </Typography>
    </Box>
  );
}

function SymptomControl({ symptom, state, api }: { symptom: string; state: string; api: Api }) {
  return (
    <Row justifyContent="space-between" alignItems="center" flexWrap="wrap" sx={{ mb: 1 }} data-testid={`symptom-${symptom}`}>
      <Typography id={`symptom-${symptom}-label`} variant="body1" sx={{ fontWeight: 600 }}>{SYMPTOM_LABELS[symptom] ?? symptom}</Typography>
      <ToggleButtonGroup
        exclusive size="small" value={state} aria-labelledby={`symptom-${symptom}-label`}
        onChange={(_, next) => { if (next) api.setSymptom(symptom, next); }}
      >
        {Object.entries(SYMPTOM_STATES).map(([value, label]) => <ToggleButton key={value} value={value} sx={{ textTransform: "none", px: 1.5 }}>{label}</ToggleButton>)}
      </ToggleButtonGroup>
    </Row>
  );
}

export function EstimateControls({ content, api }: { content: EstimateContent; api: Api }) {
  return (
    <Paper component="section" aria-label="Patient inputs" sx={{ p: 3 }}>
      <Row justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h3" component="h3">Invented patient</Typography>
        <Button size="small" variant="outlined" data-testid="estimate-reset" onClick={api.reset}>Reset</Button>
      </Row>
      <Typography variant="h4" component="h4" sx={{ mb: 1 }}>Labs</Typography>
      {content.labs.map((lab) => <LabControl key={lab.key} lab={lab} value={api.inputs.labs[lab.key]} api={api} />)}
      <Typography variant="h4" component="h4" sx={{ mt: 3, mb: 1 }}>Symptoms</Typography>
      {content.symptoms.map((s) => <SymptomControl key={s} symptom={s} state={api.inputs.symptoms[s]} api={api} />)}
    </Paper>
  );
}

const signed = (v: number) => (Math.abs(v) < 0.005 ? "0.00" : `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}`); // a share that rounds to zero has no sign

function Gauge({ p }: { p: number }) {
  return (
    <Box role="img" aria-label={`Estimate ${Math.round(p * 100)} percent on a scale from 0 to 100, with the uncertain range from 40 to 60`} sx={{ position: "relative", height: 14, borderRadius: 7, bgcolor: "#E1E8E8", my: 1.5 }}>
      <Box sx={{ position: "absolute", left: "40%", width: "20%", top: 0, bottom: 0, bgcolor: "#FFE7B0" }} />
      <Box sx={{ position: "absolute", left: `calc(${(p * 100).toFixed(1)}% - 4px)`, top: -3, width: 8, height: 20, borderRadius: 1, bgcolor: "primary.main", transition: "left 120ms" }} />
    </Box>
  );
}

function Bars({ content, estimate }: { content: EstimateContent; estimate: Estimate }) {
  const labs = new Map(content.labs.map((l) => [l.key, l]));
  const top = Math.max(1, ...estimate.breakdown.map((r) => Math.abs(r.contribution)));
  return (
    <Box component="ul" data-testid="breakdown" sx={{ listStyle: "none", p: 0, m: 0 }}>
      {estimate.breakdown.map((row) => {
        const name = row.kind === "lab" ? labs.get(row.key)?.name ?? row.key : SYMPTOM_LABELS[row.key] ?? row.key;
        const width = `${(Math.abs(row.contribution) / top) * 50}%`;
        const up = row.contribution >= 0;
        return (
          <Box component="li" key={`${row.kind}-${row.key}`} data-testid={`bar-${row.key}`} data-contribution={row.contribution} sx={{ display: "grid", gridTemplateColumns: "9.5rem 1fr 3.5rem", alignItems: "center", gap: 1, mb: 0.5 }}>
            <Typography variant="body2">{name}</Typography>
            <Box aria-hidden="true" sx={{ position: "relative", height: 12 }}>
              <Box sx={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: "1px", bgcolor: "#C4CBCB" }} />
              <Box sx={{ position: "absolute", top: 1, bottom: 1, width, [up ? "left" : "right"]: "50%", bgcolor: up ? "#00696B" : "#8C5A00", borderRadius: 1 }} />
            </Box>
            <Typography variant="body2" sx={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{signed(row.contribution)}</Typography>
          </Box>
        );
      })}
      <Box component="li" data-testid="bar-start" sx={{ display: "grid", gridTemplateColumns: "9.5rem 1fr 3.5rem", gap: 1, mt: 1, pt: 1, borderTop: "1px solid #C4CBCB" }}>
        <Typography variant="body2">Starting point</Typography>
        <span />
        <Typography variant="body2" sx={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{signed(estimate.start)}</Typography>
      </Box>
    </Box>
  );
}

export function EstimateResult({ content, estimate, inputs, status, error }: { content: EstimateContent; estimate: Estimate; inputs: EstimateInputs; status: EstimateStatus; error?: ShownError }) {
  const notDone = content.labs.filter((l) => inputs.labs[l.key] === null).map((l) => l.name);
  const statusText = status === "error" ? error?.message ?? "Something went wrong. Please try again." : ESTIMATE_STATUS_TEXT[status];
  return (
    <Paper component="section" aria-label="Estimate" sx={{ p: 3, position: { md: "sticky" }, top: { md: 16 } }}>
      <Typography variant="h3" component="h3">Estimate</Typography>
      <Typography component="p" data-testid="estimate-probability" aria-live="polite" sx={{ fontSize: "3rem", fontWeight: 700, lineHeight: 1.1, mt: 1 }}>{Math.round(estimate.probability * 100)}%</Typography>
      <Chip data-testid="estimate-band" label={BAND_TEXT[estimate.band]} sx={{ mt: 1, bgcolor: estimate.band === "uncertain" ? "#FFE7B0" : "#E1E8E8", color: estimate.band === "uncertain" ? "#5C4300" : "#171D1D" }} />
      <Gauge p={estimate.probability} />
      <Typography variant="body2" role={status === "error" ? "alert" : "status"} data-testid="estimate-status" color={status === "error" ? "error" : "text.secondary"} sx={{ minHeight: "1.5em" }}>{statusText}</Typography>
      <Typography variant="h4" component="h4" sx={{ mt: 2, mb: 0.5 }}>What moved it</Typography>
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mb: 1 }}>{BREAKDOWN_NOTE}</Typography>
      <Bars content={content} estimate={estimate} />
      {notDone.length > 0 && <Typography variant="caption" color="text.secondary" component="p" data-testid="not-done-note" sx={{ mt: 1 }}>Not done: {notDone.join(", ")}. Their bars show how the model treats a missing result.</Typography>}
    </Paper>
  );
}
