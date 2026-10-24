# Tasks

## 1. Rating file contract and gate

- [x] 1.1 Add a blind `sheet.json` to the pilot output (same ids, order and text as `sheet.md`, no setting names or key data) and verify tests that scan it for setting names and key contents and compare it to `sheet.md`
- [x] 1.2 Define the `ratings.<rater>.json` schema (rater, kind, model id and prompt version for llm, six fields and comment per note) with atomic writing, and verify round-trip and invalid-value tests
- [x] 1.3 Make `data-gen gate` load rating files and legacy `ratings.md` (kind `human`), add `llm.gate_rater_kinds` (default `["human"]`), count only accepted kinds, use the pessimistic plausibility across raters, and report disagreements; verify tests for llm-only fails by default, explicit acceptance passes, markdown still works and disagreement counts
- [x] 1.4 Record accepted rater kinds in the gate report and the manifest, and verify the manifest and README text say "LLM review, not a clinician" when `llm` was accepted, and that template manifests stay byte-identical

## 2. Rating app

- [ ] 2.1 Scaffold `rating_ui/` (Next.js, TypeScript, pinned versions, no deploy config, loopback binding) and verify `npm run build` and `npm run dev` start on 127.0.0.1 only
- [ ] 2.2 Implement the route handlers with the path guard (blind sheet in, rating file out, key never read, kind from launch config) and verify tests requesting every route and traversal paths find no key content and that a body-supplied kind is ignored
- [ ] 2.3 Implement the one-note-at-a-time page: six fields, keyboard shortcuts, back and forward, progress with incomplete marking, synthetic-data notice, autosave and resume, with test ids on every control; verify Playwright tests for keyboard-only rating, reload resume and incomplete marking
- [ ] 2.4 Add a README for clinicians (how to launch, what each field means, where the file goes, how to run the gate) and verify a person following it from a clean checkout reaches a saved rating file

## 3. Adversarial reviewer, direct mode

- [ ] 3.1 Add the `review` extra, reviewer config (model id default `claude-sonnet-5-5`, caps, attempt limit), the skeptical-clinician prompt and strict output parsing; verify tests that prompts contain no setting names, plan data or key contents, that the same model id as the writer is refused, and that malformed output is retried then left unrated
- [ ] 3.2 Route reviewer calls through the cache and caps, add a keyless `review --estimate`, and write `ratings.<model>.json` with kind `llm`; verify tests for a free rerun with identical output, cap halting with partial ratings kept, and a dry run with no key
- [ ] 3.3 Add the controls-discrimination check (controls at least 20 points lower than LLM-written notes, else flagged and the gate fails) and verify with a fake reviewer that rates everything plausible and one that discriminates

## 4. Adversarial reviewer, browser mode with video

- [ ] 4.1 Implement the fixed tool set mapped to Playwright actions on the app's test ids, URL allow-list, step limit and refusal counting; verify tests with a scripted fake model against the real running app that all six actions work and that off-list actions and URLs are refused and counted
- [ ] 4.2 Implement the Anthropic tool-use loop over the page's accessibility snapshot with the shared spend cap and video recording to the round directory, and verify a scripted run produces a complete rating file written by the app, a session log and a non-empty video
- [ ] 4.3 Verify that hitting the step, call or spend limit keeps partial ratings, saves the video and makes the gate report the rest as unrated

## 5. Docs and integration

- [ ] 5.1 Update AGENTS.md (layout, commands for the app, `review` and the gate) and the dataset README, and verify the documented commands run as written
- [ ] 5.2 Run the real review on the pilot round in direct mode and then in browser mode; record the plausible rates, controls gap, disagreements, spend and video path in the change notes, and verify the gate output names the accepted rater kinds
- [ ] 5.3 Check the repository: no key or API token in tracked files, the video under the size limit if committed, `rating_ui/` has no deploy config (local-only for now), and `openspec validate add-realism-rating-ui --strict` passes

## Workflow follow-up

- Archive this change after `add-llm-note-writer` is archived, and reconcile that change's human-gate requirement with the accepted rater kinds.
