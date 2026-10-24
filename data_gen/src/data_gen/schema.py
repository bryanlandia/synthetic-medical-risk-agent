"""Record schema. A record has two views:

- ``input``: what a model or the agent may see (lab panel + note). No flags, probability or label.
- ``ground_truth``: symptom flags, true probability, label. For scoring and evaluation only.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from . import DISEASE_NAME, GENERATOR_VERSION, PLAN_VERSION, SCHEMA_VERSION, SYNTHETIC_NOTICE

Split = Literal["train", "test", "adversarial"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabEntry(Strict):
    lab: str
    value: float | None  # None = missing from the panel
    unit: str


class Annotation(Strict):
    """A labeled noise instance or case tag, e.g. type='unit_mismatch', lab='serum_k17'."""

    type: str
    lab: str | None = None
    flag: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class PlanLab(Strict):
    lab: str
    value: float  # the number the note states, in the unit it states
    unit: str


class PlanSymptom(Strict):
    flag: str
    stated: Literal["present", "hedged", "negated"]  # unmentioned flags are simply absent


class PlanInjection(Strict):
    id: str
    category: str
    goal: str
    text: str


class NotePlan(Strict):
    """Versioned, style-agnostic description of what a note says. Renderers (and later an LLM
    writer) turn it into text; noise and case tags are decided here, never by the renderer."""

    version: str
    style: str
    labs: list[PlanLab]
    symptoms: list[PlanSymptom]
    injection: PlanInjection | None = None
    render_seed: int


class ModelInput(Strict):
    patient_id: str
    panel: list[LabEntry]
    note: str


class GroundTruth(Strict):
    labs: dict[str, float]  # true underlying values (the panel may differ or be missing)
    flags: dict[str, bool]
    true_probability: float = Field(ge=0.0, le=1.0)
    label: Literal[0, 1]


class Record(Strict):
    synthetic: Literal[True] = True
    disease: str = DISEASE_NAME
    notice: str = SYNTHETIC_NOTICE
    schema_version: str = SCHEMA_VERSION
    generator_version: str = GENERATOR_VERSION
    plan_version: str = PLAN_VERSION
    seed: int
    patient_id: str
    split: Split
    style: str
    input: ModelInput
    ground_truth: GroundTruth
    plan: NotePlan | None = None  # evaluation metadata, not part of the model input
    tags: list[Annotation] = Field(default_factory=list)
    noise: list[Annotation] = Field(default_factory=list)

    def input_view(self) -> dict[str, Any]:
        return self.input.model_dump(mode="json")

    def tag_types(self) -> set[str]:
        return {t.type for t in self.tags}

    def noise_types(self) -> set[str]:
        return {n.type for n in self.noise}
