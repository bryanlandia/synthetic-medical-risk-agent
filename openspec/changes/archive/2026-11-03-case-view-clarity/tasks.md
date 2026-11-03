## 1. Wording and controls (`web`)

- [x] 1.1 Reword the estimate (name Velorin-Kessler syndrome as the subject, keep the range and "context only"), head the chart's note "Clinical note", remove the `answers` Demo note and its use, drop the `criteria` hint and write "coverage criteria" in the checklist heading and the explanation text, and make the sent-message control a labelled Show/Hide disclosure with a chevron; verify with tests for each string, that the preparer answers have no Demo chip, that "criteria" has no hint, that the control is operable by keyboard and its label changes, and that the existing wording tests (no verdict words, no dollar amounts) pass on the new text

## 2. Received date and zone

- [x] 2.1 Make the builder write a dated `received` (seeded over three working days, same seed gives the same values), regenerate `web/content/cases.json`, show it as "2 Nov 2026, 07:45 ET" in the queue and in the case header, and keep the stale-file test; verify with a builder test for byte-identical rebuild and the date range, a web test that every row shows a date, a time and "ET", and `uv run evals regression` from `evals/`

## 3. Where the models operate

- [x] 3.1 Add the provenance table to `copy.ts`, the `Produced` chip, the Source column in the checklists, the chips on each case-view and released-packet block, the "What produced this page?" key (queue, case and free-text view) with Escape and focus return; verify with tests that each block carries the right chip (including Template when the summary source is the template), the Source column matches the policy sources, the key opens and closes with the keyboard, the key and chips contain no accuracy figure, dollar amount or verdict word, and the analytics tests still pass

## 4. Docs and checks

- [x] 4.1 Run `npm run typecheck` and `npm test` (restore `next-env.d.ts` and `tsconfig.json`), update `web/README.md` for the provenance table and the received field, and confirm with `git diff --stat` that the policy, agent, risk model and frozen results are untouched

## Workflow follow-up

- Do not retrain, re-score any eval or spend on the model.
- Archive the change after the PR is merged.
