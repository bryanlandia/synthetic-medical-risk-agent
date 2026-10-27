"""Training records: the train split of the dataset without the dev ids. Anything else is refused by id."""

from __future__ import annotations

from pathlib import Path

from data_gen.schema import Record
from evals.devsplit import dev_ids, train_ids
from evals.records import DEFAULT_DATASET, Dataset, load_dataset


class ProtectedRecordError(ValueError):
    """A record that must not be used for training or for choosing a model was given."""


def load(directory: Path | str = DEFAULT_DATASET) -> Dataset:
    return load_dataset(directory)


def training_records(dataset: Dataset) -> list[Record]:
    """Train-split records that are not dev ids, sorted by patient id."""
    usable = set(train_ids(dataset))
    return sorted((r for r in dataset.by_split["train"] if r.patient_id in usable), key=lambda r: r.patient_id)


def dev_records(dataset: Dataset) -> list[Record]:
    wanted = set(dev_ids(dataset))
    return sorted((r for r in dataset.by_split["train"] if r.patient_id in wanted), key=lambda r: r.patient_id)


def assert_trainable(dataset: Dataset, records: list[Record]) -> None:
    """Raise, naming the first offender, if any record is from test or adversarial or is a dev id."""
    dev = set(dev_ids(dataset))
    for r in records:
        if r.split != "train":
            raise ProtectedRecordError(f"{r.patient_id} is a {r.split} record: training uses the train split only")
        if r.patient_id in dev:
            raise ProtectedRecordError(f"{r.patient_id} is a dev record: dev is for choosing a model, not fitting it")
