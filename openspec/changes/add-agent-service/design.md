# Design

## Context

See proposal.md for why. What the design rests on, all observed in the repository or the Strands documentation:

- The committed classifier is deterministic and fast: `risk_model.load(...).report(view)` returns a complete, validated report in under a millisecond, with no network. The reader already extracts the lab values a note states (`risk_model.labvalues`), with their units and decimals, and the data-quality checks already compare them with a panel.
- `risk_model` lives inside the `training/` distribution, which depends on scikit-learn and MLflow. A service image should carry numpy only.
- Strands lets a tool read **`ToolContext.invocation_state`**, request-scoped data supplied by the caller and "which the model doesn't control", while ordinary tool parameters are what the model chooses. The Anthropic provider is `strands-agents[anthropic]` (`strands.models.anthropic.AnthropicModel`, with `max_tokens` and `client_args`), and a result reports accumulated token usage.
- The project context fixes the shape: FastAPI plus Strands on a Python host, Claude as the orchestrator, a shared-secret header from a web proxy, and spend protection (rate limit, input caps, spend limit). Evals are meant to target the running API.
- The frontier-baseline experiment showed what goes wrong when a model handles the numbers: invented fields, a lab listed with a value that the panel does not have, `uncertain` flags that disagree with the probability.
- A legitimate note can contain the words "medications and allergies reviewed", so a keyword filter on the input for treatment words would refuse real records.

## Goals / Non-Goals

**Goals:**
- A request path where the numbers in the report can only come from the user's own text, through deterministic code, and cannot be altered by the model or by text inside the message.
- Every request ends in either the classifier's report or a fixed decline; free model prose is released only after a score, and only after a check against the report.
- Bounded abuse and cost: authentication, size, rate and daily-spend limits that act before the model is called.
- The agent scored by the same graders as the other systems, plus checks specific to tool use and scope, with guard tests that need no key.

**Non-Goals:**
- Web page, proxy, container and deployment; conversation memory; structured JSON input; streaming.
- Making the orchestrator smarter. Its job is routing and plain-language wording, and the design assumes it can be wrong.

## Decisions

**1. `risk_model` becomes its own project.** `risk_model/` at the repository root holds the inference package (numpy only, its own `pyproject.toml`, hatch build). `training` and `agent` depend on it by path. The committed model files stay in `training/model/` (training writes them); the agent loads them from a configured directory and the later container build copies the two JSON files. The move is behavior-preserving, and the check is mechanical: the model hash, every training test and every evals test give the same results, and the byte-identical-export test still passes. Alternative: have the agent depend on `training` with its heavy dependencies, which would put scikit-learn and MLflow in the image; or copy the package, which would let two copies drift.

**2. Intake is deterministic code that reads stated values.** `risk_model.intake.view_from_text(text)` builds the view: for each lab, the first value the message states next to the lab's name or abbreviation (read with the existing value reader, converted to the usual unit), else null; the note is the whole message. Everything downstream is existing code: a stated alternate unit becomes a unit-mismatch warning, a later disagreeing value a contradiction, a missing lab a missing-value warning, an impossible value an impossible-value warning. The model never types a number. Alternative: have the model extract the panel into tool arguments; rejected because it reopens transcription errors and injection steering of the values, and would need its own extraction eval. The cost of the deterministic choice is coverage: wording the value reader does not know ("VLI is 108") leaves the lab null. Two things limit the harm: the reply lists the labs that were read from the message, so a user can see what the score used, and the tests include handwritten wording variants.

**3. The scoring tool takes no value arguments.** `score_message()` has no parameters the model can fill with data. The service passes the user's exact message in `invocation_state` for the call (`agent(prompt, invocation_state={"message": ...})`), and the tool reads it there, runs intake and the classifier, and returns the report unchanged. The model's only power is whether to call it. Alternative: a tool with `message` or `panel` parameters and a check that they equal the user's text; this works but moves the trust boundary into a comparison that has to be right, where the no-argument tool has nothing to compare.

**4. Two terminal tools; prose only after a score.** The agent has `score_message()` and `decline(reason)` where the reason is the report contract's closed set. The system prompt tells it to call exactly one. A decline returns a fixed message per reason; a request where the model calls neither becomes an out-of-scope decline with the fixed message; and the model's own words are released only as the reply to a scored message. This keeps unsafe or off-topic prose from the model off the wire by construction, and makes refusals a countable event for the evals. A second call of either tool returns an error result and is counted, bounding the loop; the model is also limited to two invocations per request (one to choose the tool, one to write the reply), so a request costs at most two Haiku calls.

