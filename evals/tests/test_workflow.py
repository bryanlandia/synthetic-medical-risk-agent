"""The CI workflow's safety properties: no secret, no fork-secret trigger, read-only, actions pinned by SHA."""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evals.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_it_runs_on_pull_requests_only_and_never_with_secrets(workflow):
    triggers = workflow.get(True) or workflow["on"]  # YAML reads a bare `on` key as True
    assert set(triggers) == {"pull_request"}
    text = WORKFLOW.read_text()
    assert "secrets." not in text and "pull_request_target" not in text and "id-token" not in text


def test_permissions_are_read_only(workflow):
    assert workflow["permissions"] == {}
    for job in workflow["jobs"].values():
        assert job["permissions"] == {"contents": "read"}


def test_every_action_is_pinned_by_commit_sha(workflow):
    uses = [s["uses"] for job in workflow["jobs"].values() for s in job["steps"] if "uses" in s]
    assert uses and all(re.fullmatch(r".+@[0-9a-f]{40}", u) for u in uses), uses


def test_it_runs_the_harness_tests_and_the_regression_subset_with_no_key(workflow):
    steps = [s for job in workflow["jobs"].values() for s in job["steps"]]
    runs = [s["run"] for s in steps if "run" in s]
    assert "uv run pytest -q" in runs and "uv run evals regression" in runs
    for s in steps:
        if "run" in s and "pytest" in s["run"] or "regression" in s.get("run", ""):
            assert s["env"]["ANTHROPIC_API_KEY"] == ""
    assert "--frozen" in "".join(runs)  # the lock file decides what is installed
