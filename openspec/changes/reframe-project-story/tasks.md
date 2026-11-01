## 1. Model card text

- [x] 1.1 Add the disease course and funder line to the card's intended-use text in `training/src/training/model_card.py`; run `uv run training card` from `training/` and verify `training/model/MODEL_CARD.md` and `web/content/model-card.md` contain it
- [x] 1.2 Add a card test for the new text, the absence of treatment/dose/outcome figures, and an unchanged model hash; verify `uv run pytest -q` passes in `training/`

## 2. About text

- [x] 2.1 Rewrite `web/content/about.md` with the disease course, pathway and two ledgers, funder paragraph, and a "what comes next" list; verify each story heading appears in the file
- [x] 2.2 Fix the leftovers: Haiku AUC wording, "agent" wording, restore the guards paragraph and the reviewer caveat; verify by reading the file against the requirement
- [x] 2.3 Extend the About Playwright tests for the story headings and for no treatment names, doses, percentages or dollar/days figures; verify `npm test` in `web/` passes

## 3. Footer

- [x] 3.1 Add a footer naming the Kessler Family Foundation as fictional to `web/app/layout.tsx`, styled in `globals.css`; verify it is visible on each tab
- [x] 3.2 Add Playwright tests that the footer is on every tab and that the foundation's name is absent from the request body and the report; verify `npm test` passes

## 4. Docs and integration

- [x] 4.1 Update the README intro and the "to date" and TODO text to match the About story; verify the README makes no claim about features that do not exist
- [x] 4.2 Restore `web/next-env.d.ts` and `web/tsconfig.json` after the build, run `uv run evals regression` from `evals/`, and verify the web and training suites pass and the model hash is unchanged

## Workflow follow-up

- Review the copy once on a preview deploy before merging, since the wording is the deliverable.
- Archive the change after the PR is merged.
