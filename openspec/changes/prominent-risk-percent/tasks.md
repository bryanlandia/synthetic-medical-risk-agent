## 1. The shared figure (`web`)

- [x] 1.1 Add `RiskFigure` (label, number at about 4rem in dark teal, children beneath, `testId` prop, 3rem on small screens) and use it in `EstimatePanel`, `ReportCard` (replacing `.big`) and `CaseView` (number moved out of the sentence, range and "Context only" kept); verify with tests that the number is at least 3.5rem and larger than any other text in its block in all three places, keeps its test id and `/^\d+%$/` text, carries the Velorin-Kessler (fictional) label, is not red, amber or green, and that the queue still shows no probability

## 2. Checks

- [x] 2.1 Run `npm run typecheck` and `npm test` (restore `next-env.d.ts` and `tsconfig.json`), look at the three screens at desktop and phone width, and confirm with `git diff --stat` that only `web/` changed and no model, policy, agent or frozen result was touched

## Workflow follow-up

- Do not retrain, re-score any eval or spend on the model.
- Archive the change after the PR is merged.
