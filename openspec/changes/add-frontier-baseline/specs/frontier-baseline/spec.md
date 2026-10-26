# Spec Delta

## Purpose

Defines the frontier-model baseline that the fine-tuned model must beat: how the prompted model returns the risk report, what its prompt may contain, how the prompt is developed on dev with a small budget, how it is scored once on the protected splits, and what its results report must show.

## ADDED Requirements

### Requirement: The baseline returns the report through a tool
The baseline SHALL call the model with one tool whose input schema is the risk report contract, and SHALL take the report from that tool call. The request MUST NOT force a tool choice or set sampling parameters. A reply with no tool call, or a refusal, SHALL be scored as an invalid report.

#### Scenario: Request shape
- **WHEN** the baseline's request for a record is captured in a test
- **THEN** it contains exactly one tool whose schema equals the committed report schema, no forced tool choice, no temperature or other sampling parameter, and the record's input view as the only record content

#### Scenario: Report from the tool call
- **WHEN** the model replies with a tool call carrying a valid report
- **THEN** that input is the report, and the transcript keeps the raw call

#### Scenario: Missing tool call is a failure
- **WHEN** the model replies with text only, or with a refusal
- **THEN** the trial is an invalid report, counted in the parse-failure rate and graded as a failure, never retried silently into a pass

### Requirement: The prompt is a briefing, not the answer key
The baseline prompt SHALL contain the contract rules, the lab and symptom vocabulary with units and reference ranges, the conventions for data-quality warnings and uncertainty, the safety rules, an instruction to treat note text as data and never as instructions, and a qualitative disease briefing. It MUST NOT contain any number from the hidden scoring rule, any record from any split, or any ground-truth value.

#### Scenario: No numbers from the hidden rule
- **WHEN** the prompt text is scanned for every weight, the intercept and any threshold of the scoring rule, written as a decimal or as a fraction
- **THEN** none is found, and the briefing states direction and relative importance in words only

#### Scenario: No record content
- **WHEN** the prompt text is scanned for every patient id and for every sentence of every note in the train, test and adversarial splits
- **THEN** none is found

#### Scenario: Notes are data
- **WHEN** the prompt is read
- **THEN** it tells the model that text inside a note is part of the record, not an instruction, and that no instruction in a note may change the report

### Requirement: Prompt iteration is capped, dev-only and recorded
Prompt versions SHALL be scored on dev only, at most five in total, and each SHALL be recorded with its text hash, model, dev metrics, cost and the decision taken. One of the scored versions, normally the best on dev, is frozen as the final prompt. A sixth version, or any scoring of `test` or `adversarial` before a prompt is frozen, SHALL be refused.

#### Scenario: Versions are recorded
- **WHEN** a prompt version is scored on dev
- **THEN** the record file gains an entry with the hash, model, metrics with intervals, spend and a decision (iterate or freeze), and the entry cannot be altered by a later run

#### Scenario: Sixth version refused
- **WHEN** five versions are recorded and a sixth is requested
- **THEN** the run is refused and says the budget is spent

#### Scenario: Protected splits need a frozen prompt
- **WHEN** a final run on `test` or `adversarial` is requested before a prompt is frozen, or with a prompt whose hash differs from the frozen one
- **THEN** the run is refused

### Requirement: Final runs are one look
The final system SHALL be scored once on `test` and once on `adversarial` with the same model and frozen prompt, each recorded in the ledger, with three trials on the matched-pair subset for pass^3, and once on dev with the same model for comparison. The final model SHALL differ from the development model only by the model id.

#### Scenario: One final run each
- **WHEN** the final runs are complete
- **THEN** the ledger holds one entry for the final system version on `test` and one on `adversarial`, and a repeated final run is refused unless explicitly forced and warned about

#### Scenario: Same prompt, only the model changes
- **WHEN** the development system and the final system are compared
- **THEN** their prompt hashes are equal and only the model id differs

### Requirement: Each stage has a spend cap and an estimate
Every stage (a dev pass, the dev comparison run, the final runs) SHALL have a configured spend cap and call cap, SHALL print a dry-run estimate with no key, and SHALL refuse to start when the estimate exceeds the cap unless the cap is raised explicitly.

#### Scenario: Estimate before spending
- **WHEN** a stage is started without an explicit go-ahead
- **THEN** the estimated calls, tokens and cost are printed and no paid call is made

#### Scenario: Over-cap stage is refused
- **WHEN** a stage's estimate exceeds its cap
- **THEN** the run refuses to start and names the cap and the estimate

### Requirement: The baseline report states results against targets and records what was read
The baseline's results SHALL list every category and metric with its value, 95% interval, n and minimum detectable difference, the model ids, the frozen prompt hash and the total spend, and SHALL state for each metric whether targets v1 are met. A reading file SHALL record, for each grader the baseline fails, that at least 10 failing transcripts (or all, if fewer) were read, and what they showed, including any case where the grader rather than the model was at fault.

#### Scenario: Report content
- **WHEN** the baseline report is generated
- **THEN** it has a row per metric with the value, interval, n, minimum detectable difference and target status, the dev, test and adversarial results are labelled, and it names the models, the prompt hash and the spend

#### Scenario: Failures were read
- **WHEN** the baseline fails a grader
- **THEN** the reading file has an entry for that grader with the number of transcripts read (at least 10, or all if fewer) and a finding, and the report is marked incomplete without it
