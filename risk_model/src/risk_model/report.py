"""The risk report for one record: the model's probability, the note reader's symptoms, deterministic data-quality
warnings and evidence written from fixed templates. No model writes any text."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import features, quality, sensitivity
from .classifier import RiskClassifier
from .labs import LAB_BY_KEY, SYMPTOM_KEYS
from .reader import NoteReader

DISCLAIMER = "This is not medical advice. All data is synthetic and the disease is fictional."
BAND = (0.4, 0.6)
MAX_DRIVERS = 4
MIN_CONTRIBUTION = 0.05
SYMPTOM_LABEL = {"tremor": "Tremor", "fatigue": "Fatigue", "photophobia": "Light sensitivity",
                 "joint_stiffness": "Joint stiffness", "dizziness": "Dizziness"}


def _number(value: float) -> str:
    return f"{value:.4g}"


def _evidence(clf: RiskClassifier, x: np.ndarray, view: dict[str, Any], symptoms: dict[str, str], p: float) -> list[str]:
    values = features.panel_values(view)
    contributions = clf.contributions(x)
    order = np.argsort(-np.abs(contributions), kind="stable")
    drivers: list[str] = []
    for i in order:
        c = float(contributions[i])
        if abs(c) < MIN_CONTRIBUTION or len(drivers) >= MAX_DRIVERS:
            break
        kind, _, key = features.FEATURE_NAMES[i].partition(":")
        direction = "raises" if c > 0 else "lowers"
        if kind == "z":
            lab = LAB_BY_KEY[key]
            where = "above" if x[i] > 0 else "below"
            drivers.append(f"{lab.name} {_number(values[key])}{"" if lab.unit == "ratio" else " " + lab.unit} is {where} the typical value of "
                           f"{_number(lab.mean)}, which {direction} the estimate.")
        elif kind == "missing":
            drivers.append(f"{LAB_BY_KEY[key].name} is not available, so the estimate leans on the other findings.")
        else:
            level = symptoms[kind]
            drivers.append(f"{SYMPTOM_LABEL[kind]} is read as {level} in the note, which {direction} the estimate.")
    summary = f"Estimated probability {p:.2f} from the lab panel and the note's symptom readings."
    return [*drivers, summary]


def _name(gap: dict[str, Any]) -> str:
    return LAB_BY_KEY[gap["key"]].name if gap["kind"] == "lab" else SYMPTOM_LABEL[gap["key"]]


def _confidence(interval: list[float], gaps: list[dict[str, Any]]) -> list[str]:
    """At most two fixed-template statements on why the result is or is not confident."""
    lo, hi = interval
    width = hi - lo
    if not gaps:
        return ["No lab or symptom is missing, so the estimate does not depend on unmeasured findings."]
    top = gaps[0]
    swing = f"the largest swing is from {_name(top)} ({top['low']:.0%} to {top['high']:.0%})"
    if width < 0.05:
        out = [f"The findings not on the record would not change the result much (range {lo:.0%} to {hi:.0%})."]
    elif width > 0.3:
        out = [f"The estimate could fall anywhere from {lo:.0%} to {hi:.0%} depending on {len(gaps)} finding(s) not on the record; {swing}."]
    else:
        out = [f"If the findings not on the record were obtained, the estimate could range from {lo:.0%} to {hi:.0%}; {swing}."]
    decisive = [_name(g) for g in gaps if g["changes_routing"]][:3]
    if decisive:
        out.append("Obtaining " + ", ".join(decisive) + " could move the result to a different band.")
    return out


def build(view: dict[str, Any], reader: NoteReader, clf: RiskClassifier) -> dict[str, Any]:
    """A complete scored report (a plain dictionary that validates against the report contract)."""
    features.check_view(view)
    reading = reader.read(view["note"])
    x = clf.vector(view, reading.readings)
    p = float(1.0 / (1.0 + np.exp(-clf.logit(x))))
    interval, gaps = sensitivity.analyse(clf, view, reading.readings, x)
    evidence = _evidence(clf, x, view, reading.readings, p)
    evidence[-1:] = [*_confidence(interval, gaps), evidence[-1]]  # the summary stays last
    values = features.panel_values(view)
    labs_used = [{"lab": e["lab"], "value": float(e["value"]), "unit": e["unit"]}
                 for e in view["panel"] if e["lab"] in LAB_BY_KEY and values[e["lab"]] is not None]
    return {
        "status": "scored", "probability": p, "uncertain": BAND[0] <= p <= BAND[1],
        "symptoms": {k: reading.readings[k] for k in SYMPTOM_KEYS}, "labs_used": labs_used,
        "data_quality": quality.check(view, reading),
        "evidence": evidence,
        "interval": interval, "gaps": gaps,
        "disclaimer": DISCLAIMER,
    }
