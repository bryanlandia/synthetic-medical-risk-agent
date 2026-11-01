## 1. Sensitivity range in `risk_model`

- [x] 1.1 Add the closed-form sensitivity computation (per-item extremes, Platt slope guard, probability bounds) and verify with unit tests: complete record gives a point range, one missing lab brackets the probability, and bounds match a brute-force search over end values for up to six unmeasured items to 1e-9
- [x] 1.2 Cover the Plexa missing-indicator case and impossible-value labs (treated as missing) in tests, and verify the range of every dev-split record brackets its probability
- [x] 1.3 Emit `interval`, `gaps` and the two fixed-template confidence statements from `report.build`, and verify with tests that no recorded value changes, gaps are ordered by swing, and evidence stays within 8 statements of 300 characters; run `uv run pytest -q` in `risk_model/`

## 2. Report contract

- [x] 2.1 Add optional `gaps` to `RiskReport` in `evals/report.py` with its validation (bounds in [0, 1], low at most high), regenerate the schema with `evals schema --write`, and verify the schema test passes and other systems' reports still validate
- [x] 2.2 Add a code-graded `range_consistency` check (interval brackets the probability; gaps name only unmeasured items) to the classifier and agent graders, and verify `uv run evals regression` passes

## 3. Agent service

- [x] 3.1 Pass `interval` and `gaps` through, extend the reply check's allowed numbers to the interval and gap bounds, and add the range sentence to the template reply; verify with scripted-model tests that a quoted bound is released and any other invented percentage is replaced
- [x] 3.2 Run the agent's guard and injection tests and `uv run evals agent-scope`; verify no decline, injection or scope result changes

## 4. Web chart and report card

- [x] 4.1 Extend `evals demo-patients` to write each lab's reference range and an H/L flag (after unit conversion), regenerate `web/content/demo_patients.json`, and verify the stale-file test passes and the unit-mismatch patient is flagged correctly
- [x] 4.2 Show the range and flag in `ChartTab`, the range and gap list in `ReportCard`, and whitelist the new fields in `web/lib/forward.ts` and `types.ts`; verify with Playwright tests for a flagged lab, a not-reported lab, a missing-lab patient's wider range and gap entry, and that the phrase "confidence interval" and any value-editing control are absent
- [x] 4.3 Update `web/README.md` for the new fields; verify `npm test` and `npm run typecheck` pass

## 5. Evals and docs

- [x] 5.1 Run `uv run evals run --system classifier --split dev` and `--system agent --split dev`; verify metrics are unchanged and `range_consistency` passes on every record
- [x] 5.2 Record in the READMEs and the model card limitations that the range excludes model-fit uncertainty; verify the card test still passes and the model hash is unchanged
- [x] 5.3 Restore `web/next-env.d.ts` and `web/tsconfig.json` after the build and run the fast regression subset; verify everything passes

## Workflow follow-up

- Do not score test or adversarial for this change; the model is unchanged.
- Archive the change after the PR is merged.
