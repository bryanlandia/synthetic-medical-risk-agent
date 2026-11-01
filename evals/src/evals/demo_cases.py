"""The 30 demo cases for the web page's supervisor queue: dev-split records chosen by a seeded rule, each with its chart, the exact
message the check sends, the answers a (simulated) preparing clinician entered, and a fictional insurer, preparer, code and time.

Chosen from the dev split only (never a protected split). The statuses used to balance the set come from the independent packet
reference, and the file carries no ground-truth field. The committed file is checked against what this module writes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
from data_gen import SYNTHETIC_NOTICE
from data_gen.labs import LAB_BY_KEY, LabDef
from data_gen.schema import Record

from .graders import true_symptom_readings
from .messages import render_message
from .packet_eval import ATTESTED, reference, stage_records
from .records import REPO_ROOT, Dataset, input_view

DEFAULT_OUT = REPO_ROOT / "web" / "content" / "cases.json"
CASE_STREAM = 9137  # its own seed stream, independent of the generator, the dev draw and the eval fixtures
N_CASES = 30
C1_QUOTA = {"met": 9, "unknown": 6, "unmet": 15}
INSURERS = ("Harborlight Health Plan", "Juniper Ridge Assurance", "Calderon Valley Health", "Quillon Oak Benefits",
            "Bluefinch Care Alliance", "Marrowdale Health Partners", "Silverleaf Mutual", "Pinecrest Care Network",
            "Larkspur Assurance", "Northgate Family Health")
PREPARERS = ("R. Okafor", "M. Lindqvist", "A. Marchetti", "S. Takahashi", "J. Abernathy", "L. Ibarra", "P. Novak", "H. Brennan")
DAY_START, DAY_END = 7 * 60 + 30, 16 * 60 + 45  # received times, in minutes from midnight
# the answer mix across the 30 cases (the three fully releasable cases are always fully answered yes)
N_YES, N_NO, N_UNANSWERED, N_MIXED = 17, 5, 5, 3


def _noise(r: Record) -> set[str]:
    return {n.type for n in r.noise}


def _info(r: Record) -> dict[str, Any]:
    ref = reference(r, {})
    return {"c1": ref["C1"], "c2": ref["C2"], "noise": _noise(r), "borderline": 0.4 <= r.ground_truth.true_probability <= 0.6,
            "missing_lab": any(e.value is None for e in r.input.panel), "tremor": true_symptom_readings(r)["tremor"]}


# (name, predicate over a record's info, minimum count); filled in this order, before the C1 quotas are topped up
REQUIREMENTS: tuple[tuple[str, Callable[[dict[str, Any]], bool], int], ...] = (
    ("fully releasable", lambda i: i["c1"] == "met" and i["c2"] == "met", 3),
    ("tremor present", lambda i: i["tremor"] == "present", 2),
    ("tremor hedged", lambda i: i["tremor"] == "possible", 2),
    ("tremor absent", lambda i: i["tremor"] == "absent", 2),
    ("tremor not mentioned", lambda i: i["tremor"] == "not_mentioned", 2),
    ("unit mismatch", lambda i: "unit_mismatch" in i["noise"], 3),
    ("contradiction", lambda i: "contradiction" in i["noise"], 2),
    ("borderline", lambda i: i["borderline"], 3),
    ("lab not reported", lambda i: i["missing_lab"], 3),
)


def flag(lab: LabDef, value: float | None, unit: str) -> str | None:
    """H or L against the reference range, judged on the value converted to the lab's usual unit; None if within it or not reported."""
    if value is None:
        return None
    usual = lab.from_alt(value) if lab.alt_unit and unit == lab.alt_unit else value
    return "H" if usual > lab.ref_hi else ("L" if usual < lab.ref_lo else None)


def chart(record: Record) -> dict[str, Any]:
    view = input_view(record)
    labs = []
    for entry in view["panel"]:
        lab = LAB_BY_KEY[entry["lab"]]
        labs.append({"lab": lab.key, "name": lab.name, "abbr": lab.abbr, "value": entry["value"], "unit": entry["unit"],
                     "ref_lo": lab.ref_lo, "ref_hi": lab.ref_hi, "ref_unit": lab.unit, "flag": flag(lab, entry["value"], entry["unit"])})
    return {"labs": labs, "note": view["note"]}


