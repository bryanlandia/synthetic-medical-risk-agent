# Spec Delta

## Purpose

Defines how clinical notes are written by an LLM in several clinician-authored documentation settings from a note plan, while keeping the plan's ground truth and labeled noise intact, with validation, a human realism gate, matched-pair groups, caching and cost bounds, so evaluation results rest on varied, plausible prose that is still verifiably faithful.

## ADDED Requirements

### Requirement: LLM verbalizes the note plan in documentation settings
The system SHALL turn each note plan into prose using an LLM in one of four documentation settings: `shorthand`, `ehr_template`, `ai_scribe` and `copy_forward`. Verbalization SHALL NOT change the plan's lab values, symptom polarities, noise tags, label or true probability.

#### Scenario: All four settings are producible
- **WHEN** a cohort is generated with a configured rate for each setting
- **THEN** every note's metadata names exactly one setting and the realized rate of each setting is within 0.03 of its configured rate on at least 1,000 notes

#### Scenario: Ground truth is unchanged by verbalization
- **WHEN** a plan is verbalized by the LLM
- **THEN** the record's true flags, true probability, label and noise tags are identical to those of the template-rendered version of the same plan

### Requirement: Settings follow their documentation profile
Each setting SHALL follow a profile that fixes its form: `shorthand` is brief abbreviated text stating only headline items; `ehr_template` has review of systems grouped by body system and labs with high or low flags; `ai_scribe` is narrative prose that may quote the patient; `copy_forward` is a progress note that may carry stale values from a prior visit.

#### Scenario: EHR template flags are correct and computed by code
- **WHEN** an `ehr_template` note states a lab value
- **THEN** it shows a high flag if the stated value is above the lab's reference range, a low flag if below, and none if within, in 100% of validated notes

#### Scenario: Shorthand is shorter than a scribe summary
- **WHEN** at least 100 validated notes of each setting exist
- **THEN** the median word count of `shorthand` notes is below that of `ai_scribe` notes

#### Scenario: Copy-forward stale values are planned and tagged
- **WHEN** a plan marks a lab value as stale for a `copy_forward` note
- **THEN** the note states that stale value, and the record carries the matching `contradiction` noise tag with the structured value unchanged

### Requirement: Symptom wording varies
Each symptom SHALL be expressed with varied wording drawn from a per-symptom phrase set carried in the plan, and every mention SHALL include at least one of the plan's allowed phrases for that symptom.

#### Scenario: Wording diversity across a cohort
- **WHEN** at least 1,000 validated notes are analyzed
- **THEN** each symptom appears with at least 3 distinct allowed phrases and no single phrase accounts for more than 60% of that symptom's mentions

#### Scenario: Mention without an allowed phrase is rejected
- **WHEN** a note mentions a planned symptom without any of its allowed phrases
- **THEN** the note fails validation and is retried

### Requirement: Notes state no diagnosis, risk or treatment
Notes SHALL NOT state a diagnosis, a risk estimate or probability, or a medication or treatment. Plan-and-monitoring statements that name no disease and no drug are allowed.

#### Scenario: Denylist scan passes
- **WHEN** all accepted notes are scanned for the disease name, the words "diagnos", "risk" and "probab", percent signs, and a denylist of common medication names
- **THEN** there are zero matches

#### Scenario: Violating note is retried
- **WHEN** an LLM-written note contains a denylisted term
- **THEN** it fails validation and is regenerated within the bounded retry count

### Requirement: Injection text is inserted verbatim
Prompt-injection text SHALL come from the versioned catalog and appear in the note verbatim. The LLM SHALL NOT author injection content.

#### Scenario: Catalog text appears unchanged
- **WHEN** a plan includes an injection catalog entry
- **THEN** the exact catalog string is a substring of the resulting note, and the note passes validation otherwise

#### Scenario: No injection without a catalog entry
- **WHEN** a note whose plan has no injection is scanned for instruction-like override phrases from the catalog
- **THEN** none are found

### Requirement: Notes are validated against the plan
Each LLM-written note SHALL be validated before acceptance: stated lab values are parsed, tolerating flags, reference ranges and display rounding, and compared to the plan within 1% after unit conversion; symptom polarity is recovered by an independent extraction pass and compared to the plan. Mismatches not covered by a recorded noise tag cause rejection.

#### Scenario: Realistic lab formatting is accepted
- **WHEN** a note shows a lab as a value with a flag, a reference range or fewer decimals than the plan
- **THEN** validation accepts it if the value is within 1% of the plan

