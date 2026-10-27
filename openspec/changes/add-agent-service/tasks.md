## 1. Split the inference package out of `training/`

- [x] 1.1 Move `training/src/risk_model/` and its tests into a new `risk_model/` project (numpy only, pinned, hatch build, README with the synthetic-data notice); make `training` depend on it by path; keep the committed model files in `training/model/` and give `risk_model.load` an explicit directory argument and a `RISK_MODEL_DIR` default. Test that `import risk_model` loads no scikit-learn, MLflow, anthropic, pandas, evals or data_gen.
- [x] 1.2 Verify the move changes nothing: the model hash in `training/model/manifest.json` is the same, `uv run training train` reproduces byte-identical files, and the full `training/` and `evals/` suites and the fast regression give the same results as before. Eval: model hash unchanged and zero new test failures.
- [x] 1.3 Update `AGENTS.md` and the READMEs for the new layout.

## 2. Text intake

- [x] 2.1 Implement `risk_model.intake.view_from_text`: eight panel entries, first stated value per lab converted to the usual unit, null otherwise, the note equal to the whole message, nothing else. Test: no labs, some labs, labs in alternate units, a repeated lab, an impossible value, a lab named without a number, and determinism.
- [x] 2.2 Test that intake passes warnings through honestly: alternate unit gives `unit_mismatch`, a disagreeing repeat gives `contradiction`, a missing lab gives `missing_value`, an impossible value gives `impossible_value` and the probability of the lab-missing record.
- [x] 2.3 Add the evals' message renderer (`evals/src/evals/messages.py`): a "Labs:" list and a "Note:" section from a view. Test that it contains no ground-truth field and that every non-null panel value is written in it.
- [x] 2.4 Property-style test over 500 dev records: every non-null panel value from intake is a number written in the message. Eval: none is absent.
- [x] 2.5 Agreement check on dev: score the 500 dev records through the structured path and through render, intake and the classifier. Eval: at least 95% within 0.001; list the exceptions with the lab or reading that differs and write them to `evals/results/agent/intake_agreement.md`.
- [x] 2.6 Handwritten wording variants (at least 20 messages in different styles: abbreviations, prose, a list, mixed units): test what is read and what is left null, and record in a file the wordings that are not read.

## 3. Service skeleton and guards

- [x] 3.1 Create the `agent/` project (Python 3.12, uv, pinned FastAPI, uvicorn, httpx, `strands-agents[anthropic]`; `risk_model` by path) with configuration from environment variables, fail-closed startup (no shared secret, no key without the scripted model, scripted model refused in production, relaxed limits refused in production) and `GET /healthz`. Test each startup failure and that no error prints a secret.
- [x] 3.2 Implement the request checks in order: shared secret (constant-time, 401), shape and size (422, 413, control characters removed), rate limit (10 a minute and 200 a day, `Retry-After`, 429), daily spend (503). Test each path with a counting stand-in for the model and assert the model is not called on any rejection.
- [x] 3.3 Implement the spend counter in SQLite with a pinned price table: cost from reported token usage, a total that survives restart, a day boundary in UTC. Test the cap, the restart and the day roll-over with an injected clock.
- [x] 3.4 Implement structured logging of the fields in the spec without message, reply, secret or key. Test by searching the log of a served request for a word from the message, for the secret and for the key.

## 4. The agent

- [x] 4.1 Write the system prompt file and record its hash in the logs. Implement the Strands agent with `AnthropicModel` (Haiku 5.5, `max_tokens` 600, no sampling parameters), the `score_message` tool that reads the message from `invocation_state`, and the `decline(reason)` tool with the report contract's reasons. Test that the tool has no parameter carrying values or text.
- [x] 4.2 Implement the scripted model (rule-based tool choice and reply from the report, with switches to misbehave) and the production refusal. Test the scripted model through the whole service.
- [x] 4.3 Enforce one tool call and two model invocations per request; a second call returns an error result and is counted in `usage`. Test with a scripted model that calls the tool twice, calls neither tool, and passes extra arguments naming other labs or text.
- [x] 4.4 Implement the decline path: fixed message per reason, `declined` true, no report, and "no tool called" treated as an out-of-scope decline. Test each reason and that no model prose is released on a decline.
- [ ] 4.5 Run the whole service against the real Anthropic API on 5 hand-picked messages (owner-run, a few cents), check the tool choice and the replies, and record the outputs for the design notes.

## 5. Output guard

- [x] 5.1 Implement the denylist data file (medications, doses, treatment instructions, real disease names) and a test that it contains everything the evals' content check forbids. Implement the reply checks: quoted probabilities and percentages match the report within rounding, no denylisted content, at most 1,200 characters.
- [x] 5.2 Implement the template reply from the report (probability, uncertain flag, symptom readings, warnings, evidence, labs read) and append the disclaimer and synthetic-data notice by code in both cases. Test a wrong number, a medication name, an overlong reply, a missing disclaimer, and a good reply that passes through.
- [x] 5.3 Test the injection path end to end with the scripted model: an addendum asking for a result does not change the report or the tool, and a model that repeats the instruction in its reply is replaced by the template when the reply is unsafe.

## 6. Evals for the agent

- [x] 6.1 Add the `agent` system to the evals CLI: render a record, post it with `httpx`, return the response's report or a failure marker the graders count as an invalid report; add the service launcher for the scripted model and the real key, with explicit relaxed limits for eval runs. Test through the harness against the scripted service that reports validate and that a 503 is graded as an invalid report.
- [x] 6.2 Write the scope prompt set (`evals/datasets/agent_scope.jsonl`, about 70 prompts: treatment requests, real-disease questions, personal-data-looking input, other chat, injected instructions, and legitimate notes that mention medications) with each prompt's expected behavior. Test its format and that every category is present.
- [x] 6.3 Implement the tool-use and scope graders (scoring tool used once on records, decline rate and right-reason rate, over-refusal on records and legitimate prompts, reply consistency with the report, fallback rate) with their targets, and add them to the summary. Test each grader against hand-made responses, including an over-refusal and a wrong number.
- [x] 6.4 Add the guard tests to the fast regression subset (scripted model, no key, no network): every status path, the one-call limit, the output guard and the log check. Eval: the regression passes and fails if any guard is disabled.
- [x] 6.5 Add a keyless `evals estimate --system agent` for the live runs (calls, tokens and cost for dev, the scope set, `test` and `adversarial`) with a spend cap per stage as the frontier baseline has.
- [ ] 6.6 Owner-run: dev run of the agent on Haiku, the scope set, then `test` and `adversarial` once each with `--final` and the three-trial consistency run; compare with the classifier using `evals compare`. Eval: fabrication 0, safety 1, parse 0; tool-use and scope targets from the spec; report each miss with 10 failing transcripts read.

## 7. Documentation and validation

- [ ] 7.1 Write the agent README (endpoint, environment variables, limits, how to run locally with the scripted model and with a key) and a short design note on what the orchestrator adds and costs compared with the classifier alone; update `AGENTS.md` and the evals README headline table.
- [ ] 7.2 Run the full test suites for `risk_model/`, `training/`, `agent/` and `evals/`, the fast regression and `openspec validate add-agent-service --strict`.
