"""The served probability model: a logistic regression on the features, then an optional Platt scaling. numpy only."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import features
from .labs import LAB_KEYS


class RiskClassifier:
    """Built from the exported dictionary (see ``training.classifier_fit.export``)."""

    def __init__(self, spec: dict[str, Any]):
        assert tuple(spec["features"]) == features.FEATURE_NAMES, "the model was fitted on different features"
        assert tuple(spec["labs"]) == LAB_KEYS
        self.means = np.array(spec["means"], dtype=float)
        self.sds = np.array(spec["sds"], dtype=float)
        self.coef = np.array(spec["coef"], dtype=float)
        self.intercept = float(spec["intercept"])
        platt = spec.get("platt")
        self.platt = None if platt is None else (float(platt["a"]), float(platt["b"]))

    def vector(self, view: dict[str, Any], symptoms: dict[str, str]) -> np.ndarray:
        return features.build(view, symptoms, self.means, self.sds)

    def logit(self, x: np.ndarray) -> float:
        raw = float(x @ self.coef + self.intercept)
        return raw if self.platt is None else self.platt[0] * raw + self.platt[1]

    def probability(self, view: dict[str, Any], symptoms: dict[str, str]) -> float:
        z = self.logit(self.vector(view, symptoms))
        return float(1.0 / (1.0 + np.exp(-z)))

    def contributions(self, x: np.ndarray) -> np.ndarray:
        """Each feature's share of the logit (after any Platt scaling), exact for a logistic model."""
        scale = 1.0 if self.platt is None else self.platt[0]
        return x * self.coef * scale