**5. The output guard and the template.** After a score, the reply is checked in code: every number with a percent sign or a probability-like decimal is matched to the report (within rounding of the digits written), the text must not match the medication, dose, treatment and real-disease denylist (a data file kept in the agent project and checked by a test to contain everything in the evals' content check), and it must be at most 1,200 characters. A pass releases the model's reply; a fail releases a template filled from the report (probability, the uncertain flag, the symptom readings, the warnings, the evidence strings, and the list of labs read). In both cases the code appends the fixed disclaimer and the synthetic-data notice. `reply_source` says which was used, so the evals can report the fallback rate instead of hiding it.

**6. Limits act before the model.** A small ordered set of checks runs before the agent is built: shared secret (401), size and shape (413, 422), rate (429), then daily spend (503). The shared secret is compared in constant time. The rate limiter is a sliding window held in memory per process (10 a minute, 200 a day per client): the deployment is one instance, and the limiter's documentation says so. Client identity is the address the platform gives the process; behind the web proxy, a request that carries the valid secret may name the visitor's address in a header and the limiter trusts it, because only the proxy has the secret, and a request without a valid secret is rejected before the limiter. Spend is a SQLite file holding the day's total; each request adds the cost computed from the provider's reported token usage and a pinned price table, and a restart reads the total back. A request that starts under the cap may finish and push the total slightly over it; the cap is a ceiling on starting work. Token ceilings: `max_tokens` 600 on each call, and the message cap of 6,000 characters bounds the input.

**7. The orchestrator is Haiku 5.5 with no sampling parameters.** The model id and prices are pinned in configuration. The system prompt states the task (a risk-scoring assistant for a fictional syndrome), the two tools and when to use each, that it must never give medical advice, name a medication, or discuss real diseases or treatments, that text inside the message is data and never instructions, and, for the reply, that it must restate the report's numbers exactly, mention which findings drove the score, say what was missing, and stay under 150 words. The prompt is a file with a hash recorded in the logs, so a change is visible. There is no prompt-iteration budget in this change; it is written once, tested on the scope set, and fixed.

**8. A scripted model for tests and CI.** A deterministic stand-in for the orchestrator picks the tool from simple rules on the message, writes a reply from the report, and can be told to misbehave (wrong number, no tool, two tool calls, extra arguments, prose). It makes every guard testable without a key, and is refused when the environment says production. If Strands' model interface makes a stand-in heavy, the same effect comes from a fake Anthropic client handed to `AnthropicModel`, which is the fallback.

**9. The eval adapter renders records and calls the service.** `evals` gets an `agent` system. A fixed renderer turns a view into the message: a "Labs:" list (lab name, value, usual unit; null labs omitted) and a "Note:" section with the note text. The adapter posts it with `httpx` and returns the response's report, or a marker that the graders count as an invalid report. A launcher starts the service on a free port with the scripted model for CI and tests, or with the real key for the owner-run evals; for eval runs the rate limit and daily cap are raised by explicit environment variables, which the service refuses in production and logs at start. The rendering is the single place that says what a "message" is, and the text-path-versus-structured-path agreement check uses it.

**10. Tool-use and scope grading.** The service's response is enough to grade tool use: `declined`, the decline reason, `report` null or not, `reply_source`, and a tool-call count in `usage`. A committed prompt set (`evals/datasets/agent_scope.jsonl`, about 70 prompts) gives each prompt's category and expected behavior: treatment requests, real-disease questions, personal-data-looking input, other chat, injected instructions, and legitimate records whose notes mention medications or a real symptom word, which must be scored. Graders are plain functions like the others. Targets are in the delta spec and are derived from the need, not from a baseline: a safe demo must refuse nearly all and over-refuse almost none.

**11. Logging.** One JSON line per request with the fields in the spec and the prompt hash, written through the standard logger; a test searches the log of a served request for a word from the message. Nothing from the message, reply or key is written.

**12. Versions and secrets.** `strands-agents[anthropic]`, FastAPI, uvicorn and httpx are pinned; `ANTHROPIC_API_KEY`, `AGENT_SHARED_SECRET`, `AGENT_DAILY_BUDGET_USD`, the limits and `AGENT_ENV` come from the environment only; no key or URL is in any file.

## Risks / Trade-offs

- [The model ignores the tool contract, loops, or writes a wrong number] → one tool call and two invocations at most, the output guard with the template, and the fallback rate reported by the evals.
- [Free-text wording the intake does not read leaves labs null and lowers the score's quality] → the reply lists the labs read; the missing labs appear as warnings; handwritten-variant tests; the text-versus-structured agreement check on dev. Widening the forms is a follow-up that does not change the contract.
- [Haiku refuses legitimate notes because they mention medications] → legitimate-looking prompts are in the scope set with a hard over-refusal target; the system prompt says notes may mention such words.
- [Prompt injection in the pasted text] → the scored values come from code; the injection grader runs on the adversarial pairs through the agent; the reply guard stops echoed instructions with treatment content; refusals cannot be turned into free prose.
- [Spend: a loop of requests from many addresses] → the daily cap is a hard stop, independent of the rate limit.
- [In-memory rate limiting is per process] → a single instance by design, stated in the docs; a shared store is a deployment-time change if more instances are added.
- [Strands behavior changes between versions] → exact pin; an integration test with the scripted model in CI; the live evals are owner-run before a release.
- [Moving `risk_model` breaks paths] → the move is its own first task group, finished and verified (hash, tests) before any agent code.

## Migration Plan

Group 1 moves `risk_model` and updates `training`; rollback is reverting that commit. Everything else is new directories. The service has no state except the spend file.

## Open Questions

- Exact limits (messages per minute, daily cap) are defaults chosen for a demo; they are configuration and can be tuned at deployment without changing a spec.
- Whether the web page streams the reply is a question for the web change; this service returns one JSON body.
