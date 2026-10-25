# Spec Delta

## MODIFIED Requirements

### Requirement: Blind sheet for the rating tool
The pilot SHALL write a machine-readable sheet containing each note's id, text and kind (a short label and a description of what is normal for that kind of documentation) and the rating instructions, and nothing that identifies a note's plan, extractor reading, record or internal setting name. The key SHALL stay in a separate file.

#### Scenario: Sheet carries no answers
- **WHEN** `sheet.json` is written for a pilot round
- **THEN** it contains no internal setting names, no plan symptoms, no extractor labels and no record ids, each note carries only its id, text and kind, and the template-fixture controls are described as a plain clinician-written note, not as controls

#### Scenario: Same notes as the markdown sheet
- **WHEN** both sheets are written for a round
- **THEN** they list the same note ids in the same order with identical note text

#### Scenario: Each note says what kind it is meant to be
- **WHEN** a rater opens a note
- **THEN** the app shows the kind label and what is normal for it (for example that an AI-scribe draft is expected to be structured and even-toned), so the note is judged against that kind

#### Scenario: Older rounds get their kinds
- **WHEN** a round was written before kinds existed and the reviewer command runs
- **THEN** each note's kind is added to its sheet from the key, once, and a dry run changes no file

### Requirement: Adversarial LLM reviewer
The reviewer SHALL use a model different from the note writer's, a skeptical-clinician prompt that looks for signs of artificial text judged against what each kind of note normally looks like, and only what a human rater sees: the note text, its kind and the rating instructions. It SHALL output the same six fields per note plus a one-sentence reason for each implausible verdict.

#### Scenario: Reviewer is blind
- **WHEN** the reviewer's prompts for a round are captured in a test
- **THEN** they contain no internal setting names, plan data, extractor labels, record ids or key contents, and each user message states the note's kind

#### Scenario: Reviewer differs from the writer
- **WHEN** the reviewer is configured with the same model id as the writer
- **THEN** it refuses to run and says that an independent model is required

#### Scenario: Reviewer discriminates
- **WHEN** the reviewer rates a round that contains the template-fixture controls
- **THEN** the controls' plausible rate is reported and is lower than the LLM-written notes' rate by at least 20 percentage points, or the report flags the reviewer as non-discriminating

#### Scenario: Output is validated
- **WHEN** the reviewer returns an unparsable or incomplete rating for a note
- **THEN** that note is retried up to the attempt limit and otherwise left unrated, so the gate reports it missing and does not treat it as a pass

#### Scenario: Kind sets the standard
- **WHEN** an AI-scribe draft and a quick shorthand note are both tidy and even-toned
- **THEN** the prompt for the first says this is expected and is not a reason to reject it, and the prompt for the second does not
