"""Running suites through Inspect and collecting the trials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from inspect_ai import eval as inspect_eval

from . import HARNESS_VERSION
from .inspect_tasks import TrialSink, build_task
from .ledger import PROTECTED, record_final_run
from .protocol import require_frozen
from .records import Dataset
from .suites import SUITE_NAMES, suite_records
from .systems import System
from .transcripts import transcript_rows


@dataclass
class RunResult:
    system_version: str
    split: str
    suites: dict[str, int]  # suite -> number of samples
    sink: TrialSink
    logs: list[Any]
    rows: list[dict[str, Any]]
    stopped: str | None = None  # a call or spend cap ended the run early


def run_suites(dataset: Dataset, system: System, split: str, *, suites: list[str] | None = None, limit: int | None = None,
               trials: int = 1, final: bool = False, log_dir: Path | str = "logs",
               ledger_path: Path | None = None, workers: int = 8, protocol_path: Path | None = None,
               ledger_stage: str | None = None,
               progress: Callable[[str, int, int, TrialSink], None] | None = None) -> RunResult:
    """Run the chosen suites of a split. ``test`` and ``adversarial`` need ``final=True`` and are recorded.
    API-backed systems run ``workers`` samples at a time; the results do not depend on the worker count."""
    if split in PROTECTED and getattr(system, "requires_freeze", False):
        require_frozen(system.prompt_hash, split, protocol_path)
    record_final_run(system.version, split, final=final, path=ledger_path, stage=ledger_stage)
    wanted = suites or list(SUITE_NAMES)
    available = suite_records(dataset, split)
    chosen = {s: (available[s][:limit] if limit else available[s]) for s in wanted if s in available}
    sink = TrialSink()
    if progress:
        sink.on_sample = lambda suite, n: progress(suite, n, len(chosen[suite]) * trials, sink)
    tasks = [build_task(s, dataset, recs, system, sink) for s, recs in chosen.items()]
    logs = inspect_eval(tasks, model="mockllm/model", log_dir=str(log_dir), display="none", epochs=trials,
                        log_samples=True, fail_on_error=True,
                        max_samples=workers if getattr(system, "threaded", False) else 64)
    sink.settle()
    if (cache := getattr(system, "cache", None)) is not None:
        cache.compact()  # sorted by key: the committed cache does not depend on which worker finished first
    run_info = {"split": split, "harness_version": HARNESS_VERSION, "dataset_config_hash": dataset.config_hash}
    rows = transcript_rows(dataset, sink, run=run_info)
    return RunResult(system.version, split, {s: len(r) for s, r in chosen.items()}, sink, logs, rows, sink.stopped)
