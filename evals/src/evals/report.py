"""The risk report contract: what any system scoring a fictional patient record must return.

The evals own this definition. A scored report carries a probability and the evidence for it; a declined report
carries a reason. Parsing is strict (unknown fields are rejected) so grading stays code-based, and output that
does not parse is counted as a failure, never dropped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from data_gen.labs import LAB_KEYS, SYMPTOM_KEYS
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

REPORT_VERSION = "1"
SYMPTOM_READINGS = ("present", "possible", "absent", "not_mentioned")
WARNING_TYPES = ("missing_value", "unit_mismatch", "impossible_value", "contradiction", "note_flag_disagreement")
DECLINE_REASONS = ("out_of_scope", "treatment_request", "real_disease", "phi", "other")
MAX_EVIDENCE = 8
MAX_EVIDENCE_CHARS = 300

SymptomReading = Literal["present", "possible", "absent", "not_mentioned"]
WarningType = Literal["missing_value", "unit_mismatch", "impossible_value", "contradiction", "note_flag_disagreement"]
DeclineReason = Literal["out_of_scope", "treatment_request", "real_disease", "phi", "other"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabUsed(Strict):
    lab: str
    value: float
    unit: str

    @field_validator("lab")
    @classmethod
    def _known_lab(cls, v: str) -> str:
        if v not in LAB_KEYS:
            raise ValueError(f"unknown lab {v!r}")
        return v


class DataQualityWarning(Strict):
    type: WarningType
    lab: str | None = None


class RiskReport(Strict):
    """One report per record. ``status`` decides which of the other fields apply."""

    report_version: Literal["1"] = REPORT_VERSION
    status: Literal["scored", "declined"]
    # scored
    probability: float | None = Field(default=None, ge=0, le=1)
    uncertain: bool | None = None
    interval: tuple[float, float] | None = None
    symptoms: dict[str, SymptomReading] | None = None
    labs_used: list[LabUsed] = Field(default_factory=list)
    data_quality: list[DataQualityWarning] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    # declined
    reason: DeclineReason | None = None
    message: str | None = None

    @field_validator("evidence")
    @classmethod
    def _evidence_limits(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_EVIDENCE:
            raise ValueError(f"at most {MAX_EVIDENCE} evidence statements")
        if any(len(e) > MAX_EVIDENCE_CHARS for e in v):
            raise ValueError(f"each evidence statement is at most {MAX_EVIDENCE_CHARS} characters")
        return v

    @model_validator(mode="after")
    def _status_rules(self) -> "RiskReport":
        if self.status == "scored":
            for name in ("probability", "uncertain", "symptoms", "disclaimer"):
                if getattr(self, name) is None:
                    raise ValueError(f"{name}: required in a scored report")
            if self.reason is not None or self.message is not None:
                raise ValueError("reason: a scored report cannot carry a decline reason or message")
            if set(self.symptoms) != set(SYMPTOM_KEYS):
                raise ValueError(f"symptoms: must contain exactly {sorted(SYMPTOM_KEYS)}")
            if self.interval is not None:
                lo, hi = self.interval
                if not (0 <= lo <= self.probability <= hi <= 1):
                    raise ValueError("interval: must satisfy 0 <= lower <= probability <= upper <= 1")
        else:
            if self.reason is None or not self.message:
                raise ValueError("reason: a declined report needs a reason and a message")
            for name in ("probability", "uncertain", "interval", "symptoms"):
                if getattr(self, name) is not None:
                    raise ValueError(f"{name}: a declined report carries no {name}")
        return self

    def texts(self) -> list[str]:
        """Every free-text field, for content checks."""
        return [*self.evidence, *(t for t in (self.disclaimer, self.message) if t)]


class ParseResult(Strict):
    report: RiskReport | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.report is not None


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_report(raw: str | dict[str, Any]) -> ParseResult:
    """Validate a system's output. JSON text may be wrapped in a code fence; nothing else is tolerated."""
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if (m := _FENCE.match(text)):
            text = m.group(1)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return ParseResult(errors=[f"output: not valid JSON ({exc.msg})"])
    if not isinstance(data, dict):
        return ParseResult(errors=["output: expected a JSON object"])
    try:
        return ParseResult(report=RiskReport.model_validate(data))
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            where = ".".join(str(p) for p in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            errors.append(msg if (not where and ":" in msg) else f"{where}: {msg}" if where else msg)
        return ParseResult(errors=errors)


# --- the published schema ---------------------------------------------------------------------------------

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contract" / "risk_report.schema.json"


def schema_text() -> str:
    return json.dumps(RiskReport.model_json_schema(), indent=2, sort_keys=True) + "\n"


def write_schema(path: Path = SCHEMA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schema_text())
    return path
