"""What-if estimate: the classifier's probability for inputs set by hand, what moved it, and the message those inputs make.

The inputs are the eight labs (a value in the usual unit, or None for "not done") and the five symptoms (absent, possible or
present). Nothing is read from text and no model is called. Each lab value is rounded to the resolution the message writes it
with, so the number scored is the number a reader of the message sees.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import features, sensitivity
from .classifier import RiskClassifier
from .labs import LAB_BY_KEY, LAB_KEYS, LABS, SYMPTOM_KEYS

STATES = ("absent", "possible", "present")
DECIMALS: dict[str, int] = {"velorin_index": 0, "serum_k17": 1, "tarnic_acid": 0, "brell_enzyme": 0,
                            "halvin_titer": 1, "osmet_level": 0, "plexa_count": 0, "dorrin_ratio": 2}
BANDS = ("low", "uncertain", "high")  # below, inside and above the routing band
_SYMPTOM_WORDS = {"tremor": "tremor", "fatigue": "fatigue", "photophobia": "photophobia",
                  "joint_stiffness": "joint stiffness", "dizziness": "dizziness"}
# The reader looks at the clause before a mention, so each sentence opens with the same clause: a neighbour's "denies" cannot
# change how the next symptom is read.
_SENTENCE = {"present": "On review, reports {}.", "possible": "On review, possible {}.", "absent": "On review, denies {}."}


class EstimateError(ValueError):
    """The inputs are not the eight labs and five symptoms, within limits."""


def step(lab_key: str) -> float:
    """The slider increment for a lab: one unit of the last decimal the message writes."""
    return 10.0 ** -DECIMALS[lab_key]


def check(labs: Any, symptoms: Any) -> tuple[dict[str, float | None], dict[str, str]]:
    """The inputs with each lab value rounded to its resolution; raises ``EstimateError`` on anything else."""
    if not isinstance(labs, dict) or set(labs) != set(LAB_KEYS):
        raise EstimateError("labs must name exactly the eight labs")
    if not isinstance(symptoms, dict) or set(symptoms) != set(SYMPTOM_KEYS):
        raise EstimateError("symptoms must name exactly the five symptoms")
    values: dict[str, float | None] = {}
    for key in LAB_KEYS:
        v = labs[key]
        if v is None:
            values[key] = None
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v):
            raise EstimateError(f"{key} must be a number or null")
        lab = LAB_BY_KEY[key]
        rounded = round(float(v), DECIMALS[key])
        if not lab.plaus_lo <= rounded <= lab.plaus_hi:
            raise EstimateError(f"{key} is outside its plausible range")
        values[key] = rounded
    for key in SYMPTOM_KEYS:
        if symptoms[key] not in STATES:
            raise EstimateError(f"{key} must be one of {', '.join(STATES)}")
    return values, dict(symptoms)


def message(labs: dict[str, float | None], symptoms: dict[str, str]) -> str:
    """The fixed message for checked inputs: a Labs list of the labs done, then a Note with one sentence per symptom."""
    lines = ["Labs:"]
    done = [lab for lab in LABS if labs[lab.key] is not None]
    for lab in done:
        lines.append(f"- {lab.name} ({lab.abbr}): {labs[lab.key]:.{DECIMALS[lab.key]}f} {lab.unit}")
    if not done:
        lines[0] = "Labs: none reported."
    lines += ["", "Note:", *(_SENTENCE[symptoms[k]].format(_SYMPTOM_WORDS[k]) for k in SYMPTOM_KEYS)]
    return "\n".join(lines)


def _view(labs: dict[str, float | None], note: str) -> dict[str, Any]:
    return {"patient_id": "estimate", "panel": [{"lab": lab.key, "value": labs[lab.key], "unit": lab.unit} for lab in LABS], "note": note}


def _breakdown(clf: RiskClassifier, x: np.ndarray) -> tuple[list[dict[str, Any]], float]:
    """One signed share of the score per input, and the starting point; the shares and the start add up to the score."""
    parts = clf.contributions(x)
    names = features.FEATURE_NAMES
    scale, shift = (1.0, 0.0) if clf.platt is None else clf.platt
    rows: list[dict[str, Any]] = []
    for key in LAB_KEYS:
        share = parts[names.index(f"z:{key}")] + parts[names.index(f"missing:{key}")]
        rows.append({"kind": "lab", "key": key, "contribution": float(share)})
    for key in SYMPTOM_KEYS:
        share = parts[names.index(f"{key}:present")] + parts[names.index(f"{key}:possible")]
        rows.append({"kind": "symptom", "key": key, "contribution": float(share)})
    return rows, float(scale * clf.intercept + shift)


def estimate(clf: RiskClassifier, labs: Any, symptoms: Any) -> dict[str, Any]:
    """The probability, its routing band, the breakdown with its starting point, and the message for the inputs."""
    values, states = check(labs, symptoms)
    text = message(values, states)
    view = _view(values, text)
    x = clf.vector(view, states)
    score = clf.logit(x)
    p = float(1.0 / (1.0 + np.exp(-score)))
    rows, start = _breakdown(clf, x)
    return {"probability": p, "band": BANDS[sensitivity.routing(p)], "score": float(score), "start": start,
            "breakdown": rows, "message": text}
