# Spec Delta

## Purpose

Defines how the demo is deployed and kept safe to leave public: where each part runs, where each secret lives, the limits that bound spend, and the check that proves a deployment works.

## ADDED Requirements

### Requirement: The demo runs on one platform
The web app and the agent service SHALL be deployed from this repository on Vercel, with no other host. The service SHALL run unchanged from the code that the evaluations score, and the deployed model hash SHALL equal the committed one.

#### Scenario: The deployed service reports the committed model
- **WHEN** the deployed service's health check is read
- **THEN** its model hash equals the hash in the committed model manifest

### Requirement: A spike decides the platform before the page is built
Before the web page is built, a deployment of the real service SHALL be measured for whether it runs, its bundle size and its cold-start time, and the results SHALL be recorded in the design. If it does not run within the platform's limits, work SHALL stop and the design SHALL name the replacement host first.

#### Scenario: The spike is recorded
- **WHEN** the spike task is complete
- **THEN** the design states the bundle size, the cold-start time and whether the service ran

### Requirement: Secrets live only in the platform environment
The API key, the shared secret and the store credentials SHALL be set only as platform environment variables, never in a committed file or in client code. Only the production environment SHALL hold the API key; preview deployments SHALL use the scripted test model.

#### Scenario: A preview has no key
- **WHEN** a preview deployment's configuration is read
- **THEN** it has the scripted model enabled and no API key

### Requirement: Public limits bound the spend
The production configuration SHALL set a daily spend cap of at most $1, a per-visitor rate limit of at most 10 requests per minute and 200 per day, and the shared store, and the README SHALL document each variable and how a client should handle `Retry-After`.

#### Scenario: Limits documented and set
- **WHEN** the deployment guide is read against the production configuration
- **THEN** every environment variable is listed with its purpose and the cap and limits are within the stated bounds

### Requirement: A deployed smoke test proves a deployment
A documented command SHALL check a deployment with a health request, one scored request and one declined request, using the shared secret from the environment, and SHALL fail if the model hash, the scored report or the decline is wrong.

#### Scenario: Smoke test on the deployment
- **WHEN** the smoke test runs against the deployed service
- **THEN** it passes only if the hash matches, the scored request returns a report and the treatment request is declined
