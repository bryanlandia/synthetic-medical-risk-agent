"""Rules for LLM-based graders. Code-based graders come first; an LLM judge is allowed only for a check that cannot
be done mechanically, and it must be independent, specified and calibrated before its result counts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CALIBRATION_PATH = Path(__file__).resolve().parents[2] / "results" / "calibration.json"
MIN_CALIBRATION_SAMPLE = 30  # human-labelled transcripts
MIN_AGREEMENT = 0.8


class SameModelGrader(RuntimeError):
    """An LLM grader was configured with the model it would grade."""


@dataclass(frozen=True)
class LLMGraderSpec:
    name: str
    model: str
    rubric: str
    dimension: str  # one judge per dimension
    allow_unknown: bool = True  # an explicit "unknown" outcome, to reduce hallucinated verdicts

    def __post_init__(self) -> None:
        if not self.rubric.strip():
            raise ValueError(f"LLM grader {self.name} needs a written rubric")
        if not self.allow_unknown:
            raise ValueError(f"LLM grader {self.name} must allow an 'unknown' outcome")
        if not self.dimension.strip() or "," in self.dimension or " and " in self.dimension:
            raise ValueError(f"LLM grader {self.name} must judge one dimension")


def check_independent(grader: LLMGraderSpec, system_model: str) -> None:
    if grader.model == system_model:
        raise SameModelGrader(f"LLM grader {grader.name} uses {grader.model}, the model it grades; an independent "
                              "model is required")


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def is_calibrated(grader: LLMGraderSpec, path: Path = CALIBRATION_PATH) -> bool:
    entry = load_calibration(path).get(grader.name)
    return bool(entry and entry.get("n", 0) >= MIN_CALIBRATION_SAMPLE and entry.get("agreement", 0) >= MIN_AGREEMENT)


def label_results(graders: list[LLMGraderSpec], results: dict[str, Any], path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    """Mark each LLM grader's result calibrated or uncalibrated; only calibrated ones may enter headline numbers."""
    out = {}
    for g in graders:
        ok = is_calibrated(g, path)
        out[g.name] = {"result": results.get(g.name), "calibrated": ok, "headline": ok,
                       "label": "calibrated" if ok else "uncalibrated: excluded from headline numbers"}
    return out
