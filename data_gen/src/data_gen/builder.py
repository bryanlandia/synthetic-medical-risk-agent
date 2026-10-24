"""Assemble complete records (input view + ground truth + labeled noise) for all splits."""

from __future__ import annotations

from .adversarial import generate_adversarial
from .cohort import Patient, generate_cohort
from .config import GenConfig
from .labs import LABS
from .plan import PlannedNote, plan_note
from .render import render
from .schema import Annotation, GroundTruth, LabEntry, ModelInput, Record
from .seeds import rng_for


def build_record(cfg: GenConfig, patient: Patient, split: str, case: str | None) -> Record:
    planned: PlannedNote = plan_note(
        cfg, patient.labs, patient.flags, rng_for(cfg.seed, "noise", patient.index), case
    )
    note = render(planned.plan)
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
        patient_id=patient.patient_id,
        split=split,  # type: ignore[arg-type]
        style=planned.plan.style,
        input=ModelInput(patient_id=patient.patient_id, panel=panel, note=note),
        ground_truth=GroundTruth(
            labs=patient.labs,
            flags=patient.flags,
            true_probability=patient.true_probability,
            label=patient.label,  # type: ignore[arg-type]
        ),
        plan=planned.plan,
        tags=tags,
        noise=planned.noise,
    )


def build_dataset(cfg: GenConfig) -> dict[str, list[Record]]:
    cfg.check_styles_available()
    out: dict[str, list[Record]] = {"train": [], "test": [], "adversarial": []}
    for p in generate_cohort(cfg):
        out[p.split].append(build_record(cfg, p, p.split, None))
    for patient, case in generate_adversarial(cfg):
        out["adversarial"].append(build_record(cfg, patient, "adversarial", case))
    return out