#### Scenario: Invented or wrong value is rejected
- **WHEN** a note states a lab value that is not in the plan or differs from it by more than 1% without a recorded noise tag
- **THEN** the note fails validation

#### Scenario: Unfaithful note is retried then excluded
- **WHEN** a note fails validation
- **THEN** it is regenerated up to a configured maximum number of attempts, and a record still failing is excluded from the split and counted in the manifest

#### Scenario: Tagged noise is not a failure
- **WHEN** a note intentionally contains a recorded `unit_mismatch`, `contradiction` or `note_flag_disagreement`
- **THEN** validation accepts the mismatch only for the tagged lab or flag and rejects any other mismatch

#### Scenario: Identifier scan passes
- **WHEN** accepted notes are scanned for SSN-, MRN- and phone-shaped strings and denylisted facility names
- **THEN** there are zero matches

### Requirement: Notes avoid tells of machine writing
Notes SHALL state lab values at the precision a lab report prints (three significant figures), state each symptom once with one wording, and contain no contradictory shorthand and no mention that anything is fictional, synthetic or a study. These are checked offline, and a failing note is retried then excluded like any other failure.

#### Scenario: Lab values have realistic precision
- **WHEN** the prompt lists a lab value
- **THEN** it is shown with at most three significant figures and stays within 0.5% of the plan value, so it passes the 1% validation

#### Scenario: One wording per symptom
- **WHEN** a note states a symptom with two or more different allowed phrases that are not nested in one another
- **THEN** it fails validation with a repeated-symptom code, while repeating the same phrase, or a phrase nested in a longer one, is accepted

#### Scenario: Contradictory shorthand is rejected
- **WHEN** a note says "c/o denies", "c/o no" or "c/o neg"
- **THEN** it fails validation with a contradictory-phrasing code

#### Scenario: No mention of the fiction
- **WHEN** a note contains "fictional", "synthetic", "simulated", "test data", "this study" or "study condition"
- **THEN** it fails validation with a meta-mention code

#### Scenario: Prompt revisions are versioned
- **WHEN** a prompt or a display rule changes
- **THEN** `llm.prompt_version` changes so cached notes from the older prompt are never reused, and the affected settings are re-piloted and re-rated

### Requirement: Notes vary like real documentation
Each note SHALL be written with style traits drawn from its seed (layout, order, wording habits), symptom wording drawn from a pool specific to how the symptom is stated, and two exemplar notes about other patients. Quick settings SHALL have fewer traits than documented ones. The traits and exemplar choices are recorded in the plan.

#### Scenario: Wording matches the polarity
- **WHEN** a symptom is stated as present, hedged or denied
- **THEN** its allowed wording comes from a pool of at least six phrases for that polarity, and no denied pool is made by negating a positive phrase ("feels not exhausted")

#### Scenario: Traits are reproducible and independent
- **WHEN** the plan for a patient is built twice with the same seed
- **THEN** the traits and exemplar picks are identical, and drawing them does not change any other plan field

#### Scenario: Traits cover their values without dominating
- **WHEN** 120 plans are built for a setting
- **THEN** every value of every trait is used, and no value is used by more than 60% of the plans

#### Scenario: Quick notes vary less
- **WHEN** the number of traits per setting is compared
- **THEN** shorthand has fewer traits than each documented setting

#### Scenario: Exemplars are original and clean
- **WHEN** the exemplar files are scanned
- **THEN** each setting has six distinct notes, each passes the claims and identifier scans, none mentions the fiction, and every lab flag in them agrees with its reference range

#### Scenario: Copying an exemplar is rejected
- **WHEN** a note contains eight consecutive words from any exemplar of its setting, other than a stock line the traits asked for
- **THEN** it fails validation with an exemplar-copied code

#### Scenario: Pilot reports variety against limits
- **WHEN** a pilot is written
- **THEN** it reports per setting the share of notes sharing the most common first three words and the number of distinct trait combinations, and flags a setting above 35% (40% for shorthand) or below 8 combinations (6 for shorthand) out of 20 notes

### Requirement: Symptom extraction quality is measured
The symptom extractor used for validation SHALL be measured against a hand-checked sample so that validation results can be trusted.

#### Scenario: Extractor accuracy threshold
- **WHEN** the extractor is run on the owner's hand-checked sample of 80 notes, 20 per setting
- **THEN** per-flag accuracy is at least 0.95, and a lower result blocks the full paid run

### Requirement: Human realism gate before the paid run
Before the full paid run, the project owner SHALL blind-rate a pilot sample of 20 notes per setting for plausibility as real clinical documentation. Every setting SHALL reach at least 80% plausible, or the full paid run for that setting is blocked.

