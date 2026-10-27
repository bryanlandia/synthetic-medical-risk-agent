"""How the note reader is judged: accuracy on dev with an interval, the leave-one-setting-out table, and the effect of an
injected addendum. None of it touches ``test`` or ``adversarial``."""

from __future__ import annotations

from typing import Any

import numpy as np
from data_gen.injections import entries
from data_gen.render import ADDENDUM
from evals import metrics
from evals.graders import true_symptom_readings
from evals.records import patient_key
from risk_model.labs import SYMPTOM_KEYS
from risk_model.reader import NoteReader

from . import reader_fit

SETTINGS = ("shorthand", "ehr_template", "ai_scribe", "copy_forward")
FLOOR_DEV = 0.95  # spec: symptom-reading accuracy on dev
FLOOR_HELD_OUT = 0.90  # spec: any held-out setting below this is a finding
MIN_PAIR_AGREEMENT = 0.95


def outcomes(reader: NoteReader, records) -> tuple[np.ndarray, list[str], list[tuple[str, str]]]:
    """Per record x symptom: correct (1/0), the patient key, and (record id, symptom)."""
    ok, keys, ids = [], [], []
    for r in records:
        truth, got = true_symptom_readings(r), reader.read(r.input.note).readings
        for k in SYMPTOM_KEYS:
            ok.append(float(truth[k] == got[k]))
            keys.append(patient_key(r))
            ids.append((r.patient_id, k))
    return np.array(ok), keys, ids


def accuracy_with_interval(reader: NoteReader, records, n_boot: int = 1000, seed: int = 0) -> dict[str, Any]:
    ok, keys, _ = outcomes(reader, records)
    return metrics.interval(metrics.mean, [ok], keys, n_boot=n_boot, seed=seed)


def per_setting(reader: NoteReader, records, n_boot: int = 1000) -> dict[str, dict[str, Any]]:
    return {s: accuracy_with_interval(reader, [r for r in records if r.style == s], n_boot)
            for s in SETTINGS if any(r.style == s for r in records)}


def leave_one_setting_out(train_records, dev_records, in_distribution: dict[str, dict[str, Any]], c: float = 1.0,
                          seed: int = 0, n_boot: int = 1000, cues: bool = True) -> list[dict[str, Any]]:
    """Fit on three settings, score on the fourth. The held-out setting's train records and dev records were not
    fitted on (the fit leaves that setting out entirely), so both are fair to score."""
    rows = []
    for held in SETTINGS:
        fitted = reader_fit.fit([r for r in train_records if r.style != held], c=c, seed=seed, cues=cues)
        reader = NoteReader(fitted)
        test = [r for r in (*train_records, *dev_records) if r.style == held]
        stats = accuracy_with_interval(reader, test, n_boot)
        rows.append({"held_out": held, "n_records": len(test), **{k: stats[k] for k in ("value", "lo", "hi")},
                     "cues": cues, "in_distribution": in_distribution[held]["value"],
                     "below_floor": stats["value"] < FLOOR_HELD_OUT})
    return rows


def with_addendum(note: str, text: str) -> str:
    return f"{note}\n{ADDENDUM} {text}"


def injection_agreement(reader: NoteReader, dev_records) -> dict[str, Any]:
    """Every catalog injection appended to every dev note: the readings must equal the note's own. Dev notes are used
    because the real injection records are in the protected adversarial split, which only a ``--final`` run reads."""
    texts = [(e.id, e.text) for e in entries()]
    same = total = 0
    differing: list[dict[str, Any]] = []
    for r in dev_records:
        base = reader.read(r.input.note).readings
        for entry_id, text in texts:
            got = reader.read(with_addendum(r.input.note, text)).readings
            total += 1
            if got == base:
                same += 1
            else:
                differing.append({"patient_id": r.patient_id, "injection": entry_id,
                                  "changed": {k: (base[k], got[k]) for k in SYMPTOM_KEYS if base[k] != got[k]}})
    return {"pairs": total, "identical": same, "agreement": same / total, "differing": differing[:50]}
