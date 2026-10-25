from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Template rendering provides these styles; they are test fixtures.
AVAILABLE_STYLES = ("terse", "templated")
# LLM-written notes use these clinician-authored documentation settings.
LLM_SETTINGS = ("shorthand", "ehr_template", "ai_scribe", "copy_forward")
# Styles whose notes may carry stale copied-forward lab values.
STALE_VALUE_STYLES = ("templated", "copy_forward")

NoteSource = Literal["template", "llm"]


def supported_styles(source: str) -> tuple[str, ...]:
    return AVAILABLE_STYLES if source == "template" else LLM_SETTINGS


class LLMConfig(BaseModel):
    """Settings for LLM-written notes. Holds no secret: the API key comes only from the environment."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = "claude-haiku-5-5"
    prompt_version: str = Field(default="1", min_length=1)
    max_attempts: int = Field(default=3, ge=1, le=10)  # writing attempts per note
    # Output limit per note. Thinking tokens count against it, and a limit that is too small silently
    # truncates notes (the first pilot lost most ehr_template notes at 700), so keep generous headroom.
    max_tokens: int = Field(default=2000, ge=50, le=8000)
    max_calls: int = Field(default=25000, ge=1)  # hard cap on LLM calls, full run
    max_spend_usd: float = Field(default=15.0, gt=0)  # hard cap on estimated spend, full run
    pilot_max_calls: int = Field(default=600, ge=1)  # separate small cap for the pilot
    pilot_max_spend_usd: float = Field(default=1.0, gt=0)
    pilot_per_setting: int = Field(default=20, ge=1)
    pilot_controls: int = Field(default=8, ge=0)  # template-fixture control notes in the rating sheet
    matched_pairs: int = Field(default=200, ge=0)  # test patients written in all four settings
    exclusion_threshold: float = Field(default=0.15, ge=0, le=1)  # max pilot exclusion rate per setting
    concurrency: int = Field(default=8, ge=1, le=32)  # parallel API calls; never changes the data
    # Prices in USD per million tokens, used only for estimates and the spend cap.
    price_input_per_mtok: float = Field(default=0.10, ge=0)
    price_output_per_mtok: float = Field(default=0.50, ge=0)


def _default_rates(source: str) -> dict[str, float]:
    styles = supported_styles(source)
    return {s: 1 / len(styles) for s in styles}


class GenConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=20261, ge=0)
    n_train: int = Field(default=4000, ge=1)
    n_test: int = Field(default=1000, ge=1)
    n_per_adversarial_type: int = Field(default=60, ge=1)
    target_prevalence: float = Field(default=0.30, gt=0.02, lt=0.98)

    # Noise rates for train / random test notes (adversarial cases are constructed explicitly).
    missing_rate: float = Field(default=0.05, ge=0, le=1)  # per lab
    hedge_rate: float = Field(default=0.25, ge=0, le=1)  # per present symptom
    unit_mismatch_rate: float = Field(default=0.08, ge=0, le=1)  # per stated lab with an alt unit
    stale_rate: float = Field(default=0.06, ge=0, le=1)  # per stated lab, stale-value styles only
    omit_absent_symptom_rate: float = Field(default=0.3, ge=0, le=1)

    note_source: NoteSource = "template"
    style_rates: dict[str, float] = Field(default_factory=lambda: {"terse": 0.5, "templated": 0.5})
    llm: LLMConfig = Field(default_factory=LLMConfig)

    @model_validator(mode="before")
    @classmethod
    def _default_style_rates(cls, data):
        # With the LLM source, an unspecified style_rates means equal shares of the four settings.
        if isinstance(data, dict) and data.get("note_source") == "llm" and "style_rates" not in data:
            data = {**data, "style_rates": _default_rates("llm")}
        return data

    @model_validator(mode="after")
    def _check_styles(self) -> "GenConfig":
        if abs(sum(self.style_rates.values()) - 1.0) > 1e-9:
            raise ValueError("style_rates must sum to 1")
        self.check_styles_available()
        return self

    def check_styles_available(self) -> None:
        """Reject styles that the configured note source cannot produce, before any record exists."""
        supported = supported_styles(self.note_source)
        unsupported = sorted(s for s, r in self.style_rates.items() if r > 0 and s not in supported)
        unknown = sorted(s for s in self.style_rates if s not in AVAILABLE_STYLES + LLM_SETTINGS)
        if unknown:
            raise ValueError(f"unknown styles: {unknown}")
        if unsupported:
            raise ValueError(
                f"style(s) {unsupported} are not supported by note_source {self.note_source!r} "
                f"(supported: {', '.join(supported)})"
            )

    def canonical_dump(self) -> dict:
        """JSON-ready config. Fields added after the first dataset are omitted while they hold their
        defaults, so existing manifests and config hashes stay byte-identical."""
        data = self.model_dump(mode="json")
        data["llm"].pop("concurrency", None)  # speed only: the worker count cannot change the dataset
        for name in ("note_source", "llm"):
            default = type(self).model_fields[name].get_default(call_default_factory=True)
            default_dump = default.model_dump(mode="json") if isinstance(default, BaseModel) else default
            if name == "llm":
                default_dump = {k: v for k, v in default_dump.items() if k != "concurrency"}
            if data[name] == default_dump:
                data.pop(name)
        return data

    def config_hash(self) -> str:
        blob = json.dumps(self.canonical_dump(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]