def select(dataset: Dataset, rng: np.random.Generator) -> list[Record]:
    """30 dev records meeting the requirements and the C1 quotas, in a seeded order."""
    records = sorted(stage_records(dataset, "dev"), key=lambda r: r.patient_id)
    order = [records[int(i)] for i in rng.permutation(len(records))]
    infos = {r.patient_id: _info(r) for r in order}
    chosen: list[Record] = []
    used = {"met": 0, "unknown": 0, "unmet": 0}

    def take(pred: Callable[[dict[str, Any]], bool], count: int, name: str) -> None:
        have = sum(1 for r in chosen if pred(infos[r.patient_id]))
        for r in order:
            if have >= count:
                return
            info = infos[r.patient_id]
            if r in chosen or not pred(info) or used[info["c1"]] >= C1_QUOTA[info["c1"]]:
                continue
            chosen.append(r)
            used[info["c1"]] += 1
            have += 1
        if have < count:
            raise ValueError(f"the dev split cannot supply {count} cases for '{name}'")

    for name, pred, minimum in REQUIREMENTS:
        take(pred, minimum, name)
    for status, quota in C1_QUOTA.items():
        take(lambda i, s=status: i["c1"] == s, quota, f"C1 {status}")
    if len(chosen) != N_CASES:
        raise ValueError(f"expected {N_CASES} cases, selected {len(chosen)}")
    return [chosen[int(i)] for i in rng.permutation(len(chosen))]


def preparer_answers(chosen: list[Record], rng: np.random.Generator) -> list[dict[str, str]]:
    """What the simulated preparing clinician entered for C3 to C6: mostly yes, some unanswered, some no."""
    infos = [_info(r) for r in chosen]
    releasable = [k for k, i in enumerate(infos) if i["c1"] == "met" and i["c2"] == "met"]
    rest = [k for k in range(len(chosen)) if k not in releasable]
    kinds = ["yes"] * (N_YES - len(releasable)) + ["no"] * N_NO + ["unanswered"] * N_UNANSWERED + ["mixed"] * N_MIXED
    assert len(kinds) == len(rest)
    answers: dict[int, dict[str, str]] = {k: dict.fromkeys(ATTESTED, "yes") for k in releasable}
    for k, kind in zip((rest[int(i)] for i in rng.permutation(len(rest))), kinds):
        a = dict.fromkeys(ATTESTED, "yes")
        if kind in ("no", "mixed"):
            a[ATTESTED[int(rng.integers(0, len(ATTESTED)))]] = "no"
        if kind in ("unanswered", "mixed"):
            for c in rng.permutation(ATTESTED)[: (1 if kind == "mixed" else int(rng.integers(1, 3)))]:
                if a[str(c)] == "yes":
                    a[str(c)] = "unanswered"
        answers[k] = a
    return [answers[k] for k in range(len(chosen))]


def build(dataset: Dataset) -> dict[str, Any]:
    rng = np.random.default_rng(np.random.SeedSequence([dataset.seed, CASE_STREAM]))
    chosen = select(dataset, rng)
    answers = preparer_answers(chosen, rng)
    minutes = sorted(int(m) for m in rng.choice(np.arange(DAY_START, DAY_END), size=N_CASES, replace=False))
    codes: set[int] = set()
    cases = []
    for n, (record, given, minute) in enumerate(zip(chosen, answers, minutes), start=1):
        code = int(rng.integers(10000, 99999))
        while code in codes:
            code = int(rng.integers(10000, 99999))
        codes.add(code)
        cases.append({
            "id": f"case-{n:02d}", "ordinal": f"{n:02d}", "request_code": f"VK-PET-{code}", "patient_id": record.patient_id,
            "insurer": INSURERS[int(rng.integers(0, len(INSURERS)))], "preparer": PREPARERS[int(rng.integers(0, len(PREPARERS)))],
            "received": f"{minute // 60:02d}:{minute % 60:02d}", "chart": chart(record), "message": render_message(input_view(record)),
            "answers": given})
    digest = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()[:12]
    return {"notice": SYNTHETIC_NOTICE, "dataset_config_hash": dataset.config_hash, "cases_hash": digest, "cases": cases}


def text(dataset: Dataset) -> str:
    return json.dumps(build(dataset), indent=2, ensure_ascii=False) + "\n"


def write(dataset: Dataset, path: Path = DEFAULT_OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(dataset))
    return path
