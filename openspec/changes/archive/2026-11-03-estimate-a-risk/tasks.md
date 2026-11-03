# Tasks

## 1. Estimate and message template in `risk_model`

- [x] 1.1 Add an `estimate(labs, symptoms)` function that validates inputs (eight labs as a value in the plausible range or null, five symptoms in three states, no extras) and returns the probability, the band, and the per-input breakdown with its starting point; verify with unit tests that the probability equals `RiskClassifier.probability` to 1e-9 and that bars plus starting point equal the score to 1e-6 over 500 seeded input sets
- [x] 1.2 Cover the not-done lab (the missing-indicator column goes into that lab's bar) and the symptom `possible` column in the breakdown, and verify the grouped bars match the per-feature `contributions` summed by input
- [x] 1.3 Add the fixed message template (a `Labs:` list in the evals' documented format, then a `Note:` of symptom sentences, each lab at a fixed number of decimals) and verify with tests that the same inputs give identical text, a not-done lab is absent from it, and the text carries nothing but the inputs
- [x] 1.4 Add the round-trip test: all 243 symptom combinations by 200 seeded lab settings (some labs not done), plus every lab at its lowest, highest and not done, read back through intake and the note reader; verify every reading equals its input and every probability is within 0.001 of the estimate. If a wording fails, change the template, never the reader; run `uv run pytest -q` in `risk_model/`

## 2. Service route

- [x] 2.1 Add `POST /estimate` to the agent service with the shared-secret check, a body-size cap, strict input validation (422 on any bad or extra field) and the response fields from the spec; verify with scripted-model tests that no model is called, bad inputs get 422, and a wrong secret gets 401
- [x] 2.2 Give `/estimate` its own rate-limit counter (120 a minute, 5,000 a day; its own key prefix in the shared store) that neither uses nor consumes the assistant's allowance or spend; verify with tests of the 121st request, of 100 estimates followed by an analyze request, and of the shared-store prefix
- [x] 2.3 Log an estimate request's id, status and duration only; verify with a log test that no input value or message text appears
- [x] 2.4 Extend the service's health and smoke checks to cover one estimate and verify `uv run agent smoke` against the scripted service; run `uv run pytest -q` in `agent/` and `uv run evals regression`

## 3. Web route and shell

- [x] 3.1 Add the `/api/estimate` server route that adds the secret and visitor address, whitelists the response fields, maps errors through the existing messages, and never exposes the service address; verify with route tests (extra upstream field dropped, 429 mapped, no secret or address in the build output)
- [x] 3.2 Restructure `Demo.tsx` into two scenarios and Behind the demo (model card and About only), retitle the page VK-Check with per-scenario subtitles, keep the queue as the default view and its intro and help in the queue only; verify with shell tests that the first screen is the queue, the menu lists no assistant view, and the title and fictional notice show in each view
- [x] 3.3 Update the existing Playwright tests that reached the assistant through Behind the demo; verify the whole suite still passes

## 4. Estimate a risk scenario

- [x] 4.1 Build the controls (eight lab sliders with a not-done state, five three-state symptom toggles, stepped to the template's decimals) and Reset, opening on a committed borderline patient with its estimate precomputed in a content file; verify with a stale-file test that the precomputed estimate matches the service and lies in 0.4 to 0.6, and with Playwright that Reset restores every input
- [x] 4.2 Add the debounced estimate client (at most one request per 150 ms, stale answers dropped, 429 keeps the last estimate and says to slow down, the waking-up state after 1.5 s); verify with tests that a burst of 50 changes sends few requests and that a late old answer never replaces a newer one
- [x] 4.3 Show the dial, band and breakdown bars; verify with Playwright that moving a lab changes the estimate, that a not-done lab shows no value, and that the bars' text and sum agree with the estimate
- [x] 4.4 Add the introduction, the invented-patient and fictional notices and the no-advice wording; verify with a text test for the excluded words and any treatment name, and that the queue's introduction does not appear here
- [x] 4.5 Mount the collapsed free-text box inside the scenario with its existing no-history behaviour; verify it is collapsed on open, absent from Behind the demo, and sends one independent message

## 5. Send to the assistant and guardrail controls

- [x] 5.1 Add "send this patient to the assistant" using the message the route returned, and show the assistant's number beside the dial's; verify with scripted-agent tests that the numbers agree within 0.001 and that a decline shows its reason and no number
- [x] 5.2 Add the hidden-instruction, treatment-question and off-topic controls with fixed strings next to the existing examples, each reusing the injection callout's honesty rule (a low result that cannot show the instruction was ignored is said so); verify with scripted-agent tests for an unchanged number under injection, a decline for the treatment question, and a decline for off-topic
- [x] 5.3 Verify that using the scenario does not touch saved queue progress, writes nothing to storage, and loads no queue case; verify with a Playwright test that saved progress is identical afterwards

## 6. Evals, docs and integration

- [x] 6.1 Add to the agent evals a check that the generated message for seeded patients is scored by the assistant within 0.001 of the estimate, with and without the fixed injection string, and run `uv run evals run --system agent --split dev` with the scripted model; verify existing metrics are unchanged and the new check passes
- [x] 6.2 Update `web/README.md`, `agent/README.md` and the About text for the new scenario and the `/estimate` route (the About text keeps its fictional and no-advice statements); verify the documented commands run as written and the About checks still pass
- [x] 6.3 Run `npm test` and `npm run typecheck` in `web/`, restore `web/next-env.d.ts` and `web/tsconfig.json`, and run `uv run evals regression`; verify everything passes and the model hash and cases file are unchanged

## Workflow follow-up

- Do the README restructure first, as agreed in the exploration; the README should describe the two scenarios.
- Archive the change after review, and verify `openspec/specs/risk-estimator/spec.md` exists with its Purpose.
