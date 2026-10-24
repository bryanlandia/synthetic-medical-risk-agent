# Spec Delta

## Purpose

Defines how clinical notes are written by an LLM from a note plan while keeping the plan's ground truth and labeled noise intact, with validation, caching and cost bounds, so published results rest on realistic prose that is still verifiably faithful.

## ADDED Requirements

### Requirement: LLM verbalizes the note plan
The system SHALL turn each note plan into prose using an LLM, supporting the terse, templated, narrative and AI-scribe styles. Verbalization SHALL NOT change the plan's lab values, symptom polarities, noise tags, label or true probability.

#### Scenario: All four styles are producible
- **WHEN** a cohort is generated with a configured rate for each of the four styles
- **THEN** every note's metadata names exactly one style and the realized rate of each style is within 0.03 of its configured rate on at least 1,000 notes

#### Scenario: Ground truth is unchanged by verbalization
- **WHEN** a plan is verbalized by the LLM
- **THEN** the record's true flags, true probability, label and noise tags are identical to those of the template-rendered version of the same plan

### Requirement: Injection text is inserted verbatim
Prompt-injection text SHALL come from the versioned catalog and appear in the note verbatim. The LLM SHALL NOT author injection content.

#### Scenario: Catalog text appears unchanged
- **WHEN** a plan includes an injection catalog entry
- **THEN** the exact catalog string is a substring of the resulting note, and the note passes validation otherwise

#### Scenario: No injection without a catalog entry
- **WHEN** a note whose plan has no injection is scanned for instruction-like override phrases from the catalog
- **THEN** none are found

### Requirement: Notes are validated against the plan
Each LLM-written note SHALL be validated before acceptance: stated lab values are parsed and compared to the plan within 1% after unit conversion, and symptom polarity is recovered by an independent extraction pass and compared to the plan. Mismatches not covered by a recorded noise tag cause rejection.

#### Scenario: Unfaithful note is retried then excluded
- **WHEN** a note fails validation
- **THEN** it is regenerated up to a configured maximum number of attempts, and a record still failing is excluded from the split and counted in the manifest

#### Scenario: Tagged noise is not a failure
- **WHEN** a note intentionally contains a recorded `unit_mismatch`, `contradiction` or `note_flag_disagreement`
- **THEN** validation accepts the mismatch only for the tagged lab or flag and rejects any other mismatch

#### Scenario: Identifier scan passes
- **WHEN** accepted notes are scanned for SSN-, MRN- and phone-shaped strings and denylisted facility names
- **THEN** there are zero matches

### Requirement: Symptom extraction quality is measured
The symptom extractor used for validation SHALL be measured against a hand-checked sample so that validation results can be trusted.

#### Scenario: Extractor accuracy threshold
- **WHEN** the extractor is run on a hand-checked sample of at least 100 notes covering all four styles
- **THEN** per-flag accuracy is at least 0.95, and a lower result blocks the real run

### Requirement: Cached and cost-bounded generation
LLM calls SHALL be cached keyed by plan, prompt version, model identifier and sampling seed; SHALL be capped by a configured call or spend limit; and SHALL NOT be repeated for a cached input.

#### Scenario: Rerun makes no LLM calls
- **WHEN** generation is rerun with unchanged seed, configuration, prompt version and model
- **THEN** zero LLM calls are made and the notes are byte-identical to the previous run

#### Scenario: Cap halts generation safely
- **WHEN** the configured cap is reached mid-run
- **THEN** generation stops with a clear error, completed notes remain cached, and no partial record is written to a split

#### Scenario: Dry run estimates cost before spending
- **WHEN** the estimate command is run on a configuration
- **THEN** it reports the number of uncached calls and an estimated cost without making any LLM call

#### Scenario: Key comes from the environment only
- **WHEN** the repository files, cache and datasets are scanned for the API key pattern
- **THEN** there are zero matches

### Requirement: Paraphrase groups
The system SHALL produce multiple notes for one patient that differ in wording and share identical ground truth, grouped by patient identifier and numbered.

#### Scenario: Paraphrases share ground truth and differ in text
- **WHEN** a paraphrase group of k notes is produced for a patient
- **THEN** all k notes have identical labs, true flags, true probability and label, each carries a distinct `paraphrase_index`, and no two notes have identical text

### Requirement: Note provenance in the manifest
The manifest SHALL record, for each split, the note source (template or LLM), model identifier, prompt version, attempts, exclusions and total calls.

#### Scenario: Provenance is readable
- **WHEN** the manifest of an LLM-note dataset is read
- **THEN** it states note source `llm`, the model identifier, prompt version, counts of excluded records, and total LLM calls made
