import { createTheme } from "@mui/material/styles";

/** Every colour the interface uses, in one place. The pairs are checked for contrast by a test (4.5:1). */
export const COLORS = {
  background: "#F4F8F8",
  surface: "#FFFFFF",
  text: "#171D1D",
  textMuted: "#3F4948",
  primary: "#00696B",
  primaryText: "#FFFFFF",
  line: "#C4CBCB",
  strip: "#1B2A41",
  stripText: "#F4F8F8",
  link: "#00504F",
  error: "#B3261E",
  errorBg: "#FCE8E6",
  errorText: "#8C1D18",
} as const;

/** Status chips: a background and a text colour that is readable on it. The status is also written out in words. */
export const STATUS_CHIPS = {
  new: { bg: "#E1E8E8", text: "#171D1D", label: "New" },
  "in-review": { bg: "#D7E3FF", text: "#0B3A8F", label: "In review" },
  returned: { bg: "#FFE7B0", text: "#5C4300", label: "Returned" },
  released: { bg: "#C9EBD4", text: "#0F4A27", label: "Released" },
  closed: { bg: "#E8E3E3", text: "#3F3A3A", label: "Closed" },
} as const;
export type StatusKey = keyof typeof STATUS_CHIPS;

/** Criterion statuses, also written out in words. */
export const CRITERION_CHIPS = {
  met: { bg: "#C9EBD4", text: "#0F4A27", label: "Met" },
  unmet: { bg: "#FFE7B0", text: "#5C4300", label: "Unmet" },
  unknown: { bg: "#E1E8E8", text: "#171D1D", label: "Unknown" },
} as const;

export const DEMO_CHIP = { bg: "#E8DEF8", text: "#3A2A66" } as const;

/** What produced a block: models in teal, plain code in grey, the simulated preparer in the Demo purple, the supervisor in green. The label says it too. */
export const PRODUCED_CHIPS = {
  model: { bg: "#D2EEF0", text: "#0B4A4C" },
  code: { bg: "#E1E8E8", text: "#171D1D" },
  preparer: DEMO_CHIP,
  you: { bg: "#C9EBD4", text: "#0F4A27" },
} as const;

/** Text-on-background pairs that must meet 4.5:1. */
export const CONTRAST_PAIRS: [string, string, string][] = [
  ["text on background", COLORS.text, COLORS.background],
  ["text on surface", COLORS.text, COLORS.surface],
  ["muted text on surface", COLORS.textMuted, COLORS.surface],
  ["muted text on background", COLORS.textMuted, COLORS.background],
  ["primary button text", COLORS.primaryText, COLORS.primary],
  ["primary text on surface", COLORS.primary, COLORS.surface],
  ["link on surface", COLORS.link, COLORS.surface],
  ["strip text", COLORS.stripText, COLORS.strip],
  ["error text", COLORS.errorText, COLORS.errorBg],
  ["demo chip", DEMO_CHIP.text, DEMO_CHIP.bg],
  ...Object.entries(PRODUCED_CHIPS).map(([k, v]) => [`produced ${k}`, v.text, v.bg] as [string, string, string]),
  ...Object.entries(STATUS_CHIPS).map(([k, v]) => [`status ${k}`, v.text, v.bg] as [string, string, string]),
  ...Object.entries(CRITERION_CHIPS).map(([k, v]) => [`criterion ${k}`, v.text, v.bg] as [string, string, string]),
];

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: COLORS.primary, contrastText: COLORS.primaryText },
    error: { main: COLORS.error },
    background: { default: COLORS.background, paper: COLORS.surface },
    text: { primary: COLORS.text, secondary: COLORS.textMuted },
    divider: COLORS.line,
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: 'Roboto, "Helvetica Neue", system-ui, -apple-system, "Segoe UI", sans-serif',
    h1: { fontSize: "1.35rem", fontWeight: 600, letterSpacing: 0 },
    h2: { fontSize: "1.25rem", fontWeight: 600 },
    h3: { fontSize: "1.05rem", fontWeight: 600 },
    h4: { fontSize: "1rem", fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: { styleOverrides: { a: { color: COLORS.link } } },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiPaper: { defaultProps: { elevation: 0 }, styleOverrides: { root: { border: `1px solid ${COLORS.line}` } } },
    MuiTooltip: { defaultProps: { arrow: true, enterTouchDelay: 0 } },
  },
});
