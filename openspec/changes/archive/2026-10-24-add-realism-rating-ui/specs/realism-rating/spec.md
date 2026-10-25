# Spec Delta

## Purpose

Lets a human clinician or a clearly labelled LLM reviewer rate blind pilot notes for realism in a purpose-built tool, and feeds those ratings into the realism gate with the rater's kind recorded and enforced.

## ADDED Requirements

### Requirement: Blind sheet for the rating tool
The pilot SHALL write a machine-readable blind sheet containing each note's id and text and the rating instructions, and nothing that identifies a note's setting, plan or extractor reading. The key SHALL stay in a separate file.

#### Scenario: Sheet carries no answers
- **WHEN** `sheet.json` is written for a pilot round
- **THEN** it contains no setting names, no plan symptoms and no extractor labels, and the test that scans it for the four setting names and the key's contents finds none

#### Scenario: Same notes as the markdown sheet
- **WHEN** both sheets are written for a round
- **THEN** they list the same note ids in the same order with identical note text

### Requirement: Rating app shows one note at a time and saves as it goes
The rating app SHALL present notes one at a time with plausibility (y or n) and the five symptom labels (present, possible, absent, none), a progress indicator and a visible notice that all data is synthetic. It SHALL save every change to a rating file immediately, let the rater go back and forward, and resume where they stopped.

#### Scenario: Rate with the keyboard
- **WHEN** a rater uses only the keyboard to set all six fields on a note and move to the next
- **THEN** the values are saved, the progress count increases by one, and no pointer interaction was needed

#### Scenario: Reload does not lose work
- **WHEN** the page is reloaded or the app restarted after 10 notes are rated
- **THEN** the same rater resumes at the first unrated note with all 10 earlier ratings intact

#### Scenario: Incomplete notes are visible
- **WHEN** a note is missing any of the six fields
- **THEN** the progress view marks it incomplete and the app does not report the round as finished

### Requirement: Rating app cannot reveal the key
The rating app SHALL read only the blind sheet and write only rating files, and SHALL bind to the local machine only. It MUST NOT read, serve or reference the key file.

#### Scenario: No route exposes the key
- **WHEN** every route of the running app is requested, including paths that try to reach `key.json`
- **THEN** none returns key contents and the path guard rejects any file outside the blind sheet and the rating files with a client error

#### Scenario: Local binding
- **WHEN** the app starts with its default settings
- **THEN** it listens on the loopback interface only

### Requirement: Rating files record the rater and their kind
Each rating file SHALL record a rater name, a rater kind of `human` or `llm`, and for an LLM the model id and prompt version. The rater kind SHALL come from how the file was created (app launch option or reviewer command), not from a field the rater can edit while rating.

#### Scenario: Human and LLM files are distinguishable
- **WHEN** a clinician rates in the app and the reviewer rates a round
- **THEN** two files exist, one with kind `human` and one with kind `llm` plus model id and prompt version

#### Scenario: Kind cannot be changed from the page
- **WHEN** a rating is saved from the page with a body that sets a different kind
- **THEN** the saved file keeps the kind set at launch

### Requirement: Gate accepts only configured rater kinds
`data-gen gate` SHALL read the rating files of a round and count only ratings from rater kinds listed in the configuration, which defaults to `human` only. The report SHALL name the rater kinds it counted, and the dataset manifest SHALL record them. With several accepted raters on the same note, the gate SHALL use the most pessimistic plausibility (n if any says n).

#### Scenario: LLM ratings alone do not pass by default
- **WHEN** only an `llm` rating file exists for a round that would otherwise reach 80% plausible in every setting
- **THEN** the gate fails and says that no accepted human ratings were found

#### Scenario: LLM ratings can be accepted explicitly
- **WHEN** the configuration lists `llm` as an accepted kind and the llm file reaches the thresholds
- **THEN** the gate passes, prints `rated by: llm (not a clinician)`, and the manifest of the full run records `llm` as the rater kind

#### Scenario: Markdown ratings still work
- **WHEN** a round has only a hand-filled `ratings.md`
- **THEN** the gate reads it as kind `human`, exactly as before

#### Scenario: Disagreement is reported and counted pessimistically
- **WHEN** a human and the reviewer both rate a note and disagree on plausibility
- **THEN** the note counts as implausible for the gate and the report lists the number of disagreements per setting

### Requirement: Adversarial LLM reviewer
The reviewer SHALL use a model different from the note writer's, a skeptical-clinician prompt that looks for signs of artificial text, and only what a human rater sees: the note text and the rating instructions. It SHALL output the same six fields per note plus a one-sentence reason for each implausible verdict.

#### Scenario: Reviewer is blind
- **WHEN** the reviewer's prompts for a round are captured in a test
- **THEN** they contain no setting names, plan data, extractor labels or key contents

#### Scenario: Reviewer differs from the writer
- **WHEN** the reviewer is configured with the same model id as the writer
- **THEN** it refuses to run and says that an independent model is required

#### Scenario: Reviewer discriminates
- **WHEN** the reviewer rates a round that contains the template-fixture controls
- **THEN** the controls' plausible rate is reported and is lower than the LLM-written notes' rate by at least 20 percentage points, or the report flags the reviewer as non-discriminating

#### Scenario: Output is validated
- **WHEN** the reviewer returns an unparsable or incomplete rating for a note
- **THEN** that note is retried up to the attempt limit and otherwise left unrated, so the gate reports it missing and does not treat it as a pass

### Requirement: Reviewer operates the rating app through a browser
The reviewer SHALL be able to rate a round by operating the running rating app in a browser, using only a fixed set of actions (read the current note, set plausibility, set a symptom label, add a comment, go to the next note, finish), and SHALL record the session as a video.

#### Scenario: UI session produces the same kind of file
- **WHEN** the reviewer completes a round through the browser
- **THEN** the rating file is written by the app itself, has kind `llm`, covers every note, and a video file of non-zero length exists for the session

#### Scenario: Browser actions are limited
- **WHEN** the reviewer asks for an action outside the fixed set, or a URL outside the local app
- **THEN** the action is refused and counted in the session log

#### Scenario: UI session is bounded
- **WHEN** the reviewer exceeds the configured step limit, call cap or spend cap
- **THEN** the session stops, the ratings made so far are kept, the gate reports the rest as unrated, and the video is saved

### Requirement: Reviewer spend is capped and cached
Reviewer calls SHALL go through the same cache and call and spend caps as the writer, with their own configured limits, and a dry run SHALL estimate the cost without a key.

#### Scenario: Dry run needs no key
- **WHEN** the reviewer estimate is run without an API key
- **THEN** it prints the number of calls and an estimated cost and makes no API call

#### Scenario: Rerun is free in direct mode
- **WHEN** the direct reviewer is run twice on the same round with the same model and prompt version
- **THEN** the second run makes zero paid calls and writes identical ratings

### Requirement: LLM review is labelled everywhere it appears
Wherever an LLM reviewer's ratings are reported (gate output, manifest, README, the demo page), they SHALL be described as an LLM review and not as a clinician's, and the README SHALL state that clinical validation was not performed.

#### Scenario: Labels present
- **WHEN** a dataset is generated after a gate that accepted `llm` ratings
- **THEN** the manifest and the dataset README both say the realism review was done by an LLM and not by a clinician
