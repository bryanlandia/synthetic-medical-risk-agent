## 1. Policy and criteria in `risk_model`

- [x] 1.1 Add the fictional policy file (wording for C1 to C6, lab list, illustrative notice) and a loader; verify with a test that it names no coefficient and states it is fictional
- [x] 1.2 Implement `criteria` (C1 and C2 three-valued logic, C3 to C6 from answers, evidence ids and values as written); verify with unit tests for every scenario in the spec: two high labs, one high plus one unreported, cannot be met, alternate unit, impossible value, hedged and absent tremor, nothing answered, malformed answers rejected
- [x] 1.3 Implement the gap list (one per unknown criterion, what would settle it, never altering a value); verify gaps match unknown criteria one to one and `labs_used` values are unchanged
- [x] 1.4 Implement the summary verifier and the fixed-template summary; verify with tests for a faithful draft, a missing or unknown citation, an invented number or unit, a status contradiction, banned and coaching vocabulary, and a paraphrased verdict; run `uv run pytest -q` in `risk_model/`

## 2. Packet endpoint in `agent`

- [x] 2.1 Add `POST /packet` with the closed request body and response model, reusing the secret, size, rate-limit and spend guards and the decline path; verify with scripted-model tests for 401, 413, 422 on extra fields and attestation keys, 429, 503 at the cap, and a treatment-question decline
- [x] 2.2 Add the no-tool summary step (prompt, JSON output, token cap, timeout), the verifier fallback and the failure counter, with the prompt hash in `/healthz`; verify with a scripted model that a bad draft yields the template with `summary_source` `template`, and a model failure still returns the table and gaps
- [x] 2.3 Add the content-free log line and spend accounting for the summary call; verify no message word appears in logs and the daily total rises by the reported cost
- [x] 2.4 Verify the injected-addendum case leaves the criteria table unchanged and the model input holds only the table and evidence; run `uv run pytest -q` in `agent/` and `uv run evals agent-scope` to confirm no existing guard result changes

## 3. Web packet view

- [x] 3.1 Add the server route and whitelisted types/forwarding for `/packet`; verify with `forward` tests that extra fields are dropped and the secret and address never reach the page
- [x] 3.2 Build the packet view in `ChartTab`: C3 to C6 controls starting not yet answered, the criteria table with cited values, gaps, summary with source, the clinician-only rationale field (not sent to the service), sign-off lock, copy and print, and the synthetic banner; verify with Playwright tests for default answers, one request with the stored message, empty rationale, locked state after sign-off, banner in print, and absence of "approved", "denied", "eligible", "qualifies", "confidence interval" and any value-editing control
- [x] 3.3 Test that the page's criteria wording equals the policy file; update `web/README.md`; run `npm test` and `npm run typecheck`

## 4. Evals

- [x] 4.1 Write seeded attestation fixtures for the dev, test and adversarial ids covering yes, no and unanswered for each of C3 to C6; verify they regenerate byte-identically
- [x] 4.2 Add the independent reference computation and the graders (criterion accuracy per criterion, gap recall and precision, citation grounding, fabrication and fallback rates, safety and banned-vocabulary); verify each returns the expected value exactly on hand-built sets, and add them to `uv run evals regression`
- [x] 4.3 Build the adversarial packet set (addenda, asserted history, attestation-from-note attempts, wording requests, paraphrased verdicts, treatment questions) and its resistance grader; verify the scripted system resists and a deliberately weak stub fails
- [x] 4.4 Add the packet system to the harness with the dev, test and adversarial stages, the dev-first and freeze rule, ledger entries and `--force` warning; verify a test run without a dev run is refused and the ledger records one look each

## 5. Run and report

- [x] 5.1 Run `uv run evals estimate` for the packet, then iterate the summary prompt on the dev split with Haiku (at most 5 versions) and record the raw fabrication and fallback rates; verify the shown-summary grounding is 1.0
- [x] 5.2 Read failing dev transcripts for each missed target and record what was read; then freeze and run test and adversarial once each
- [x] 5.3 Write the packet results summary with the synthetic-data notice, per-criterion accuracy, intervals and target labels; verify it is complete (no unread failed grader)
- [x] 5.4 Update `agent/README.md`, the root README and the About text for the packet (fixed pipeline, one model step, verifier, no verdicts), run the fast regression subset and `npm test`, and confirm the model hash is unchanged

## Workflow follow-up

- Do not retrain or regenerate data for this change.
- Archive the change after the PR is merged.
