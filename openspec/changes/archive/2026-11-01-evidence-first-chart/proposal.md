# Proposal

## Why

A visitor can only use the demo by pressing sample buttons or writing a clinical note. A chart that shows what the record supports, with its reference ranges, a range around the probability and what is missing, is usable without typing and is the evidence block the prior-auth packet (`pet-ct-readiness`) will cite. It also replaces a single bare probability with an honest statement of confidence.

## What Changes

- Show each lab with its unit, reference range and H/L flag on the chart. The generator already computes the range and flag; the work is to carry them to the chart and report and to define the range for every lab.
- Report a probability range, not only the 0.4 to 0.6 `uncertain` band. The report contract already allows an optional interval. The range comes from closed-form computation over plausible values of unmeasured labs and unmentioned symptoms, done in `risk_model` with numpy and no model call.
- Add a gap analysis for a fixed patient: for each unmeasured lab, how far the result could move across its plausible range, and whether obtaining it could change the routing (confident, uncertain, needs a human). It never edits recorded values.
- Show why a number is or is not confident, in text written from fixed templates, like the existing evidence strings.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `risk-report`: scored reports carry the interval (now produced, not optional in practice) and a gap list; the interval must bracket the probability and use only measured and unmeasured labs.
- `web-demo`: the chart shows reference ranges and flags; the report card shows the range and the gaps.

## Impact

- `risk_model/` (interval and gap computation; note the classifier has a missing-lab indicator feature, so the bounds must account for it), `agent/` (passes the new fields through; guards unchanged), `web/` chart and report card, `evals/` report grading.
- No model files change, so the model hash and card stay valid. Verify before relying on this.
- Out of scope: editable values or sliders, criteria checking, the packet, multi-turn state, a differential diagnosis, changes to training or data generation.
- Eval categories affected: report validity (interval brackets the probability), no-fabrication, and a new code-graded check that the interval contains the probability under every missing-lab filling.
