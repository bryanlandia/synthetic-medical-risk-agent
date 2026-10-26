"""Running a system over records: the trial loop that produces transcripts. Graders and Inspect wrap this."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from data_gen.schema import Record

from .records import input_view
from .report import RiskReport, parse_report
from .systems import System


@dataclass
class Trial:
    """One attempt at one task: everything needed to read it later."""

    record_id: str
    system_version: str
    trial_index: int
    raw_output: str
    report: RiskReport | None
    errors: list[str]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    graders: dict[str, Any] = field(default_factory=dict)

    @property
    def parsed(self) -> bool:
        return self.report is not None

    def to_json(self) -> dict[str, Any]:
        row = asdict(self)
        row["report"] = self.report.model_dump(mode="json") if self.report else None
        return row


def _set_trial(system: System, trial_index: int) -> None:
    setter = getattr(system, "set_trial", None)
    if setter:
        setter(trial_index)


def run_trial(system: System, record: Record, trial_index: int = 0) -> Trial:
    view = input_view(record)
    _set_trial(system, trial_index)
    started = time.perf_counter()
    raw = system.run(view)
    latency = time.perf_counter() - started
    raw_text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True)
    result = parse_report(raw)
    usage = getattr(system, "last_usage", None) or {}
    return Trial(record.patient_id, system.version, trial_index, raw_text, result.report, result.errors,
                 int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)), latency)


def run_system(system: System, records: list[Record], trials: int = 1) -> list[Trial]:
    return [run_trial(system, r, t) for r in records for t in range(trials)]


def run_view(system: System, view: dict[str, Any], record_id: str, trial_index: int = 0) -> Trial:
    """Run a system on an explicit view (used for the injection counterfactual, where the view is altered)."""
    from .records import assert_clean_view

    assert_clean_view(view)
    _set_trial(system, trial_index)
    started = time.perf_counter()
    raw = system.run(view)
    latency = time.perf_counter() - started
    raw_text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True)
    result = parse_report(raw)
    usage = getattr(system, "last_usage", None) or {}
    return Trial(record_id, system.version, trial_index, raw_text, result.report, result.errors,
                 int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)), latency)