#### Scenario: Rating sheet is blind
- **WHEN** the rating sheet is generated
- **THEN** the notes are shuffled across settings, the sheet contains no setting names, and the mapping from note id to setting is stored separately

#### Scenario: Gate result per setting
- **WHEN** the owner's ratings are loaded
- **THEN** a report shows the plausible count and rate for each setting, marks each setting pass or fail at 80%, and the full run proceeds only if all four pass

#### Scenario: Controls reveal rater discrimination
- **WHEN** template-fixture notes are mixed into the sheet as controls
- **THEN** their plausible rate is reported separately and excluded from the gate

#### Scenario: Failed setting is revised and re-rated
- **WHEN** a setting fails the gate
- **THEN** its prompt is revised and its prompt version bumped, 20 fresh notes are drawn for that setting, and only that setting is re-rated

### Requirement: Matched-pair groups
The system SHALL write a configured number of test patients in all four settings, forming groups with identical ground truth. Each record in a group SHALL have a unique record identifier and a shared `pair_group` value, and identifiers SHALL NOT reveal the setting.

#### Scenario: Pair members share ground truth and differ in setting and text
- **WHEN** a matched-pair group is produced
- **THEN** its four records have identical labs, true flags, true probability and label, four different settings, no two identical texts, and unique record identifiers that do not encode the setting

#### Scenario: Groups can be deduplicated
- **WHEN** a pooled metric is computed over the test split
- **THEN** records can be grouped by `pair_group` so that a matched patient is not counted four times

### Requirement: Cached and cost-bounded generation
LLM calls SHALL be cached keyed by plan, prompt version, model identifier and sampling seed; SHALL be capped by a configured call or spend limit; and SHALL NOT be repeated for a cached input. The pilot SHALL run under its own small cap.

#### Scenario: Rerun makes no LLM calls
- **WHEN** generation is rerun with unchanged seed, configuration, prompt version and model
- **THEN** zero LLM calls are made and the notes are byte-identical to the previous run

#### Scenario: Cap halts generation safely
- **WHEN** the configured cap is reached mid-run
- **THEN** generation stops with a clear error, completed notes remain cached, and no partial record is written to a split

#### Scenario: Dry run estimates cost before spending
- **WHEN** the estimate command is run on a configuration
- **THEN** it reports the number of uncached calls, including the pilot and matched-pair notes, and an estimated cost without making any LLM call

#### Scenario: Key comes from the environment only
- **WHEN** the repository files, cache and datasets are scanned for the API key pattern
- **THEN** there are zero matches

### Requirement: Note provenance in the manifest
The manifest SHALL record, for each split, the note source (template or LLM), model identifier, prompt version, counts per setting, matched-pair group count, attempts, exclusions and total calls.

#### Scenario: Provenance is readable
- **WHEN** the manifest of an LLM-note dataset is read
- **THEN** it states note source `llm`, the model identifier, prompt version, counts per setting, the number of matched-pair groups, exclusion counts per setting and noise type, and total LLM calls made

### Requirement: Bounded concurrent generation
The system SHALL write notes with a configurable number of parallel workers (default 8, at most 32), and the resulting dataset SHALL NOT depend on the worker count. Call caps SHALL hold exactly under concurrency, and rate-limit responses SHALL be retried with backoff without consuming a note's attempt.

#### Scenario: Output does not depend on the worker count
- **WHEN** the same configuration is generated with 1 worker and again with 8 workers
- **THEN** the accepted records, exclusion counts and per-setting counts are identical

#### Scenario: Calls overlap up to the configured limit
- **WHEN** a run uses 8 workers and each call takes measurable time
- **THEN** more than one call is in flight at once and never more than 8

#### Scenario: Call cap is exact under concurrency
- **WHEN** the call cap is 25 and 8 workers are running
- **THEN** exactly 25 paid calls are made, the run stops with a clear error, nothing is written to a split, and all 25 results are in the cache

#### Scenario: Rate limits back off without using up attempts
- **WHEN** the API answers a call with rate-limit errors
- **THEN** the call is retried with exponentially growing waits up to a fixed bound, the note's attempt count is unchanged, and if the bound is exceeded the attempt fails as a retryable call error

#### Scenario: Stopping early does not depend on the worker count
- **WHEN** the pilot reaches its target or a setting is stopped early while other notes are still in flight
- **THEN** in-flight notes finish and are cached, and only results up to the stopping point enter the sample and the counts
