## Context

See proposal.md for motivation. The report is built by `risk_model/report.py` from a linear model: `features.build` gives eight lab z-scores, eight missing indicators and ten symptom columns; `RiskClassifier.logit` is `coef . x + intercept`, then an affine Platt step. A missing lab sits at z = 0 with its indicator on. `RiskReport` in `evals/report.py` already has an optional `interval`, and its schema is committed in `evals/contract/`. The reply check in `agent/guard.py` rejects any quoted percentage that is not the probability or a band edge. The chart is `web/components/ChartTab.tsx`, fed by `web/content/demo_patients.json`, which `evals demo-patients` writes.

## Goals / Non-Goals

**Goals:** a range around the probability, a gap list for a fixed patient, reference ranges and flags on the chart, all computed by code with no model call and no change to the model files.

**Non-Goals:** sliders or any editing of recorded values; a statistical confidence interval (model-fit uncertainty is not estimated); changing training, the generator or the model hash; the scan-readiness packet.

## Decisions

- **Exact closed form, no search.** The logit is a sum over features, and an unmeasured lab or unmentioned symptom changes only its own terms, so the extremes add up per item. For a missing lab the change from the current state is `coef_z * z - coef_missing`, linear in z, so its extremes sit at the two ends of the plausible range. For a symptom the choices are absent (0), possible, present. The Platt scale is positive, so the sigmoid keeps the order and the bounds map straight to probabilities. Alternative: sampling or an optimizer, which is slower and not exact. A test asserts the Platt slope is positive and compares the bounds with a brute-force search.
- **The missing indicator is part of the sum.** Obtaining a lab removes its indicator term as well as adding its value term. The Plexa count has a negative missing coefficient, so a typical Plexa value raises the estimate relative to missing. This is the fitted model's behaviour and is already a listed limitation in the card; the gap text states the bounds and does not explain a cause.
- **"Plausible" is mean plus or minus two SD, inside the plausibility bounds.** The full plausibility bounds reach six SD and would make most ranges 0 to 1, which says nothing. Two SD is a judgment, kept as one named constant and covered by a test. Alternative: the reference range (about 1.5 SD), which is narrower and tied to clinical flags. Trade-off: a different constant changes the numbers, not the method.
- **The range includes leaving an item unmeasured.** For a lab whose value term is near zero (the Osmet level) every plausible value would raise the logit, so the two end values alone do not contain the current estimate and the existing contract (lower bound at most the probability) would fail. Each item's change therefore ranges over {0} and its end values. A brute-force test rebuilds every feature vector to check this.
- **Version.** The report logic changed, so `LOGIC_VERSION` is 2 and the system version is `classifier@414c2d467c87+r2` (the agent's likewise). The r1 test and adversarial results stay recorded under r1; the r2 dev result has the same metrics. Test and adversarial are not re-scored and nothing is re-frozen here.
- **The prompted-model tool omits `gaps`.** The baseline's tool input is built from the committed schema and its cache key does not include the schema, so `report_tool()` leaves out `gaps` (computed by code, not asked of a model) and a fresh baseline call sees the same tool as before.
- **Evidence count.** Up to 4 drivers, 2 confidence statements and the summary, which stays last because the template reply reads `evidence[:-1]`; the training test allows 7 (the contract allows 8).
- **Naming.** The field stays `interval`, but the UI and templates call it the range if missing results are obtained. It excludes model-fit and calibration uncertainty, and says so, so it is never read as a confidence interval.
- **Gaps are optional and flat.** `gaps` is an optional list in `RiskReport` (extra fields are forbidden, so the schema must change). Prompted-model, oracle and floor systems omit it and stay valid. One entry per unmeasured item; routing is the existing bands (below 0.4, 0.4 to 0.6, above 0.6).
- **Confidence text from templates.** At most two fixed-template evidence statements, so no model writes report text and the fabrication check is unaffected.
- **The reply check accepts the new numbers.** Allowed numbers become the probability, band edges, interval bounds and gap bounds, each with its written-precision tolerance. Anything else still falls back to the template reply.
- **Flags computed where the data is written.** `evals demo-patients` adds the range and the H/L flag per lab, after unit conversion, so the browser does no unit logic and the stale-file test covers it.

## Risks / Trade-offs

- [The classifier system's version or ledger entry changes with new report fields] → check whether `system_version` depends only on the model hash; run `evals regression` and the dev run before touching any ledger; do not re-score test or adversarial.
- [The prompted-model system or the tool schema breaks on the new optional field] → the field is optional and the existing regression subset validates every system's reports.
- [Gap text for the Plexa quirk looks odd] → the gap shows bounds only; the card already lists missing labs as a weakness.
- [A visitor reads the range as clinical certainty] → fixed wording, "range if missing results are obtained", plus the disclaimer.
- [The reply check becomes looser] → only four named number sources are added; a test keeps rejecting other numbers.

## Migration Plan

Additive: new optional fields and new UI. Deploy the agent project, then the web project; the web whitelist ignores fields it does not know, so either order is safe. Rollback is a revert of each project. No data or model file changes.

## Open Questions

- Unmentioned symptoms widen the range a lot, because a note that omits a symptom is treated as possibly stating it. On the dev split 139 of 500 records (28%) have a range wider than 0.3, against 78 (16%) when only labs count. Whether an unmentioned symptom should count as "could be present" is worth a look, since the data omits many absent symptoms.

- Whether two SD is the right default range, to be revisited after seeing real demo-patient output; the constant is isolated so a change does not alter the spec.
