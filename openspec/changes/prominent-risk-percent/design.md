## Context

The estimate is shown in three places with three treatments: a clause in a `body2` sentence (CaseView), a 3rem MUI `Typography` (EstimatePanel) and a 2.6rem `.big` paragraph (ReportCard). Tests find the number by `data-testid` (`estimate-probability`, `probability`) and match `/^\d+%$/`.

## Decisions

- **One `RiskFigure` component** (`web/components/RiskFigure.tsx`) taking `probability` and optional children for the line beneath (range, band chip). It renders a label, then the number at about 4rem, weight 700, tabular figures, in the theme's dark teal. It takes a `testId`, so each screen keeps its current id on the number element and existing tests are untouched. Alternative of tuning each place separately was rejected: it is how the three drifted apart.
- **Neutral colour.** Teal is the theme's own colour. A red-to-green scale would read as a verdict, and the specs forbid verdict wording. The uncertain chip keeps its amber.
- **Case view:** the number leaves the sentence. The sentence keeps the range and "Context only; it decides no criterion", so the existing wording tests (the word "criteria", no verdict words, no dollar amounts) still apply.
- **Responsive:** the figure falls back to 3rem under the small breakpoint so it never wraps in the sticky Estimate panel.
- **Accessibility:** the label and number are in one element with `aria-live="polite"` only where it already was (Estimate). Contrast of dark teal on the white card is checked against 4.5:1.

## Risks

- A bigger number can be over-read. The label, the range and "context only" stay next to it, and the "fictional" wording is in the label itself.
- Layout shift in the free-text card: the badge moves under the number, as it already was.
