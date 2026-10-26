"""Which records belong to which suite, for each split a run can target."""

from __future__ import annotations

from typing import Any

from .devsplit import dev_ids
from .graders import CLEAR_HIGH, CLEAR_LOW, true_warning_types
from .graders import BORDERLINE_BAND
from .injection import injection_tag
from .ledger import PROTECTED
from .records import Dataset, categories

SUITE_NAMES = ("happy_path", "data_quality", "borderline", "consistency", "adversarial")
RUN_SPLITS = ("dev", "test", "adversarial")


def split_records(dataset: Dataset, split: str) -> list[Any]:
    if split == "dev":
        dev = set(dev_ids(dataset))
        return [r for r in dataset.by_split["train"] if r.patient_id in dev]
    if split in PROTECTED:
        return list(dataset.by_split[split])
    raise ValueError(f"unknown split {split!r}; choose one of {RUN_SPLITS}")


def _in_band(record: Any) -> bool:
    p = record.ground_truth.true_probability
    return BORDERLINE_BAND[0] <= p <= BORDERLINE_BAND[1] or p < CLEAR_LOW or p > CLEAR_HIGH


def suite_records(dataset: Dataset, split: str) -> dict[str, list[Any]]:
    """The records of each suite on a split. A record can be in several suites."""
    records = split_records(dataset, split)
    out: dict[str, list[Any]] = {name: [] for name in SUITE_NAMES}
    for r in records:
        cats = categories(r)
        if split in ("dev", "test"):
            out["happy_path"].append(r)
        if true_warning_types(r):
            out["data_quality"].append(r)
        if _in_band(r):
            out["borderline"].append(r)
        if r.pair_group:
            out["consistency"].append(r)
        if injection_tag(r):
            out["adversarial"].append(r)
    return {k: v for k, v in out.items() if v}
