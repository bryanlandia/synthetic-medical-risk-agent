# Spec Delta

## MODIFIED Requirements

### Requirement: Note styles
The generator SHALL support a configurable set of note styles. Template rendering provides `terse` and `templated`, which are test fixtures. LLM-written notes use the documentation settings `shorthand`, `ehr_template`, `ai_scribe` and `copy_forward`. A style that the configured note source does not support SHALL be rejected before any record is produced. Each note's style SHALL be recorded in its metadata.

#### Scenario: Style is recorded and rates are realized
- **WHEN** a cohort of at least 1,000 notes is generated with a configured rate per supported style
- **THEN** every note's metadata names exactly one style and the realized rate of each style is within 0.03 of its configured rate

#### Scenario: Unavailable style is rejected
- **WHEN** a configuration requests a style that the configured note source cannot produce, for example `ai_scribe` with template rendering or `terse` with the LLM source
- **THEN** generation fails with a clear error before producing any record

#### Scenario: Stale copied-forward value is tagged
- **WHEN** a `templated` or `copy_forward` note contains a stale copied-forward lab value
- **THEN** it is tagged `contradiction` with the lab named, and the structured value is unchanged

#### Scenario: Ground truth does not depend on style
- **WHEN** notes for one patient are written in different styles
- **THEN** the true flags, true probability and label are identical across them
