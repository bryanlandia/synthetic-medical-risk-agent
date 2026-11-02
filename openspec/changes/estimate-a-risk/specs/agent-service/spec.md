# Spec Delta

## ADDED Requirements

### Requirement: An estimate endpoint takes structured inputs
The service SHALL expose `POST /estimate` taking JSON with a `labs` object giving, for each of the eight labs, a number in the lab's usual unit or null, and a `symptoms` object giving, for each of the five symptoms, `absent`, `possible` or `present`, and no other field. It MUST NOT call a language model and each request SHALL be independent.

#### Scenario: Bad inputs
- **WHEN** a lab is outside its plausible range, a symptom state is unknown, a lab or symptom is missing, or there is an extra field
- **THEN** the status is 422 and nothing is computed

#### Scenario: No model call
- **WHEN** valid inputs are posted with the right secret
- **THEN** the response is served and no model is called

### Requirement: An estimate response carries the estimate and what produced it
A successful `/estimate` response SHALL carry `request_id`, `probability`, `band`, a signed `breakdown` with its starting point, the generated `message`, and `model_hash`.

#### Scenario: An estimate
- **WHEN** valid inputs are posted with the right secret
- **THEN** the response has a probability, a band, a breakdown that sums with its starting point to the model's score, the message, and the model hash

### Requirement: The estimate endpoint is guarded and limited apart from the assistant
`/estimate` SHALL require the shared secret before any computation, SHALL cap its body size, and SHALL be rate limited per client in its own counter, separate from the counters for `/analyze` and `/packet`, at no more than 120 requests per minute and 5,000 per day. Its requests MUST NOT count toward the assistant's limits or the daily spend, and the assistant's requests MUST NOT count toward its limits.

#### Scenario: Wrong secret
- **WHEN** an estimate request has no secret or a wrong one
- **THEN** the status is 401

#### Scenario: Moving a slider does not use the assistant's allowance
- **WHEN** a client sends 100 estimate requests in a minute and then one analyze request
- **THEN** all 101 are served

#### Scenario: Its own limit
- **WHEN** a client sends 121 estimate requests in a minute
- **THEN** the first 120 are served and the 121st gets 429 with `Retry-After`

### Requirement: The estimate endpoint logs no inputs
The service SHALL log an estimate request's size, timing and outcome only, never its inputs or its message.

#### Scenario: A logged request
- **WHEN** an estimate is served and the log line is read
- **THEN** it holds a request id, a status and a duration, and none of the input values
