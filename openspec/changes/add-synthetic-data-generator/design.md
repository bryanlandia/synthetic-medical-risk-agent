# Design

## Context

Greenfield repo; `data_gen/` is empty. Downstream changes (training, agent, evals) consume this change's output, so the record schema, split layout and note plan format are the contract. See proposal.md for motivation and the specs (`synthetic-cohort`, `clinical-notes`) for requirements. Notes here are rendered from templates. LLM-written prose is a separate follow-up change (`add-llm-note-writer`) that consumes the same note plan. The repo is public, so nothing secret can live in committed files.

## Goals / Non-Goals

**Goals:**
- Fully deterministic, offline generation from a committed seed: no API key and no network.
- One schema shared by data_gen, training and evals, validated at write time.
- Noise and adversarial content decided by the generator, so every defect is labeled by construction.
- A stable, versioned note plan that both the template renderer and the later LLM writer consume.

**Non-Goals:**
- LLM-written prose, caching, spend caps and paraphrase groups (follow-up change).
- Narrative and AI-scribe styles (follow-up change).
- Hiding the scoring rule from repo readers. "Hidden" means hidden from models, the agent and training inputs; the rule lives in `data_gen/` only and is not imported by `training/` or `agent/`.
- Realism of the fictional physiology.

## Decisions

**Python 3.12 managed by `uv`, pinned in `pyproject.toml` and a lockfile.** Pydantic v2 models define the record schema. Alternative: dataclasses or JSON Schema only. Pydantic gives validation plus JSON Schema export for evals and the web sample-patient buttons. Note: the machine's default `python3` is a broken pyenv 3.6, so `uv` is also the way to avoid it.

**Randomness via numpy `SeedSequence.spawn` with one child stream per concern** (features, labels, noise plan, split assignment, adversarial cases, template choices). Adding a noise type or changing templates then never shifts the features or labels. Alternative: a single RNG, rejected because any change reorders every later draw.

**Scoring rule: logistic over standardized labs plus symptom flags, with a few interaction terms.** Coefficients are config in `data_gen/`, the intercept is calibrated by search to hit target prevalence. True probability is stored per record. The rule takes structured ground-truth features only (spec requirement). Alternative: tree-based rule, rejected because logistic gives a clean probability for Brier and reliability analysis.

**Two views of every record: model input and ground truth.** The input view is the lab panel plus the note; the ground-truth view holds symptom flags, true probability and label. Symptoms reach models only through the note, so classifier and agent input is labs plus note text. Alternative: expose flags as structured fields, rejected because the note would then be decoration and negation and hedging could not be tested. Flags remain in the record because the scoring rule needs them.

**Plan, then render.** The generator builds a versioned note plan per patient (which labs to state, units, how each symptom flag is stated, negated or hedged, note style, contradictions, injection text, tagged by construction). A template renderer turns the plan into text for the terse and templated styles. Because the generator wrote the words, faithfulness is true by construction, and a parse-back test confirms it. The plan-to-text seam is where the follow-up change plugs in an LLM verbalizer for richer styles. Alternative: have an LLM add noise freely, rejected because labels would be unreliable. Injection text comes from a fixed versioned catalog.

**Train / random-test assignment is stratified by label**, using a seeded permutation within each label class, so prevalence matches between the two splits by construction (an unstratified split misses the 0.02 prevalence tolerance about one run in five at 4,000 / 1,000). Lab-mean balance is left to chance: its tolerance (0.1 SD) is exceeded by roughly 3% of seeds at these sizes, so the default seed was chosen from a seed that satisfies it, and `validate` checks it.

**Splits assigned from a per-patient stream, adversarial records generated separately** by case-type generators (borderline is rejection-sampled to true probability 0.4-0.6) so the quota of at least 50 per type is exact. Patient IDs are derived from seed and index, so cross-seed collisions are avoided by including the seed in the ID.

**Output: JSONL per split plus `manifest.json`** (seed, generator version, plan version, config hash, counts, realized prevalence, noise and style rates, Bayes ceiling). Alternative: Parquet, rejected for diff-ability and because datasets are small.

**Generated datasets are committed (about 10 MB at default sizes, capped at 15 MB by a test).** They are byte-reproducible from the seed in a few seconds, so the repo needs no API keys; committing them is a convenience and could be dropped if repository size matters.

## Risks / Trade-offs

- [Models trained or tested on template notes look better than they would on realistic prose, because template notes are easy to read and have learnable artifacts] → Template data is for development and CI only; published numbers require the LLM-written notes from the follow-up change, and the README must say so.
- [Symptom signal lives only in prose, so a weak note style makes the task unlearnable] → Style mix and hedge rates are config, and the manifest reports the Bayes ceiling both with full flags and with note-recoverable flags.
- [Rule too easy or too noisy, making later results uninformative] → Report a Bayes-optimal baseline (the true-probability AUC and Brier) in the manifest, so fine-tuned models can be compared with the ceiling.
- [Schema or plan format churn breaks the follow-up change] → Version the schema, the plan and the generator; downstream code asserts the versions.
- [Committed datasets grow or leak something] → Size check; notes are scanned for identifier-shaped strings before commit.
- [Injection catalog is stale or too narrow] → Catalog is data, versioned, and extendable without code changes.
- [Public repo shows the rule] → Accepted; models and the agent never receive it.

## Open Questions

- Final dataset sizes (train, test, adversarial). Defaults: 4,000 / 1,000 / about 400, adjustable in config without touching specs.
- Which text encoder or prompt format the classifier uses for lab panel plus note. Decided in the `model-training` change; the input view defined here does not change.
