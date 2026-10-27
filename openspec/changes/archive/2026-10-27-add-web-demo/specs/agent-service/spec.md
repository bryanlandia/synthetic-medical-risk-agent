# Spec Delta

## ADDED Requirements

### Requirement: Limit counters can live in a shared store
The service SHALL be able to keep the daily spend total and the per-visitor request counts in a store shared by every instance, reached over HTTPS with credentials from the environment, so that the daily cap and the rate limits hold across instances and restarts. Without a store it SHALL use the process-local counters.

#### Scenario: Two instances share one cap
- **WHEN** two service instances use the same store and together spend past the daily cap
- **THEN** the next request to either instance gets 503

#### Scenario: Two instances share one limit
- **WHEN** one visitor sends 6 requests to each of two instances within a minute
- **THEN** the 11th request in that minute gets 429 with `Retry-After`

### Requirement: Production requires the shared store
When the environment says production, the service SHALL refuse to start unless the shared store is configured, and SHALL name the missing variable, not its value.

#### Scenario: Production without a store
- **WHEN** the service starts in production with no store configured
- **THEN** it exits with an error naming the missing variable
