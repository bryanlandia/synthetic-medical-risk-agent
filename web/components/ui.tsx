"use client";

import Box from "@mui/material/Box";
import type { SxProps, Theme } from "@mui/material/styles";
import Chip from "@mui/material/Chip";
import TableCell from "@mui/material/TableCell";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { Fragment, type ReactNode } from "react";
import { CRITERION_SOURCE, DEMO_NOTES, HINTS, PRODUCED, STRIP_TEXT, formatReceived, type DemoNoteKey, type HintTerm, type ProducedKind } from "@/lib/copy";
import { CRITERION_CHIPS, DEMO_CHIP, PRODUCED_CHIPS, STATUS_CHIPS, COLORS, type StatusKey } from "@/lib/theme";

/** The one loud element: a strip on every screen saying everything is invented. */
export function DemoStrip() {
  return (
    <Box className="no-print" role="note" data-testid="demo-strip" sx={{ bgcolor: COLORS.strip, color: COLORS.stripText, px: 2, py: 0.75, position: "sticky", top: 0, zIndex: 1300 }}>
      <Row spacing={1.5} alignItems="center" justifyContent="center" flexWrap="wrap">
        <Chip size="small" label="DEMO" sx={{ bgcolor: DEMO_CHIP.bg, color: DEMO_CHIP.text, fontWeight: 700 }} />
        <Typography variant="body2">{STRIP_TEXT}</Typography>
      </Row>
    </Box>
  );
}

/** A small chip and a muted sentence beside something that is simulated. */
export function DemoNote({ note }: { note: DemoNoteKey }) {
  return (
    <Row spacing={1} alignItems="flex-start" data-testid={`demo-note-${note}`} sx={{ my: 0.75 }}>
      <Chip size="small" label="Demo" sx={{ bgcolor: DEMO_CHIP.bg, color: DEMO_CHIP.text, height: 20, flexShrink: 0 }} />
      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.5 }}>{DEMO_NOTES[note]}</Typography>
    </Row>
  );
}

/** A small label saying what produced a block (a model, code, the simulated preparer or the supervisor), with its explanation on hover or focus. */
export function Produced({ kind, testId }: { kind: ProducedKind; testId?: string }) {
  const p = PRODUCED[kind];
  const c = PRODUCED_CHIPS[p.tone];
  return (
    <Tooltip title={p.text} describeChild>
      <Box component="span" tabIndex={0} data-testid={`produced-${testId ?? kind}`} data-produced={kind} sx={{ display: "inline-flex", verticalAlign: "middle", ml: 1, borderRadius: 4, "&:focus-visible": { outline: `2px solid ${COLORS.primary}`, outlineOffset: 2 } }}>
        <Chip size="small" label={p.label} sx={{ bgcolor: c.bg, color: c.text, height: 22, fontSize: "0.75rem", cursor: "help" }} />
      </Box>
    </Tooltip>
  );
}

/** Where a criterion's answer comes from, and what produced it. */
export function SourceCell({ source, testId }: { source: string; testId: string }) {
  const kind: ProducedKind = source === "labs" ? "rules" : source === "note" ? "reader" : "preparer";
  return (
    <TableCell data-testid={`source-${testId}`}>
      {CRITERION_SOURCE[source as keyof typeof CRITERION_SOURCE] ?? source}
      <Produced kind={kind} testId={`source-${testId}`} />
    </TableCell>
  );
}

/** A term with a short hint, reachable by keyboard. */
export function Term({ term, children }: { term: HintTerm; children?: ReactNode }) {
  return (
    <Tooltip title={HINTS[term]} describeChild>
      <Box component="span" tabIndex={0} sx={{ borderBottom: "1px dotted", cursor: "help", "&:focus-visible": { outline: `2px solid ${COLORS.primary}`, outlineOffset: 2 } }}>
        {children ?? term}
      </Box>
    </Tooltip>
  );
}

const TERM_PATTERN = /(PET-CT|prior authorization|packet)/g;

/** Text in which the first use of each of the three terms carries its hint. */
export function withTerms(paragraphs: string[]): ReactNode[] {
  const seen = new Set<string>();
  return paragraphs.map((text, i) => (
    <Typography key={i} variant="body1" sx={{ mb: 1.25 }}>
      {text.split(TERM_PATTERN).map((part, j) => {
        if (part && part in HINTS && !seen.has(part)) {
          seen.add(part);
          return <Term key={j} term={part as HintTerm} />;
        }
        return <Fragment key={j}>{part}</Fragment>;
      })}
    </Typography>
  ));
}

export function StatusChip({ status, testId }: { status: StatusKey; testId?: string }) {
  const c = STATUS_CHIPS[status];
  return <Chip size="small" label={c.label} data-testid={testId} sx={{ bgcolor: c.bg, color: c.text }} />;
}

export function CriterionChip({ status, testId }: { status: keyof typeof CRITERION_CHIPS; testId?: string }) {
  const c = CRITERION_CHIPS[status];
  return <Chip size="small" label={c.label} data-testid={testId} sx={{ bgcolor: c.bg, color: c.text }} />;
}

export const clock = (at: string): string => (/^\d{4}-\d\d-\d\d \d\d:\d\d$/.test(at) ? formatReceived(at) : new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));

/** A row of items with a gap, aligned and wrapped as asked. */
export function Row({ spacing = 1, alignItems, justifyContent, flexWrap, component = "div", sx, children, ...rest }: {
  spacing?: number; alignItems?: string; justifyContent?: string; flexWrap?: "wrap" | "nowrap"; component?: "div" | "nav"; sx?: SxProps<Theme>; children?: ReactNode;
  role?: string; className?: string; "aria-label"?: string; "data-testid"?: string;
}) {
  return (
    <Box component={component} sx={[{ display: "flex", flexDirection: "row", gap: spacing, alignItems, justifyContent, flexWrap }, ...(Array.isArray(sx) ? sx : [sx])]} {...rest}>
      {children}
    </Box>
  );
}
