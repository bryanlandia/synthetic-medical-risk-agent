# Proposal

## Why

The project's value is rigorous evaluation, and an evaluation of note reading is only as meaningful as the notes. The template notes from `add-synthetic-data-generator` are faithful but unrealistic: five fixed symptom phrases, a handful of boilerplate frames, and no variety of documentation setting. A system that only reads one rigid format has shown nothing, so the project needs notes that mimic several real clinical documentation settings, with the same labeled ground truth, so evals can slice results by setting, hold settings out, and compare the same patient across settings.

The goal is a trustworthy measurement, not impressive scores: results may be modest, and that is acceptable as long as the evaluation is sound.

## What Changes

- Add an LLM verbalizer in `data_gen/` that writes notes in four clinician-authored documentation settings: `shorthand`, `ehr_template`, `ai_scribe` and `copy_forward`. Patient-authored text (portal messages) is out of scope.
- Extend the note plan to version 2 (additive): symptom phrase sets so wording varies, lab flags and reference ranges computed by code, and per-setting completeness and stale-value rules.
- Validate every LLM note against its plan (tolerant lab parsing plus an independent symptom extraction pass), reject notes that state a diagnosis, risk or treatment, retry boundedly, and exclude and count failures.
- Add a human realism gate before the paid run: the owner blind-rates 20 notes per setting, and each setting must reach at least 80% plausible. The same 80 notes measure extractor accuracy.
- Add matched-pair groups: a configurable number of test patients written in all four settings, for consistency and held-out-setting evals.
- Cache every LLM result with a hard call or spend cap and a dry-run cost estimate.
- Embed prompt-injection text from the existing catalog verbatim; the LLM never writes injections.
- Record note source, model, prompt version, settings and pair groups in the manifest.
- Produce the LLM-note versions of the three splits for all published numbers. The template dataset stays as test fixtures.

## Capabilities

### New Capabilities
- `llm-note-writing`: LLM verbalization of note plans in documentation settings, validation and exclusion of unfaithful notes, the realism gate, matched-pair groups, caching and cost bounds, and provenance.

### Modified Capabilities
- `clinical-notes`: the "Note styles" requirement changes. The reserved `narrative` and `ai_scribe` names are replaced by the four LLM documentation settings, and a style unsupported by the configured note source is rejected.

## Out of scope

- Patient-authored text (portal messages) and any non-clinician setting.
- Clinician diagnoses, risk impressions or treatment statements in notes.
- Changing the scoring rule, split definitions or any ground-truth field. Schema and plan changes are additive only.
- Training, agent and eval code, including the held-out-setting experiments themselves. This change only provides the data and the `setting` and pair fields they need.
- Serving, and any use of the LLM at inference time in the product.
- Clinical validation: the realism gate measures plausibility to the project owner, not accuracy against real records.

## Eval categories affected

Unlocks realistic inputs for happy path, data quality, borderline and adversarial categories. Matched pairs supply the consistency category (same patient, different documentation setting), and the `setting` field enables per-setting and held-out-setting breakdowns.

## Impact

- New dependency on the Anthropic API (Haiku-class model) for dataset generation only. Roughly 6,000 notes plus extraction calls, retries and an 88-note pilot; the dry-run `estimate` confirms the cost before any paid run. A call cap, a committed cache and a Console spend limit bound it.
- A small additive change in `data_gen/` code: plan version 2 (symptom phrase sets, lab flags, setting rules) and schema version 2 (optional `pair_group`). The committed template dataset keeps validating.
- Human effort: the owner reviews one blind sheet of about 88 notes.
- The API key comes only from the environment. Larger committed artifacts (LLM-note datasets and cache) are checked by a size limit.
