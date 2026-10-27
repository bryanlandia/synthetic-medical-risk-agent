"""Data-quality warnings from the panel and from the lab values the note states. One warning per problem found."""

from __future__ import annotations

from typing import Any

from . import features, labvalues
from .labs import LAB_BY_KEY, LAB_KEYS
from .reader import Reading

ORDER = ("missing_value", "impossible_value", "unit_mismatch", "contradiction", "note_flag_disagreement")


def check(view: dict[str, Any], reading: Reading, note: str | None = None) -> list[dict[str, str | None]]:
    """Warnings as ``{"type", "lab"}`` dictionaries (lab is None for a symptom conflict), in a fixed order."""
    features.check_view(view)
    found: set[tuple[str, str | None]] = set()
    panel: dict[str, float | None] = {}  # usual-unit value, None if missing or impossible
    for entry in view["panel"]:
        lab = LAB_BY_KEY.get(entry["lab"])
        if lab is None:
            continue
        if entry["value"] is None:
            found.add(("missing_value", lab.key))
            panel[lab.key] = None
            continue
        if entry["unit"] == lab.alt_unit:
            found.add(("unit_mismatch", lab.key))
        value = lab.to_usual(float(entry["value"]), entry["unit"])
        if features.impossible(lab, value):
            found.add(("impossible_value", lab.key))
            panel[lab.key] = None
        else:
            panel[lab.key] = value
    for stated in labvalues.read(view["note"] if note is None else note):
        lab = LAB_BY_KEY[stated.lab]
        if lab.alt_unit and stated.unit == lab.alt_unit:
            found.add(("unit_mismatch", lab.key))
        reference = panel.get(lab.key)
        if reference is not None and not labvalues.agrees(lab, stated, reference):
            found.add(("contradiction", lab.key))
    if reading.conflicts:
        found.add(("note_flag_disagreement", None))
    rank = {t: i for i, t in enumerate(ORDER)}
    lab_rank = {k: i for i, k in enumerate(LAB_KEYS)}
    ordered = sorted(found, key=lambda w: (rank[w[0]], lab_rank.get(w[1], -1) if w[1] else -1))
    return [{"type": t, "lab": lab} for t, lab in ordered]
