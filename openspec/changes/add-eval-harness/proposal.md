# Proposal

## Why

Evals are the primary deliverable of this project, and they should come before the system they judge. The data is finished (a fictional disease, hidden ground truth, tagged edge cases, matched pairs, and the best score any system could reach), but nothing yet says what a correct answer looks like, how a system is scored, or what the numbers to beat are. Writing the evals first, in the way Anthropic recommends (specific and measurable success criteria, code-graded checks wherever possible, a reference solution, balanced sets, transcripts read by a person, capability evals kept apart from regression evals), turns the agent, the prompt and the fine-tuned model into things built to pass them, and keeps the frontier-model baseline honest.

## What Changes

- Add a **risk report contract**: the structured output every system under test must produce for a patient record (a probability, an uncertainty statement, the symptoms it read from the note, the data-quality warnings it raised, the lab values it relied on, a disclaimer, or a refusal). It is defined here and published as a JSON Schema, so the agent is later built to it.
- Add an **eval harness** in `evals/` (Python, Inspect AI): a system-under-test adapter (a record's input view in, a report out), trials with full transcripts, code-based graders for each category, aggregation with confidence intervals and minimum detectable differences, and a results format.
- Add **reference systems that need no API**: an oracle (knows the hidden rule, defines the ceiling), a floor (prevalence only) and a lab-only logistic baseline. They validate the harness and graders before any model is used, and give the numbers success targets are anchored to.
- Add **dev and test discipline**: a deterministic dev split carved from train (excluded from any training), `test` and `adversarial` scored only in explicit final runs, and a recorded count of how often each system version has seen them.
- Add **graders** for happy path (AUC, Brier, calibration), data quality (warnings against tags), borderline (stated uncertainty), consistency (matched pairs, repeated trials with pass^k), adversarial (prompt injection judged against the same record without the injected text), symptom reading, fabrication and scope markers.
- Add **bounded spend**: dry-run estimate, response cache and call and spend caps for API-backed systems, as in the note writer.
- Add a CI job that runs the harness tests and the regression subset with the code-only systems (no key, no spend).
- Record **success targets** (version 1) from the baseline runs, labelling each eval as capability or regression.

## Capabilities

### New Capabilities
- `risk-report`: the structured report a system must return for a patient record, its validation, and its safety content rules.
- `eval-harness`: how systems are run and graded, the reference baselines, the dev and test discipline, metrics and statistics, transcripts, spend bounds and result reporting.

### Modified Capabilities

None. Reading records uses the existing `synthetic-cohort`, `clinical-notes` and `llm-note-writing` data as it is. The dev split is a deterministic selection over existing train records, so no data file changes.

## Out of scope

- The frontier-model baseline itself (its prompt, its tuning on dev, its first headline numbers): the next change, `add-frontier-baseline`.
- The safety and scope dataset (treatment and dosing requests, real diseases, PHI-looking text) and any LLM-judged grading: a later change; this change only fixes the rule that an LLM grader needs a different model, a rubric with an "unknown" option and a recorded calibration.
- Tool-use evals (they need the agent), the fine-tuned rows, the agent, serving and deployment.
- A Harbor-based slice (possible later add-on); the adapter keeps the harness replaceable.
- Training: this change only provides the dev ids that training must exclude.

## Eval categories affected

Defines or enables all of them: happy path, data quality, borderline, consistency, adversarial, plus symptom reading and fabrication. Safety/scope has its grader rules but no data yet; tool use waits for the agent.

## Impact

- New `evals/` package depending on `data_gen` (to read records) and on Inspect AI (pinned). No change to `data_gen/` data or specs.
- New `.github/workflows` job for the key-free harness tests.
- Spend: none for this change's own runs (reference systems need no API); API-backed systems arrive with the next change, and the caps and estimate are built and tested here with a mock client.
