# Design

## Context

Builds on the archived `add-synthetic-data-generator`, which provides the record schema, splits, ground truth and a versioned note plan (version 1) with template renderers. This change plugs an LLM verbalizer into the plan-to-text seam and extends the plan additively. See proposal.md for motivation and the specs for requirements. The repo is public, so the API key lives only in the environment.

The template notes were reviewed and found unrealistic: five fixed symptom phrases, a few boilerplate frames, four-significant-figure lab values, no lab flags or reference ranges, and no variety of setting. They remain as test fixtures.

## Goals / Non-Goals

**Goals:**
- Notes that plausibly resemble four clinician-authored documentation settings, with the plan's ground truth and noise labels intact.
- Every accepted note verifiably faithful, with measured validator quality and a human plausibility gate.
- Data that supports per-setting breakdowns, held-out-setting experiments and same-patient comparisons across settings.
- Reruns free and spend bounded, so the repo reproduces without an API key.

**Non-Goals:**
- Making models look good. The project's deliverable is a sound evaluation; modest or null results are acceptable. The data should be honest about its difficulty (Bayes ceiling stays in the manifest), not tuned for headroom.
- Patient-authored text, clinician diagnoses or treatment statements.
- Bit-reproducible LLM output (we cache and commit it instead).
- Clinical validation of realism. The gate measures plausibility to the project owner, who is not claimed to be a clinician.
- Running the held-out-setting experiments (training and evals changes).

## Decisions

**Four settings as profiles.** Each setting is a versioned prompt plus a rule set in the plan.

| Setting | Form | Plan rules |
|---|---|---|
| `shorthand` | brief, abbreviations, headline items only | 2 to 3 labs, at most 2 negatives |
| `ehr_template` | ROS grouped by body system, labs with H/L flags and reference ranges, typed history and a monitoring plan | all non-missing labs, flags from code |
| `ai_scribe` | narrative prose, may quote the patient, hedged phrasing | 0 to 3 labs inline, hedges favored |
| `copy_forward` | progress note carrying prior-visit text | elevated stale-value rate, stale values tagged |

These come from general knowledge of documentation styles and are plausible stand-ins, not a verified catalog.

**Plan version 2 (additive).** Adds the `setting`; a per-symptom allowed phrase set (synonyms such as shaky, tired, lightheaded, light sensitivity, stiff joints, chosen deterministically by seed) so wording varies and the extractor can check it; lab flags (H, L or none) computed by code from the stated value against the lab's reference range, so the LLM never decides them; and stale-value rules that now also cover `copy_forward`. Template renderers ignore the new fields, and the committed version 1 dataset still validates. Alternative: let the LLM choose wording freely, rejected because the extractor and the diversity check need a controlled vocabulary.

**Schema version 2 (additive).** Optional `pair_group` on a record. Matched-pair records use `patient_id` of the form `<base>-m<k>` with `k` randomly assigned per group so the id does not reveal the setting. Validators accept schema versions 1 and 2.

**Matched pairs are a subset of the test split** (default 200 patients, so 800 records). Alternative: a separate fourth split, rejected because it would change the split requirements of the archived `synthetic-cohort` spec. Cost: pooled metrics must deduplicate by `pair_group`, which the spec requires to be possible.

**No clinician impression.** Real notes often contain an assessment, which is a noisy label proxy and would let a classifier read the clinician's guess instead of the symptoms. Notes may contain only plan-and-monitoring language naming no disease or drug, enforced by a denylist scan (disease name, "diagnos", "risk", "probab", percent signs, common medication names). This is the first call and can be revisited as a separate, deliberate experiment.

**Anthropic API with a Haiku-class model, model id in config.** Cheap and fast for thousands of short notes. Alternative: a larger model, rejected for cost; the model id is recorded in the manifest.

**Prompt per setting, built from the plan only.** The prompt receives the plan facts (labs with units, flags and ranges; symptoms with polarity, hedge and allowed phrases; noise instructions) and the setting profile, never the label, true probability or scoring rule. Injection text is inserted by code after generation, not authored by the model.

**Tolerant lab parsing plus an independent symptom extractor.** Lab values are parsed by code that tolerates flags, reference ranges, dates and display rounding, compared within 1% after unit conversion. Symptom polarity comes from a separate extraction prompt over the controlled vocabulary. Alternative: trust the writer's own claims, rejected because it shares the writer's errors. A pilot exclusion rate above 15% for a setting means its prompt or parser needs work before the full run.

**Human gate on one sheet.** The pilot generates 20 notes per setting (80), plus 8 template-fixture control notes, shuffled, with no setting names, and a separate key file. For each note the owner records plausibility (yes or no) and the polarity of each of the five symptoms. One pass produces both gates: at least 16 of 20 plausible per setting, and at least 0.95 per-flag extractor accuracy on the 80 notes. The controls are reported, not gated, and show whether the rater discriminates. A failing setting gets a revised prompt, a bumped version, 20 fresh notes and a re-rating of that setting only. Ratings are committed. Alternative: automated plausibility scoring by an LLM judge, rejected as the primary gate because it would share the writer's blind spots; it could be added as a cheap secondary signal later.

**Bounded retries, then exclude.** Up to a configured number of attempts per note; failures are excluded and counted, with rates reported per setting and noise type so selection bias is visible.

**Cache keyed by plan hash, setting, prompt version, model id and sampling seed,** committed with the datasets so a fresh clone reruns with zero calls.

**Cost control.** A hard `--max-llm-calls` cap, a small separate cap for the pilot, a dry-run `estimate` that counts uncached calls, and a Console spend limit. Rough budget: about 6,000 notes (train 4,000, test 1,000 including 200 matched groups written four times, adversarial 420) plus extraction calls, retries and the pilot, on the order of ten to twenty dollars; the dry run confirms before any spend.

**Statistical power is part of the design.** With about 1,000 test notes over four settings there are roughly 250 per setting, enough for rough per-setting estimates (a rough AUC uncertainty near ±0.04) but not fine comparisons. The evals should report confidence intervals; enlarging the test split is a config change if finer slices are wanted.

## Risks / Trade-offs

- [LLM rewrites a value, drops a symptom or invents clinical detail] → Two-part validation, denylist scan, bounded retries, human gate, exclusions counted.
- [Settings sound alike because one model wrote them] → Distinct profile prompts and plan rules, measurable form checks in the spec, and the blind rating with controls.
- [Single rater and a plausibility notion that is not clinical] → Documented as a non-goal; ratings committed so others can audit; the gate is a smoke test, not validation.
- [Extractor shares the writer model's blind spots] → Different prompt and a hand-checked 80-note sample with a 0.95 threshold that blocks the run.
- [Exclusions bias the dataset toward easy notes] → Report exclusion rates by setting and noise type; investigate before publishing numbers.
- [Matched pairs double count patients in pooled metrics] → `pair_group` is required to be usable for deduplication.
- [Prose still carries LLM tics a classifier can learn] → Held-out-setting experiments in later changes, which this data is designed to support.
- [Cache or datasets grow large or leak a key] → Size check and key-pattern scan in the integration tasks.
- [Provider model deprecation changes outputs on regeneration] → Model id and prompt version are in the cache key and manifest; the committed cache preserves the published data.

## Open Questions

- Maximum retry count and the pilot exclusion threshold. Defaults: 3 attempts and 15%, adjustable in config without touching the spec.
- The number of matched-pair patients (default 200) and the setting mix for train and test (default equal shares). Config values.
