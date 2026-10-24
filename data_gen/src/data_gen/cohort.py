"""Cohort generation: patients, true probabilities, labels and the train / random-test split."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import GenConfig
from .labs import LABS, SYMPTOMS
from .rule import calibrated_intercept, round_sig, true_probability, trunc_normal
from .seeds import cohort_patient_id, rng_for


@dataclass(frozen=True)
class Patient:
    index: int
    patient_id: str
    labs: dict[str, float]
    flags: dict[str, bool]
    true_probability: float
    label: int
    split: str = ""


def sample_features(rng: np.random.Generator) -> tuple[dict[str, float], dict[str, bool]]:
    labs = {
        lab.key: round_sig(trunc_normal(rng, lab.mean, lab.sd, lab.plaus_lo, lab.plaus_hi))
        for lab in LABS
    }
    flags = {s.key: bool(rng.random() < s.base_rate) for s in SYMPTOMS}
    return labs, flags


def sample_label(seed: int, index: int, p: float) -> int:
    return int(rng_for(seed, "labels", index).random() < p)


def build_patient(seed: int, index: int, intercept: float) -> Patient:
    labs, flags = sample_features(rng_for(seed, "features", index))
    p = true_probability(labs, flags, intercept)
    return Patient(
        index=index,
        patient_id=cohort_patient_id(seed, index),
        labs=labs,
        flags=flags,
        true_probability=p,
        label=sample_label(seed, index, p),
    )


def assign_splits(patients: list[Patient], seed: int, n_train: int) -> list[Patient]:
    """Stratified by label so train and random test share prevalence; deterministic."""
    n = len(patients)
    frac = n_train / n
    split_of: dict[int, str] = {}
    for cls in (0, 1):
        idx = [p.index for p in patients if p.label == cls]
        order = rng_for(seed, "split", cls).permutation(len(idx))
        n_cls_train = round(frac * len(idx))
        for rank, pos in enumerate(order):
            split_of[idx[pos]] = "train" if rank < n_cls_train else "test"
    return [
        Patient(**{**p.__dict__, "split": split_of[p.index]}) for p in patients
    ]


def generate_cohort(cfg: GenConfig) -> list[Patient]:
    intercept = calibrated_intercept(cfg.target_prevalence)
    n = cfg.n_train + cfg.n_test
    patients = [build_patient(cfg.seed, i, intercept) for i in range(n)]
    return assign_splits(patients, cfg.seed, cfg.n_train)
