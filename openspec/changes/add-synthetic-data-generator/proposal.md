# Proposal

## Why

Every later phase (baseline evals, fine-tuning, the agent, the comparison report) depends on labeled data whose ground truth we fully control. Real medical data is off the table, so we invent a fictional disease defined by a hidden scoring rule. That lets us measure accuracy, calibration and robustness exactly. This is the first change because nothing else can be built or evaluated without it.

## What Changes

- Add a seeded, reproducible generator in `data_gen/` that samples fictional patients: 6-10 fictional lab values plus symptom flags.
- Define the fictional disease as a hidden logistic scoring function over those features. Labels are sampled from the true probability, and the true probability is stored with every record so calibration can be measured against it.
- Generate clinical notes from each patient's ground-truth features using deterministic templates (no LLM calls). Symptom flags are not model inputs: they reach models only through the note, while the lab panel is the structured input. This change provides two styles (terse shorthand, templated with stale values); the notes carry controlled, labeled noise: hedging, contradictions with the labs, missing values, and mixed units (mg/dL vs mmol/L). Ground truth stays in the record for scoring.
- Define a versioned note plan as the seam where a later change plugs in LLM-written prose (narrative and AI-scribe styles).
- Produce three splits: train, random test, and adversarial (edge cases, borderline cases near the threshold, notes contradicting labs, prompt-injection and jailbreak text in notes, impossible values).
- Stamp every artifact (data files, README for the dataset, record metadata) as synthetic and fictional.
- Make generation deterministic from a committed seed, with the generator version and seed recorded in the output.

## Capabilities

### New Capabilities
- `synthetic-cohort`: seeded generation of fictional patients (labs, symptom flags), the hidden scoring rule, label and true-probability sampling, record schema, split definitions, and fictional-data labeling.
- `clinical-notes`: deterministic template rendering of clinical notes from ground-truth features, the note plan, labeled controlled noise (hedging, contradictions, missing values, mixed units), note styles, and adversarial note content.

### Modified Capabilities

None (greenfield).

## Out of scope

- Classifier or LoRA training, and any use of the data by a model (`model-training` change).
- Agent, tools, or API code (`risk-scoring-agent` change).
- Eval harness, scorers, and reports. This change only supplies the datasets and the labeled noise metadata that evals will consume (`evals` change).
- Serving or deploying anything.
- LLM-written notes, their cache and spend cap, the narrative and AI-scribe styles, and paraphrase groups (`add-llm-note-writer` change). Numbers published in the README must come from that change's notes, not from template notes.

## Eval categories affected

This change supplies the data for: happy path (accuracy and calibration vs. true probability), data quality, borderline, and adversarial (prompt injection in notes). Consistency (paraphrased notes for the same patient) comes from `add-llm-note-writer`. Tool use and safety/scope cases that are not note-driven come from the later evals change.

## Impact

- New code under `data_gen/` (Python package, tests, CLI) and generated datasets, whose size and location are decided in design.
- No API dependency or spend: generation is offline and deterministic.
- Defines the record schema and the hidden rule that every downstream change builds on, so changing it later is costly.
