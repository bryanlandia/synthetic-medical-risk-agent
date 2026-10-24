# Claude PR review

Pull requests in this repository get an automatic, **advisory** review from Claude Sonnet 5.5 at medium effort. The workflow is [.github/workflows/claude-pr-review.yml](../.github/workflows/claude-pr-review.yml) and uses the official `anthropics/claude-code-action`. Review criteria are in [.claude/review-guidelines.md](../.claude/review-guidelines.md).

## What is reviewed

- Reviewed: non-draft pull requests from branches in this repository, when opened, updated, reopened or marked ready for review.
- Skipped: drafts, fork pull requests, and pull requests that change only `data_gen/data/**` or lockfiles. Fork pull requests get no review because GitHub withholds secrets from fork-triggered runs on public repositories.
- The review plugin also skips trivial or automated pull requests and pull requests that already have a review comment from Claude, so later pushes are usually not re-reviewed.
- The review is advisory. It is not a required check and has no power to approve, request changes, merge or push; its only write tool posts inline comments.

## One-time setup (repository owner)

1. **Create a dedicated API key and set a spend limit.** In the Anthropic Console, create a key used only for this workflow and set a monthly spend limit before enabling the workflow. That limit is the real cost cap.
2. **Install the Claude GitHub App** on this repository (https://github.com/apps/claude). It needs repository admin and is a browser step.
3. **Store the key as a repository secret** named `ANTHROPIC_API_KEY`. Run this in your own terminal so the key is never pasted into chat or written to a file, and paste the key when prompted:

   ```sh
   gh secret set ANTHROPIC_API_KEY
   gh secret list   # shows the secret name only
   ```

## Cost and limits

Each run is bounded by `--max-turns`, a 15 minute job timeout, one run per pull request at a time (older runs are cancelled), and the path exclusions above. The workflow first ran on Opus 5.5 and was switched to Sonnet 5.5 to cut the price per review. The figures below were measured on **Opus 5.5** (plus the Sonnet and Haiku helper agents the review plugin starts) on a small test pull request with two files and two seeded defects; Sonnet 5.5 figures are recorded after the switch is verified (task 7.3).

| Attempt | Total cost | Model time | Turns | Result |
|---|---|---|---|---|
| 1 | $0.44 | 51 s | 13 | ran, posted nothing |
| 2 (rerun) | $0.50 | 93 s | 16 | two inline comments, both defects found |

Wall-clock time for the whole job was about 1.5 to 2.5 minutes. Larger pull requests will cost more; the turn limit, 15 minute timeout and Console spend limit bound it.

Reliability: the same pull request produced no comments on one attempt and the correct comments on the rerun, so a single quiet run does not prove a pull request is clean. Re-run the job (or push a commit) if a review looks missing. The agent's individual steps are not visible in the run log (`show_full_output` is off), and the result reported 2 to 3 denied tool permissions per run whose cause is not yet known. The `--effort medium` flag is passed to the action but is not echoed in the log, so it can be confirmed only from the workflow file. (`medium` is also Sonnet 5.5's default level, so the flag documents the intent.)

## Checking the setup

The workflow's properties from the spec (triggers, permissions, pinned actions, model, effort, limits, no key in the repository) are checked by a script:

```sh
uv run .github/scripts/check_pr_review_workflow.py              # check the repository
uv run .github/scripts/check_pr_review_workflow.py --self-test  # prove each check can fail
```

If `uv` hangs while searching for Python, your shell may have a stale `VIRTUAL_ENV`. Run it with `env -u VIRTUAL_ENV` and `UV_PYTHON` set to a managed Python 3.12.

## Disable or uninstall

- Pause: disable the "Claude PR review" workflow under the repository's Actions settings.
- Uninstall: delete `.github/workflows/claude-pr-review.yml`, delete the `ANTHROPIC_API_KEY` secret (and revoke the key in the Anthropic Console, since deleting the secret does not revoke it), and uninstall the Claude GitHub App from the repository settings if no other Claude feature uses it.

## Known behavior

- Workflow changes are not reviewed: the action skips (and the job still shows success) on any pull request that adds or edits the workflow file, because the file must match the one on `main`. This is why the first pull request that added it got no review. Review changes to `.github/workflows/claude-pr-review.yml` by hand.
- The plugin and its marketplace are fetched from a git URL at run time. They run with access to the pull request contents and the API key.
- Review text may be wrong or noisy. Treat it as a second opinion.
