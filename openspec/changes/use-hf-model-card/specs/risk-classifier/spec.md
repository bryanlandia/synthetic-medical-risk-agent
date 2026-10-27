# Spec Delta

## MODIFIED Requirements

### Requirement: A model card states what the model is
The repository SHALL contain a model card for the classifier in the Hugging Face model card layout: a metadata block, then the template's sections in its order (model details, sources, uses with an explicit out-of-scope use, bias, risks and limitations, how to get started, training details, evaluation, and the remaining template sections). It SHALL give the intended use (a fictional-disease demo, not medical advice), the data, the train and dev split, the held-out results, the known weaknesses and the synthetic-data notice, and SHALL say so where a section does not apply instead of omitting it.

#### Scenario: Model card present and current
- **WHEN** the test suite runs
- **THEN** the model card names the hash of the committed model file, and a mismatch fails the suite

#### Scenario: The layout
- **WHEN** the committed card is read
- **THEN** it starts with a metadata block, its section headings are the template's in the template's order, and it contains the synthetic-data notice and an out-of-scope use that excludes any real medical use

## ADDED Requirements

### Requirement: The card's metadata carries the results as data
The card's metadata block SHALL parse as YAML and SHALL carry tags marking the model as synthetic and not for clinical use and a `model-index` with the dev and test AUC, Brier score, log loss and ECE. Every number in it SHALL equal the number in the corresponding result file, and the card SHALL be written by code from those files.

#### Scenario: Metadata equals the result files
- **WHEN** the metadata is parsed and compared with the dev and test summary files
- **THEN** every metric value in it is equal to the value in its result file

#### Scenario: The card is exactly what the files say
- **WHEN** the card is regenerated from the committed model and result files
- **THEN** the output is byte-identical to the committed card

### Requirement: The card's example runs
The card's "How to Get Started" section SHALL contain a code example that loads the model and scores a message. The example SHALL run unchanged against the committed model and return a report.

#### Scenario: The example runs
- **WHEN** the example is extracted from the card and executed against the committed model
- **THEN** it completes and returns a report with a probability between 0 and 1
