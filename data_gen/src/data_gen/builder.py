"""Assemble complete records (input view + ground truth + labeled noise) for all splits."""

from __future__ import annotations

from . import SCHEMA_VERSION, SCHEMA_VERSION_LLM
from .adversarial import generate_adversarial
from .cohort import Patient, generate_cohort
from .config import GenConfig
from .labs import LABS
from .plan import PlannedNote, plan_note
from .render import render
from .schema import Annotation, GroundTruth, LabEntry, ModelInput, Record
from .seeds import rng_for


def plan_for(cfg: GenConfig, patient: Patient, case: str | None) -> PlannedNote:
    return plan_note(cfg, patient.labs, patient.flags, rng_for(cfg.seed, "noise", patient.index), case)


def assemble_record(
    cfg: GenConfig, patient: Patient, split: str, case: str | None, planned: PlannedNote, note: str,
    *, patient_id: str | None = None, pair_group: str | None = None,
) -> Record:
    """Combine a plan and its note text into a record. ``patient_id`` overrides the patient's own id
    (matched-pair members get distinct ids that share a ``pair_group``)."""
    pid = patient_id or patient.patient_id
    panel = [
        LabEntry(
            lab=lab.key,
            value=None if lab.key in planned.missing else planned.panel_overrides.get(lab.key, patient.labs[lab.key]),
            unit=lab.unit,
        )
        for lab in LABS
    ]
    tags = list(planned.tags)
    if case == "borderline":
        tags.append(Annotation(type="borderline", detail={"true_probability": patient.true_probability}))
    return Record(
        seed=cfg.seed,
        schema_version=SCHEMA_VERSION_LLM if planned.plan.version == "2" else SCHEMA_VERSION,
        plan_version=planned.plan.version,
        patient_id=pid,
        split=split,  # type: ignore[arg-type]
        style=planned.plan.style,
        input=ModelInput(patient_id=pid, panel=panel, note=note),
        ground_truth=GroundTruth(
            labs=patient.labs,
            flags=patient.flags,
            true_probability=patient.true_probability,
            label=patient.label,  # type: ignore[arg-type]
        ),
        plan=planned.plan,
        pair_group=pair_group,
        tags=tags,
        noise=planned.noise,
    )


def build_record(cfg: GenConfig, patient: Patient, split: str, case: str | None) -> Record:
    planned = plan_for(cfg, patient, case)
    return assemble_record(cfg, patient, split, case, planned, render(planned.plan))


def build_dataset(cfg: GenConfig) -> dict[str, list[Record]]:
    """Template-rendered dataset (offline). LLM-written notes go through the LLM note writer."""
    if cfg.note_source != "template":
        raise ValueError("build_dataset renders templates; use the LLM note writer for note_source 'llm'")
    cfg.check_styles_available()
    out: dict[str, list[Record]] = {"train": [], "test": [], "adversarial": []}
    for p in generate_cohort(cfg):
        out[p.split].append(build_record(cfg, p, p.split, None))
    for patient, case in generate_adversarial(cfg):
        out["adversarial"].append(build_record(cfg, patient, "adversarial", case))
    return out
