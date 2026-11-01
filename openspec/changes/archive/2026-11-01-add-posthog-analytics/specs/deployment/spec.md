# Spec Delta

## ADDED Requirements

### Requirement: Analytics runs only in production
The analytics project key and host SHALL be set only in the web project's production environment and SHALL be documented with the other variables. Preview deployments and local runs MUST NOT have them.

#### Scenario: A preview has no analytics key
- **WHEN** a preview deployment's configuration is read
- **THEN** it has no analytics key and the page records nothing
