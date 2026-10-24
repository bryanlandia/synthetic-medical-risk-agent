from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Styles with a renderer in this package. Reserved names are accepted by the schema
# but rejected at generation time until a later change provides a renderer.
AVAILABLE_STYLES = ("terse", "templated")
RESERVED_STYLES = ("narrative", "ai_scribe")


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
    stale_rate: float = Field(default=0.06, ge=0, le=1)  # per stated lab, templated style only
    omit_absent_symptom_rate: float = Field(default=0.3, ge=0, le=1)

    style_rates: dict[str, float] = Field(default_factory=lambda: {"terse": 0.5, "templated": 0.5})

    @model_validator(mode="after")
    def _check_styles(self) -> "GenConfig":
        known = set(AVAILABLE_STYLES) | set(RESERVED_STYLES)
        unknown = set(self.style_rates) - known
        if unknown:
            raise ValueError(f"unknown styles: {sorted(unknown)}")
        if abs(sum(self.style_rates.values()) - 1.0) > 1e-9:
            raise ValueError("style_rates must sum to 1")
        return self

    def check_styles_available(self) -> None:
        reserved = [s for s, r in self.style_rates.items() if r > 0 and s in RESERVED_STYLES]
        if reserved:
            raise ValueError(
                f"styles {reserved} are reserved: no renderer yet (provided by add-llm-note-writer)"
            )

    def config_hash(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]
