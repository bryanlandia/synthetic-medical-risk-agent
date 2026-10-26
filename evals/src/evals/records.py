"""Loading the dataset, the view a system may see, categories, and the patient key for statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_gen.dataset_io import read_dataset
from data_gen.schema import Record

SPLITS = ("train", "test", "adversarial")
VIEW_KEYS = {"patient_id", "panel", "note"}
PANEL_KEYS = {"lab", "value", "unit"}
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = REPO_ROOT / "data_gen" / "data_llm"

# tag type -> the eval category it belongs to
TAG_CATEGORY = {
    "missing_labs": "data_quality", "unit_mismatch": "data_quality", "impossible_value": "data_quality",
    "contradiction": "data_quality", "note_flag_disagreement": "data_quality",
    "borderline": "borderline", "prompt_injection": "adversarial",
}
NOISE_CATEGORY = {"missing_value": "data_quality", "unit_mismatch": "data_quality", "contradiction": "data_quality"}


@dataclass
class Dataset:
    directory: Path
    by_split: dict[str, list[Record]]
    manifest: dict[str, Any]
    _index: dict[str, Record] = field(default_factory=dict, repr=False)

    @property
    def seed(self) -> int:
        return int(self.manifest["seed"])

    @property
    def config_hash(self) -> str:
        return str(self.manifest["config_hash"])

    def record(self, patient_id: str) -> Record:
        if not self._index:
            self._index = {r.patient_id: r for recs in self.by_split.values() for r in recs}
        return self._index[patient_id]


def load_dataset(directory: Path | str = DEFAULT_DATASET) -> Dataset:
    by_split, manifest = read_dataset(Path(directory))
    return Dataset(Path(directory), by_split, manifest)


def input_view(record: Record) -> dict[str, Any]:
    """What a system under test may see: patient id, lab panel, note. Nothing else."""
    view = record.input_view()
    assert_clean_view(view)
    return view


def assert_clean_view(view: dict[str, Any]) -> None:
    extra = set(view) - VIEW_KEYS
    if extra:
        raise ValueError(f"input view has fields a system must not see: {sorted(extra)}")
    for entry in view["panel"]:
        if set(entry) != PANEL_KEYS:
            raise ValueError(f"panel entry has unexpected fields: {sorted(set(entry) ^ PANEL_KEYS)}")


def patient_key(record: Record) -> str:
    """The patient a record belongs to: matched-pair members share one, so the bootstrap draws them together."""
    return record.pair_group or record.patient_id


def categories(record: Record) -> set[str]:
    """Every eval category a record belongs to (it can belong to several)."""
    cats: set[str] = set()
    if record.split == "test":
        cats.add("happy_path")
    for tag in record.tags:
        cats.add(TAG_CATEGORY[tag.type])
    for noise in record.noise:
        if noise.type in NOISE_CATEGORY:
            cats.add(NOISE_CATEGORY[noise.type])
    if record.pair_group is not None:
        cats.add("consistency")
    if 0.4 <= record.ground_truth.true_probability <= 0.6:
        cats.add("borderline")
    return cats


def tag_types(record: Record) -> set[str]:
    return record.tag_types()


def unique_patients(records: list[Record]) -> list[Record]:
    """One record per patient: the first of each matched-pair group. Happy-path metrics use this basis, like the
    manifest's best-possible scores, so a patient written in four settings is not counted four times."""
    seen: set[str] = set()
    out = []
    for r in records:
        key = patient_key(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out
