## Why

The risk percentage is the number a visitor is looking for, but it is easy to miss. In a case it is a clause in the middle of a body-text sentence, in the free-text card it is a 2.6rem figure with no label, and only the Estimate dial gives it real size (3rem). The three places should show the same figure in the same way, large and labelled.

## What Changes

- One shared figure for the estimated risk, used in the case view, the Estimate a risk panel and the free-text report card: a large number (about 4rem) in the theme's dark teal, a small label above it ("Estimated risk of Velorin-Kessler syndrome (fictional)"), and the range and uncertain band directly beneath.
- Case view: the percentage moves out of the body sentence into the figure at the top of the "Why this patient was flagged" block. The text beside it keeps "Context only; it decides no criterion" and the range sentence.
- Estimate a risk: the figure grows from 3rem to the shared size and the gauge sits directly under it.
- Free-text card: the figure replaces the bare 2.6rem number.
- The colour is not red, amber or green, so the number does not read as a verdict. The uncertain chip keeps its amber.
- No change to any value, route, model, policy check or eval.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-demo`: the report card and the Estimate a risk panel show the estimate as a large, labelled figure.
- `review-workspace`: the case view shows the estimate as the same figure, still labelled as context only.

## Impact

- `web/components/` (a new `RiskFigure`, and `CaseView.tsx`, `EstimatePanel.tsx`, `ReportCard.tsx`), `web/app/globals.css` (the `.big` rule), `web/tests/`.
- Existing test ids (`probability`, `estimate-probability`, `estimate`) stay on the number, so current tests keep working.
- Out of scope: the queue list (it must keep showing no probability), the gauge and bars, the released packet's wording, the model, the agent and the policy. No eval category is affected and nothing is re-scored.
