## 1. The 30 cases (`evals`)

- [x] 1.1 Write the cases builder: stratified seeded selection of 30 dev records (C1 met 8 to 10, unknown 6 to 7, the rest unmet; at least 3 unit mismatch, 2 contradiction, 3 borderline, 3 with a lab not reported; tremor present, hedged, absent and not mentioned) using the packet reference for statuses and the record's noise tags; reuse the chart building (reference ranges and flags) and the harness's `render_message`; verify with tests that every id is in the dev split, every message equals the harness rendering, the mix meets the ranges and no ground-truth key appears
- [x] 1.2 Add the seeded preparer answers (at least 15 fully answered yes, at least 3 with a no, at least 3 with an unanswered item), the ten fictional insurers, eight made-up preparer surnames, request codes and received times; verify with tests that a rebuild is byte-identical, at least 6 insurers appear, and none of the names is on a short list of real insurer and organisation names
- [x] 1.3 Add `evals demo-cases`, write `web/content/cases.json` with a content hash, and remove `demo_patients.json`, `evals demo-patients` and their stale-file test; verify with a stale-file test that fails if the committed file differs, and that the packets built for the 30 (scripted service) give at least 3 fully releasable (the three dev patients with C1 and C2 both met), 5 with an unknown criterion and 5 with an unmet one; run `uv run pytest -q` and `uv run evals regression` from `evals/`

## 2. Material foundation (`web`)

- [x] 2.1 Add the pinned MUI dependencies (checked for React 19 and Next 15 peer ranges), the App Router cache provider and one custom theme (palette, type, shape, spacing, focus rings) with the system font stack and no third-party font, script or image; record the first-load JS size before and after; verify with `npm run typecheck`, a production build, and a Playwright test that the built pages make no request to another site
- [x] 2.2 Build the shell: the persistent demo strip, the app bar with Queue and a "Behind the demo" menu, the footer naming the fictional foundation, and the analytics notice; verify with Playwright tests that the strip, title and footer are visible on the queue, a case and each Behind the demo view, and that no view claims HL7, FHIR or a vendor
- [x] 2.3 Check theme contrast for text and chips against their backgrounds (4.5:1) and that status is also shown as text; verify with a test over the theme's colour pairs

## 3. State and persistence

- [x] 3.1 Write the reducer, the `localStorage` store (key, cases hash, policy id, versioning, hydrate-after-mount) and Reset; verify with Playwright tests that returned cases and notes survive a reload, a stale hash or policy id is discarded, Reset after confirmation restores 30 New cases and cancelling changes nothing, and nothing is stored server-side

## 4. Queue and explanation

- [x] 4.1 Build the queue (30 rows with the specified fields, status chips with text, status filter) from `cases.json`; verify with tests that 30 New rows show on first load, no packet request is made and no row shows a probability or a criterion status, and that filtering Returned shows only returned cases
- [x] 4.2 Build the "What is this packet for?" card, the help dialog and the four term hints from one source string, with the dismiss-and-restore behavior; verify with tests that the card names the scan, the criteria, the evidence, the missing items, the supervisor's decision and that the tool decides nothing about care or coverage, that it stays dismissed across a reload and returns after Reset, that the help dialog closes with Escape, and that no text contains approved, denied, eligible or qualifies

## 5. The case view

- [x] 5.1 Build the case view: chart (labs with range and flag, note), the sent-message control, the checklist with cited evidence and gaps, the checked summary with its source, the risk estimate and range as context, and the preparer's four answers with no control to change them; make one packet request on first open, keep the result, set New to In review, and explain 429 and 503 with a retry; verify with tests for exactly one request carrying the stored message and the preparer answers, no request on reopening, citations beside met criteria, the error messages, and no answer-editing control
- [x] 5.2 Add the `DemoNote` component and place the notes for the role, the preparer answers, the shared policy, the release, the cover sheet, the return note and the saved progress, from one table; verify with a test that opens each place and finds its note, that notes are not dismissible banners, and that the flow shows no dollar amount, savings word or accuracy figure

## 6. Decisions and the released packet

- [x] 6.1 Build Release, Return with a note and Close with their rules (Release disabled while any criterion is unknown with the gap named, rationale of at least 20 characters when any is unmet, note of at least 5 characters to return) and the confirm dialogs that say nothing is transmitted; verify with tests for each rule, that Returned shows its chip and note in the queue, that a decided case is read-only, that focus returns to the opening control after a dialog, and that no request is made by a decision
- [x] 6.2 Build the released packet: cover sheet with the fictional insurer, code, patient id and study, the checklist with evidence, the summary, the supervisor's rationale marked as their own words, the audit timeline, the what-happens-next note, copy and print with a print stylesheet; verify with tests for the cover sheet fields, the timeline order across open, return, reopen and release, and that the print view holds the packet and the notice and omits the queue and controls

## 7. Behind the demo and analytics

- [x] 7.1 Move the free-text assistant, the model card and About under "Behind the demo" with their behavior unchanged (labs names from `cases.json`); verify by adapting the existing free-text, model-card and About tests to the new navigation and running them
- [x] 7.2 Replace the analytics click names with the new fixed set and update the name checker; verify with the analytics tests that each named click sends one event, that a case click carries only its ordinal, and that typed text, a return note, a rationale, a patient id and a criterion status never appear in an event; opt-out and Do Not Track still hold

## 8. Suite, docs and checks

- [x] 8.1 Rewrite the remaining Playwright tests around the queue and case view, keep `forward` and `packet-forward`, add a keyboard-only run through a case (open, decide, close the dialog), and add a test that no verdict wording or care-gating wording appears; run `npm test` and `npm run typecheck`, then restore `next-env.d.ts` and `tsconfig.json`
- [x] 8.2 Update `web/README.md`, the About text and the root README for the supervisor workflow, the cases builder and the new dependencies; run `uv run evals regression` and the agent tests to confirm nothing else changed, and confirm the model hash and the frozen packet results are untouched
- [x] 8.3 Run one live smoke check of a single case through the real service (a few cents) and record the built first-load JS size against the earlier figure in `web/README.md`

## Workflow follow-up

- Do not retrain, regenerate data or re-score the packet evals for this change.
- Archive the change after the PR is merged.
