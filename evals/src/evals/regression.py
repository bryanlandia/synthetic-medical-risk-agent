"""The fast regression subset: no key, no spend. It fails if the oracle misses its ceiling, a grader is broken, or a
reference system's dev results drift from the committed baselines."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

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


def run_regression(dataset: Dataset) -> list[str]:
    """Returns the list of failures; empty means the regression subset passes."""
    failures: list[str] = []
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
