"""How far the estimate could move if the findings the record lacks were obtained.

The model is a logistic regression, so the logit is a sum over features and an unmeasured item changes only its own terms.
Each item's extremes therefore add up, and the bounds are exact (no search, no sampling). Recorded values are never varied.

This is a range over unmeasured findings, not a statistical confidence interval: it says nothing about how well the
model was fitted or calibrated.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import features
from .classifier import RiskClassifier
from .labs import LAB_BY_KEY, LAB_KEYS, SYMPTOM_KEYS

PLAUSIBLE_SD = 2.0  # an unmeasured lab is taken to lie within its usual mean plus or minus this many standard deviations
BAND = (0.4, 0.6)  # the routing bands: below, inside and above (the report's uncertain band)


def routing(p: float) -> int:
    """0 below the band, 1 inside it, 2 above it."""
    return 0 if p < BAND[0] else (1 if p <= BAND[1] else 2)


def _sigmoid(z: float) -> float:
    return float(1.0 / (1.0 + np.exp(-z)))


def _lab_deltas(clf: RiskClassifier, key: str) -> tuple[float, float]:
    """Lowest and highest change in the raw logit if this missing lab were measured, or left unmeasured (change 0)."""
    i = LAB_KEYS.index(key)
    lab = LAB_BY_KEY[key]
    lo = max(lab.mean - PLAUSIBLE_SD * lab.sd, lab.plaus_lo)
    hi = min(lab.mean + PLAUSIBLE_SD * lab.sd, lab.plaus_hi)
    z = [(v - clf.means[i]) / clf.sds[i] for v in (lo, hi)]
    c_z = clf.coef[features.FEATURE_NAMES.index(f"z:{key}")]
    c_missing = clf.coef[features.FEATURE_NAMES.index(f"missing:{key}")]
    ends = [c_z * v - c_missing for v in z]
    return min(0.0, *ends), max(0.0, *ends)


def _symptom_deltas(clf: RiskClassifier, key: str) -> tuple[float, float]:
    """An unmentioned symptom sits at the reference level (absent); it could be possible or present."""
    c = [clf.coef[features.FEATURE_NAMES.index(f"{key}:{level}")] for level in ("present", "possible")]
    return min(0.0, *c), max(0.0, *c)


def unmeasured(view: dict[str, Any], symptoms: dict[str, str]) -> list[tuple[str, str]]:
    """The labs with no usable value and the symptoms the note does not mention, as (kind, key)."""
    values = features.panel_values(view)
    return [("lab", k) for k in LAB_KEYS if values[k] is None] + \
           [("symptom", s) for s in SYMPTOM_KEYS if symptoms.get(s) == "not_mentioned"]


def analyse(clf: RiskClassifier, view: dict[str, Any], symptoms: dict[str, str], x: np.ndarray) -> tuple[list[float], list[dict[str, Any]]]:
    """(interval, gaps): the range of the probability over every unmeasured item, and each item's own range, largest swing first.

    The range includes leaving an item unmeasured, so it always contains the reported probability."""
    scale = 1.0 if clf.platt is None else clf.platt[0]
    assert scale > 0, "the bounds assume a Platt slope that keeps the order of the logit"
    logit = clf.logit(x)
    p = _sigmoid(logit)
    here = routing(p)
    items = unmeasured(view, symptoms)
    deltas = {(kind, key): (_lab_deltas(clf, key) if kind == "lab" else _symptom_deltas(clf, key)) for kind, key in items}
    low = _sigmoid(logit + scale * sum(d[0] for d in deltas.values()))
    high = _sigmoid(logit + scale * sum(d[1] for d in deltas.values()))
    interval = [min(low, p), max(high, p)]
    gaps = []
    for (kind, key), (dlo, dhi) in deltas.items():
        lo, hi = _sigmoid(logit + scale * dlo), _sigmoid(logit + scale * dhi)
        gaps.append({"kind": kind, "key": key, "low": min(lo, p), "high": max(hi, p),
                     "changes_routing": routing(lo) != here or routing(hi) != here})
    gaps.sort(key=lambda g: (-(g["high"] - g["low"]), g["kind"], g["key"]))
    return interval, gaps
