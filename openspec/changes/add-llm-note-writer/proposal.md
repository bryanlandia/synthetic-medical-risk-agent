# Proposal

## Why

Template notes from `add-synthetic-data-generator` are faithful but stiff, so models trained or tested on them will look better than they would on realistic documentation, and two realistic styles (narrative, AI-scribe) cannot be templated convincingly. Published results need notes that read like real documentation, with the same labeled ground truth. This change adds that, on top of the stable note plan.

## What Changes

- Add an LLM verbalizer in `data_gen/` that turns a note plan into prose for all four styles: terse, templated, narrative and AI-scribe. The plan, labels and ground truth are unchanged.
- Validate every LLM-written note against its plan: stated lab values by parsing, symptom polarity by an independent extraction pass. Failed notes are retried a bounded number of times and then excluded and counted.
- Cache every LLM result keyed by plan, prompt version and model, with a hard call or spend cap and a dry-run cost estimate, so reruns are free and the bill is bounded.
- Add paraphrase groups: several notes with different wording for the same patient, for consistency evals.
- Embed prompt-injection text from the existing catalog verbatim. The LLM never writes the injections.
- Record the note source (template or LLM), model and prompt version in the manifest.
- Produce the LLM-note versions of the three splits, to be used for all published numbers.

## Capabilities

### New Capabilities
- `llm-note-writing`: LLM verbalization of note plans, validation and exclusion of unfaithful notes, caching and cost bounds, paraphrase groups, and provenance of note source.

### Modified Capabilities

None. This builds on `clinical-notes` and `synthetic-cohort` (from `add-synthetic-data-generator`, which must be archived first) without changing their requirements.

## Out of scope

- Changing the scoring rule, record schema, split definitions or the note plan format.
- Training, agent and eval code. Retraining or re-evaluating on the LLM notes belongs to those changes.
- Serving, and any use of the LLM at inference time in the product.

## Eval categories affected

Unlocks realistic inputs for happy path, data quality, borderline and adversarial categories, and supplies the paraphrase groups for the consistency category.

## Impact

- New dependency on the Anthropic API (Haiku-class model) for dataset generation only. It spends money, so there is a call cap, a dry-run estimate, a committed cache, and a Console spend limit.
- The API key comes only from the environment.
- Larger committed artifacts (LLM-note datasets and the cache), checked by a size limit.
