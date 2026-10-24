# Design

## Context

Builds on `add-synthetic-data-generator`, which provides the record schema, splits, ground truth and a versioned note plan with a template renderer. This change plugs an LLM verbalizer into the plan-to-text seam. That change must be archived first. See proposal.md for motivation and the spec for requirements. The repo is public, so the API key lives only in the environment.

## Goals / Non-Goals

**Goals:**
- Realistic prose in four styles with the plan's ground truth and noise labels intact.
- Every accepted note verifiably faithful, with measured validator quality.
- Reruns free and spend bounded, so the repo reproduces without an API key.

**Non-Goals:**
- Bit-reproducible LLM output (we cache and commit it instead).
- Any change to the plan format, schema or splits.
- LLM use at product inference time.

## Decisions

**Anthropic API with a Haiku-class model, model id in config.** Cheap and fast for thousands of short notes. Alternative: a larger model, rejected for cost; the model id is recorded in the manifest so it can be swapped and the cache invalidated.

**Prompt per style, built from the plan only.** The prompt receives the plan facts (labs with units, symptom statements with polarity and hedge, noise instructions) and a style description, never the label, true probability or scoring rule, so notes cannot leak ground truth. Injection catalog text is inserted by code after generation (a placeholder marker the LLM must keep), not authored by the model.

**Two-part validation.** Lab values are parsed by code and compared to the plan within 1% after unit conversion. Symptom polarity is recovered by an independent extraction pass (separate prompt over the controlled fictional symptom vocabulary) and compared to the plan. Alternative: trust a self-reported claims list from the writer, rejected because it shares the writer's errors. Alternative: a pure lexicon with negation cues, rejected as brittle on narrative and scribe styles, though it is reused as a fast pre-check. The extractor is itself measured: at least 0.95 per flag on a hand-checked sample of 100 notes covering all styles, and a lower score blocks the real run.

**Bounded retries, then exclude.** Up to a configured number of attempts per note; records still failing are excluded and counted. Exclusion could bias the sample toward easy cases, so the manifest reports exclusion rate per style and per noise type.

**Cache keyed by plan hash, prompt version, model id and sampling seed.** Committed with the datasets so a fresh clone reruns with zero calls. Paraphrase index is part of the sampling seed.

**Cost control.** A hard `--max-llm-calls` cap, a dry-run `estimate` command that counts uncached calls, and an Anthropic Console monthly spend limit. Rough budget: about 5,400 notes plus extraction calls and retries, on the order of ten to twenty dollars, confirmed by the dry run before any paid run.

**Paraphrase groups** reuse the plan with different sampling seeds; ground truth is copied from the plan, never re-derived.

## Risks / Trade-offs

- [LLM rewrites a value or drops a symptom] → Two-part validation, bounded retries, exclusions counted.
- [Extractor shares the writer model's blind spots] → Different prompt and a measured hand-checked sample; threshold blocks the real run.
- [Exclusions bias the dataset toward easy notes] → Report exclusion rates by style and noise type; investigate before publishing numbers.
- [Prose still carries learnable artifacts or LLM tics] → Mix styles and sampling seeds; training and evals should test generalization across styles (held-out style), handled in those changes.
- [Cache or datasets grow large or leak a key] → Size check and key-pattern scan in the integration tasks.
- [Provider model deprecation changes outputs on regeneration] → Model id and prompt version are in the cache key and manifest; committed cache preserves the published data.

## Open Questions

- Maximum retry count and the paraphrase group size k. Defaults: 3 attempts, k = 3, adjustable in config without touching the spec.
