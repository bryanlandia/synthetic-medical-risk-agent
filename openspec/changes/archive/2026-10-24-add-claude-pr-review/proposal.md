# Proposal

## Why

The project is built mostly through AI-assisted changes, and an independent reviewer on every pull request catches mistakes before they reach `main`. Setting this up now, before more PRs land, means the generator change already open as PR #1 and every later change (LLM note writer, training, agent, evals) get a second look. Review quality and cost depend on configuration (model, effort, scope), so it should be a deliberate, tested step and not an afterthought.

## What Changes

- Add a GitHub Actions workflow that runs Claude as a pull request reviewer using the official `anthropics/claude-code-action`, authenticated with an Anthropic API key stored as a repository secret.
- Pin the reviewer to Claude Sonnet 5.5 at medium effort (chosen over Opus 5.5 to keep each review cheap; see design).
- Run on pull requests that are opened, updated, reopened, or marked ready for review, and post findings on the PR as inline comments (or one summary comment when nothing is found). Draft PRs are skipped.
- Keep the reviewer advisory: it is not a required check and never blocks merging.
- Bound cost and blast radius: least-privilege workflow permissions, one run per PR at a time with older runs cancelled, a job timeout, a turn limit, and path exclusions for generated data and lockfiles.
- Add project-specific review criteria in a dedicated guidelines file that the reviewer is told to follow (synthetic-data constraint, no real medical advice, spec alignment, ignore generated data).
- Document the one-time manual setup: install the Claude GitHub App, store the API key secret, and set a spend limit in the Anthropic Console.
- Verify end to end with a throwaway pull request that contains a deliberate defect.

## Capabilities

### New Capabilities
- `pr-review-automation`: automatic, advisory, cost-bounded, least-privilege AI review of pull requests, including which PRs are reviewed, which model and effort are used, how credentials are handled, and what criteria the reviewer applies.

### Modified Capabilities

None.

## Out of scope

- Blocking merges on review results, required status checks, or branch protection rules.
- `@claude` mention-driven interactive runs, issue-to-PR automation, and any workflow that lets Claude push commits.
- Reviewing pull requests from forks. GitHub withholds secrets from fork-triggered runs on public repositories, so fork PRs get no automated review.
- Other CI (tests, lint, evals); those belong to later changes.
- Cloud-provider authentication (Bedrock, Vertex, Foundry) and organization-level rollout.
- Changes to application code, the data generator, or AGENTS.md.

## Eval categories affected

None directly. This is repository tooling. Reviews of later changes will cover eval code and datasets, so the review guidelines include checks relevant to the safety, adversarial, and data-quality eval categories.

## Impact

- New files: a workflow under `.github/workflows/`, a review guidelines file, and setup notes. No application code changes.
- New external dependencies: the `anthropics/claude-code-action` GitHub Action and the `code-review` plugin it installs at run time, both third-party code run with access to PR contents.
- New spend: Anthropic API tokens per review (Sonnet 5.5) and GitHub Actions minutes. Mitigated by turn limit, concurrency, timeouts, path exclusions, and a Console spend limit.
- New secret: `ANTHROPIC_API_KEY` repository secret, supplied by the repository owner at setup time and never written to a file.
- Requires a repository admin to install the Claude GitHub App (a browser step).
