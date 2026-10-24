"""Seed handling: one independent random stream per concern and per patient.

Every draw is keyed by (seed, concern, *index), so changing one concern (e.g. note
templates) never shifts another (features, labels), and patient i does not depend on
how many patients are generated. Append new concerns at the end; never reorder.
"""

from __future__ import annotations

import numpy as np

CONCERNS: tuple[str, ...] = (
    "features",
    "labels",
    "noise",
    "split",
    "adversarial",
    "notes",
    "calibration",
    "injection",
)


def rng_for(seed: int, concern: str, *index: int) -> np.random.Generator:
    if seed < 0 or any(i < 0 for i in index):
        raise ValueError("seed and indexes must be non-negative")
    key = [seed, CONCERNS.index(concern) + 1, *index]
    return np.random.default_rng(np.random.SeedSequence(key))


def cohort_patient_id(seed: int, index: int) -> str:
    return f"P{seed}-{index:06d}"


def adversarial_patient_id(seed: int, index: int) -> str:
    # Opaque on purpose: the id must not reveal the case type.
    return f"P{seed}-A{index:05d}"
