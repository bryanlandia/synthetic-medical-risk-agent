# Spec Delta

## ADDED Requirements

### Requirement: Results state which targets are met
A results summary SHALL compare each metric with its target in the targets file. It SHALL give the plain fact of whether the value reaches the target in the metric's direction, and a label: clearly met when the whole 95% interval reaches the target, clearly not met when the whole interval falls short, and not distinguishable when the target lies inside the interval.

#### Scenario: The three labels
- **WHEN** summaries are built for a higher-is-better metric with a target of 0.70 and values 0.80 with interval [0.76, 0.84], 0.72 with interval [0.66, 0.78], and 0.60 with interval [0.55, 0.65]
- **THEN** they are labelled clearly met, not distinguishable and clearly not met, and the plain fact is reached, reached and not reached respectively

#### Scenario: A value short of the target inside its interval
- **WHEN** a metric has a target of 0.70, a value of 0.68 and an interval of [0.62, 0.74]
- **THEN** the plain fact is not reached and the label is not distinguishable

#### Scenario: Direction is respected
- **WHEN** a lower-is-better metric such as the Brier score has a target of 0.18, a value of 0.15 and an interval of [0.13, 0.17]
- **THEN** it is labelled clearly met

### Requirement: API-backed systems are deterministic under concurrency
API-backed systems SHALL run their calls concurrently with the trial index and token usage held per call, never in shared state, and a run SHALL give the same transcripts and results at any worker count.

#### Scenario: Same results at one and eight workers
- **WHEN** the same mock API-backed system is run on the same records with one worker and with eight
- **THEN** the transcripts, the results summary and the cache contents are identical

#### Scenario: Trial index and usage belong to the call
- **WHEN** several trials of the same record run concurrently
- **THEN** each call's cache key uses its own trial index and each transcript records its own token counts

#### Scenario: A cap still stops safely
- **WHEN** the call cap is reached during a concurrent run
- **THEN** no more than the cap's calls were made, finished trials are saved and cached, and nothing is lost
