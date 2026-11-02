## 1. Wording in the web app

- [x] 1.1 Add `criterionText(id, text)` to `web/lib/copy.ts` (positive wording for C5, the policy text for every other id) and use it for the preparer answers table and checklist in `CaseView.tsx`, and for the released packet table and the copied text in `ReleasedPacket.tsx`; verify with `npm run typecheck`
- [x] 1.2 Add Playwright tests: a case whose C5 answer is Yes shows the positive wording in the answers table and the checklist as met; a released packet and its copied text show it and none contains "No PET-CT"; C1 to C4 and C6 equal the policy text; C5 is still in the policy copy; run `npm test`

## 2. Docs and checks

- [x] 2.1 Note the display wording in `web/README.md`; confirm with `git diff --stat` that nothing outside `web/` and this change changed (policy files, cases file, agent and frozen results untouched)

## Workflow follow-up

- Do not retrain, regenerate data or re-score any eval for this change.
- Archive the change after the PR is merged.
