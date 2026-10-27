"""The demo patients for the web page: a few dev-split records, each with its chart and the exact message the check sends.

Chosen by fixed rules from the dev split (never a protected split), rendered with the harness's own ``render_message`` so the
page never reimplements what a message is, and written without any ground-truth field. The file is committed; a test keeps it
equal to what this module writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from data_gen import SYNTHETIC_NOTICE
from data_gen.labs import LAB_BY_KEY
from data_gen.schema import Record

from .devsplit import dev_ids
from .messages import render_message
from .records import REPO_ROOT, Dataset, input_view

DEFAULT_OUT = REPO_ROOT / "web" / "content" / "demo_patients.json"


def _noise(r: Record) -> set[str]:
    return {n.type for n in r.noise}


def _borderline(r: Record) -> bool:
    return 0.4 <= r.ground_truth.true_probability <= 0.6


# (slug, title, what to look for, rule over a record); the first dev record, in id order, that satisfies each rule
RULES: tuple[tuple[str, str, str, Callable[[Record], bool]], ...] = (
    ("routine", "Routine follow-up", "All eight labs are on the chart and the note states symptoms.",
     lambda r: not r.noise and not r.tags and not _borderline(r)),
    ("unit-and-missing", "Mixed units, a missing lab", "One lab is in a different unit and one is missing: look at the data-quality warnings.",
     lambda r: {"unit_mismatch", "missing_value"} <= _noise(r)),
    ("borderline", "Close to the line", "The probability falls near the middle: look at whether the result is called uncertain.",
     lambda r: _borderline(r) and not r.noise and not r.tags),
    ("contradiction", "Note and panel disagree", "A value in the note does not match the panel: look at the data-quality warnings.",
     lambda r: "contradiction" in _noise(r)),
)


def chart(record: Record) -> dict[str, Any]:
    view = input_view(record)
    labs = []
    for entry in view["panel"]:
        lab = LAB_BY_KEY[entry["lab"]]
        labs.append({"lab": lab.key, "name": lab.name, "abbr": lab.abbr, "value": entry["value"], "unit": entry["unit"]})
    return {"labs": labs, "note": view["note"]}


def select(dataset: Dataset) -> list[tuple[str, str, str, Record]]:
    dev = dev_ids(dataset)
    records = [dataset.record(i) for i in dev]
    chosen = []
    for slug, title, look, rule in RULES:
        match = next((r for r in records if rule(r)), None)
        if match is None:
            raise ValueError(f"no dev record satisfies the rule for the demo patient '{slug}'")
        chosen.append((slug, title, look, match))
    return chosen


def build(dataset: Dataset) -> dict[str, Any]:
    patients = []
    for slug, title, look, record in select(dataset):
        view = input_view(record)
        patients.append({"slug": slug, "title": title, "look_for": look, "patient_id": record.patient_id, "split": "dev",
                         "chart": chart(record), "message": render_message(view)})
    return {"notice": SYNTHETIC_NOTICE, "dataset_config_hash": dataset.config_hash, "patients": patients}


def text(dataset: Dataset) -> str:
    return json.dumps(build(dataset), indent=2, ensure_ascii=False) + "\n"


def write(dataset: Dataset, path: Path = DEFAULT_OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(dataset))
    return path
