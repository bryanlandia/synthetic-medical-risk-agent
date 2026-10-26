"""The dev split: 500 train patients chosen by a seeded, label-stratified draw. Computed, never stored.

Prompts and systems are iterated on dev only. Training code must exclude the dev ids (``train_ids``).
"""

from __future__ import annotations

import numpy as np

from .records import Dataset

DEV_SIZE = 500
DEV_SEED_STREAM = 7919  # its own stream, so the draw is independent of every data_gen concern


def dev_ids(dataset: Dataset, n: int = DEV_SIZE) -> list[str]:
    """Patient ids of the dev split, sorted. The same dataset and seed always give the same ids."""
    train = sorted(dataset.by_split["train"], key=lambda r: r.patient_id)
    positives = [r.patient_id for r in train if r.ground_truth.label == 1]
    negatives = [r.patient_id for r in train if r.ground_truth.label == 0]
    if n > len(train):
        raise ValueError(f"dev size {n} exceeds the train split ({len(train)})")
    n_pos = round(n * len(positives) / len(train))
    rng = np.random.default_rng(np.random.SeedSequence([dataset.seed, DEV_SEED_STREAM]))
    pos = rng.choice(len(positives), size=n_pos, replace=False)
    neg = rng.choice(len(negatives), size=n - n_pos, replace=False)
    return sorted([positives[int(i)] for i in pos] + [negatives[int(i)] for i in neg])


def train_ids(dataset: Dataset, n: int = DEV_SIZE) -> list[str]:
    """Every train patient id except the dev ids: what training may use."""
    dev = set(dev_ids(dataset, n))
    return sorted(r.patient_id for r in dataset.by_split["train"] if r.patient_id not in dev)
