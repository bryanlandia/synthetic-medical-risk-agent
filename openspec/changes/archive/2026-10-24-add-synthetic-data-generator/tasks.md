# Tasks

## 1. Project setup

- [x] 1.1 Create `data_gen/` Python package with `pyproject.toml` (Python 3.12, `uv`, lockfile) and verify `uv sync` and `uv run pytest` succeed on an empty test
- [x] 1.2 Add dataset README stating all data is synthetic and the disease is fictional, and verify a test asserts that text is present

## 2. Schema and fictional disease

- [x] 2.1 Define the Pydantic record schema with a model-input view (lab panel, note) and a ground-truth view (flags, true probability, label), plus split, tags, noise metadata, style, synthetic marker and schema version, and verify schema tests accept valid and reject invalid records and that the input view serializes with no flags, probability or label
- [x] 2.2 Define 6-10 fictional lab definitions (name, unit, alternate unit and conversion factor, reference and plausible ranges) and verify a test that none of the names match a denylist of real test names and the count is in bounds
- [x] 2.3 Implement seed handling with one spawned stream per concern and verify the same seed gives byte-identical structured output and a different seed does not collide on IDs

## 3. Cohort generation

- [x] 3.1 Implement feature sampling and the hidden logistic scoring rule over structured ground-truth features only, and verify a test that true probability is in [0, 1] and unchanged when note text changes
- [x] 3.2 Implement intercept calibration to target prevalence and Bernoulli label sampling, and verify on 10,000 patients that every one of ten probability bins is within 0.03 and prevalence is within 0.02
- [x] 3.3 Implement train and random-test splits and verify disjointness, distribution match (prevalence within 0.02, lab means within 0.1 SD) and that all present values are in plausible range

## 4. Adversarial cases

- [x] 4.1 Implement case-type generators for borderline (0.4-0.6), impossible values, missing labs, unit mismatch, contradiction, note-flag disagreement, and prompt injection, and verify at least 50 tagged records per type with impossible values and flag disagreement only in this split
- [x] 4.2 Add the versioned injection catalog with at least 3 categories (including override-risk-output and request-treatment-advice) and verify injection tags appear only in the adversarial split with labels unchanged

## 5. Note plan and template rendering

- [x] 5.1 Implement the versioned note plan (stated labs, units, per-flag statement, negation or hedge, style, contradictions, missing values, injection text) with labeled noise metadata, and verify realized noise and style rates are within 0.03 of config on 1,000 plans
- [x] 5.2 Implement the terse and templated renderers (the latter with optional stale value) and verify the same plan and seed give byte-identical text with zero network calls
- [x] 5.3 Implement a parse-back check and verify that on 1,000 rendered notes every planned lab value (within 1% after unit conversion) and symptom polarity is recovered, and that requesting a reserved style fails with a clear error
- [x] 5.4 Implement the identifier scan and verify it flags SSN-, MRN- and phone-shaped strings and denylisted facility names, and passes on all rendered notes

## 6. Output and docs

- [x] 6.1 Implement JSONL split writers and `manifest.json` (seed, versions, config hash, counts, prevalence, noise and style rates, true-probability AUC and Brier ceiling) and verify a test reads back the manifest values
- [x] 6.2 Implement the CLI (`generate`, `validate`) and document commands in AGENTS.md, verifying the documented commands run as written on a small config

## 7. Integration

- [x] 7.1 Run a full generation at default sizes (about 4,000 / 1,000 / 400), commit the datasets, and verify `validate` passes and a second run is byte-identical
- [x] 7.2 Verify dataset size and the identifier scan pass, and confirm `training/` and `agent/` contain no import of the scoring rule

## Workflow follow-up

- Archive the change after review.
- Verify the archived specs appear under `openspec/specs/synthetic-cohort` and `openspec/specs/clinical-notes`.
- Start `add-llm-note-writer` once this change is archived.
