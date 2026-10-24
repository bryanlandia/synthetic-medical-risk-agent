"""Adversarial split: deliberately hard cases, each tagged with its case type."""

from __future__ import annotations

from .cohort import Patient, sample_features, sample_label
from .config import GenConfig
from .plan import CASE_TYPES
from .rule import calibrated_intercept, true_probability
from .seeds import adversarial_patient_id, rng_for

ADV_BASE = 10_000_000  # index space disjoint from cohort patients
ADV_STRIDE = 100_000


def adv_index(type_idx: int, k: int) -> int:
    return ADV_BASE + type_idx * ADV_STRIDE + k


def adversarial_patient(seed: int, type_idx: int, k: int, intercept: float) -> tuple[Patient, str]:
    case = CASE_TYPES[type_idx]
    index = adv_index(type_idx, k)
    for attempt in range(100_000):
        rng = rng_for(seed, "adversarial", type_idx + 1, k, attempt)
        labs, flags = sample_features(rng)
        p = true_probability(labs, flags, intercept)
        if case != "borderline" or 0.4 <= p <= 0.6:
            break
    else:  # pragma: no cover
        raise RuntimeError("could not sample a borderline patient")
    patient = Patient(
        index=index, patient_id="", labs=labs, flags=flags,
        true_probability=p, label=sample_label(seed, index, p), split="adversarial",
    )
    return patient, case


def generate_adversarial(cfg: GenConfig) -> list[tuple[Patient, str]]:
    intercept = calibrated_intercept(cfg.target_prevalence)
    items = [
        adversarial_patient(cfg.seed, t, k, intercept)
        for t in range(len(CASE_TYPES))
        for k in range(cfg.n_per_adversarial_type)
    ]
    order = rng_for(cfg.seed, "adversarial", 0, 0, 0).permutation(len(items))
    out = []
    for new_pos, old_pos in enumerate(order):
        patient, case = items[old_pos]
        out.append((Patient(**{**patient.__dict__, "patient_id": adversarial_patient_id(cfg.seed, new_pos)}), case))
    return out
