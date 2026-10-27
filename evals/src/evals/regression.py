"""The fast regression subset: no key, no spend. It fails if the oracle misses its ceiling, a grader is broken, or a
reference system's dev results drift from the committed baselines."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .agent_service import REPO_ROOT, _uv
from .records import Dataset
from .report import SCHEMA_PATH, schema_text
from .runner import run_suites
from .selfcheck import self_check
from .summary import summarize
from .systems import FloorSystem, LabOnlySystem, OracleSystem
from .targets import TARGETS_PATH

BASELINES_DIR = Path(__file__).resolve().parents[2] / "results" / "baselines" / "dev"
DRIFT_TOLERANCE = 1e-6


def reference_systems(dataset: Dataset) -> dict[str, Any]:
    return {"oracle": OracleSystem(dataset), "floor": FloorSystem(dataset), "lab_only": LabOnlySystem(dataset)}


def baseline_summaries(dataset: Dataset, log_dir: Path, *, n_boot: int = 1000, seed: int = 0) -> dict[str, dict[str, Any]]:
    """The three reference systems on dev (no protected split is touched)."""
    out = {}
    for name, system in reference_systems(dataset).items():
        run = run_suites(dataset, system, "dev", log_dir=log_dir / name)
        out[name] = summarize(dataset, run, n_boot=n_boot, seed=seed)
    return out


# The agent service's guard tests: every status path, the one-tool-call limit, the output guard, the log check. They use the
# scripted model, need no key and make no network call; if a guard is removed one of them fails.
AGENT_GUARD_TESTS = ("tests/test_guards.py", "tests/test_spend.py", "tests/test_logs.py", "tests/test_config.py",
                     "tests/test_guard.py", "tests/test_agent_flow.py", "tests/test_tools.py")


def agent_guard_failures(timeout: float = 300.0) -> list[str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR")}
    env["UV_PYTHON_PREFERENCE"] = "only-managed"  # no ANTHROPIC_API_KEY is passed on
    try:
        proc = subprocess.run([_uv(), "run", "--project", str(REPO_ROOT / "agent"), "pytest", "-q", "-x", *AGENT_GUARD_TESTS],
                              cwd=REPO_ROOT / "agent", env=env, capture_output=True, text=True, timeout=timeout)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return [f"the agent guard tests could not run: {exc}"]
    if proc.returncode != 0:
        return [f"agent guard tests failed: {(proc.stdout + proc.stderr)[-400:].strip()}"]
    return []


def run_regression(dataset: Dataset) -> list[str]:
    """Returns the list of failures; empty means the regression subset passes."""
    failures: list[str] = agent_guard_failures()
    for name, problem in self_check(dataset, OracleSystem(dataset)).items():
        failures.append(f"grader {name} is broken or the oracle missed its ceiling: {problem}")
    if SCHEMA_PATH.read_text() != schema_text():
        failures.append("the published report schema differs from the model (run `evals schema --write`)")
    if not TARGETS_PATH.exists():
        failures.append("targets file is missing (run `evals baselines`)")
    with tempfile.TemporaryDirectory() as tmp:
        fresh = baseline_summaries(dataset, Path(tmp), n_boot=50)
    for name, summary in fresh.items():
        committed_path = BASELINES_DIR / name / "summary.json"
        if not committed_path.exists():
            failures.append(f"committed baseline for {name} is missing (run `evals baselines`)")
            continue
        committed = {(r["category"], r["metric"]): r["value"] for r in json.loads(committed_path.read_text())["rows"]}
        for row in summary["rows"]:
            was = committed.get((row["category"], row["metric"]))
            if was is None or abs(was - row["value"]) > DRIFT_TOLERANCE:
                failures.append(f"{name} {row['category']}.{row['metric']} drifted: committed {was}, now {row['value']}")
    return failures
