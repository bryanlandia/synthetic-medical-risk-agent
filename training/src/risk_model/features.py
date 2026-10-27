"""Features from the input view: lab z-scores, missing indicators and the symptom readings. Nothing else is read."""

from __future__ import annotations

from typing import Any

import numpy as np

from .labs import LAB_BY_KEY, LAB_KEYS, SYMPTOM_KEYS, Lab

VIEW_KEYS = {"patient_id", "panel", "note"}
PANEL_KEYS = {"lab", "value", "unit"}

# present and possible are indicator columns; absent and not mentioned are the reference level
SYMPTOM_COLUMNS = tuple(f"{s}:{level}" for s in SYMPTOM_KEYS for level in ("present", "possible"))
FEATURE_NAMES: tuple[str, ...] = (
    *(f"z:{k}" for k in LAB_KEYS), *(f"missing:{k}" for k in LAB_KEYS), *SYMPTOM_COLUMNS)


def check_view(view: dict[str, Any]) -> None:
    """Raise if the view carries anything a system may not see (ground truth, plan, split)."""
    extra = sorted(set(view) - VIEW_KEYS)
    if extra:
        raise ValueError(f"input view has fields a system must not see: {extra}")
    for entry in view["panel"]:
        odd = sorted(set(entry) ^ PANEL_KEYS)
        if odd:
            raise ValueError(f"panel entry has unexpected fields: {odd}")


def impossible(lab: Lab, value: float) -> bool:
    """A value no patient could have: outside the lab's plausible range (negative, or shifted by a power of ten)."""
    return not (lab.plaus_lo <= value <= lab.plaus_hi)


def panel_values(view: dict[str, Any]) -> dict[str, float | None]:
    """Usual-unit value per lab; None where the panel has none or the value is impossible."""
    check_view(view)
    out: dict[str, float | None] = {k: None for k in LAB_KEYS}
    for entry in view["panel"]:
        lab = LAB_BY_KEY.get(entry["lab"])
        if lab is None or entry["value"] is None:
            continue
        value = lab.to_usual(float(entry["value"]), entry["unit"])
        out[lab.key] = None if impossible(lab, value) else value
    return out


def build(view: dict[str, Any], symptoms: dict[str, str], means: np.ndarray, sds: np.ndarray) -> np.ndarray:
    """The feature vector in ``FEATURE_NAMES`` order. A missing or impossible lab sits at the mean with its indicator on."""
    values = panel_values(view)
    raw = np.array([np.nan if values[k] is None else values[k] for k in LAB_KEYS], dtype=float)
    missing = np.isnan(raw)
    z = np.where(missing, 0.0, (raw - means) / sds)
    cols = [1.0 if symptoms.get(s) == level else 0.0 for s in SYMPTOM_KEYS for level in ("present", "possible")]
    return np.concatenate([z, missing.astype(float), np.array(cols)])
