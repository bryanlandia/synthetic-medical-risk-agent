"""The system adapter and the reference systems.

A system is anything that takes a record's input view and returns a report: a lookup, a logistic model, a direct
model call, or the deployed service. The reference systems need no API. The oracle looks the truth up by patient
id, so it cheats on purpose: it defines the ceiling and proves the graders, and is labelled a reference.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from data_gen.labs import LAB_KEYS, SYMPTOM_KEYS

from .devsplit import train_ids
from .records import Dataset
from .report import WARNING_TYPES

DISCLAIMER = "This is not medical advice. All data is synthetic and the disease is fictional."
BORDERLINE_BAND = (0.4, 0.6)


class System(Protocol):
    name: str
    version: str
    reference: bool  # reference systems (oracle, floor, baselines) are labelled and excluded from comparisons

    def run(self, view: dict[str, Any]) -> dict[str, Any] | str:
        """Return a report (a dict) or raw text that parses as one."""
        ...


def _panel_labs(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"lab": e["lab"], "value": e["value"], "unit": e["unit"]} for e in view["panel"] if e["value"] is not None]


def scored_report(view: dict[str, Any], probability: float, *, uncertain: bool,
                  symptoms: dict[str, str] | None = None, data_quality: list[dict[str, Any]] | None = None,
                  evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "scored", "probability": float(probability), "uncertain": uncertain,
        "symptoms": symptoms or {k: "not_mentioned" for k in SYMPTOM_KEYS},
        "labs_used": _panel_labs(view), "data_quality": data_quality or [],
        "evidence": evidence or [], "disclaimer": DISCLAIMER,
    }


class OracleSystem:
    """The hidden rule and the plan, looked up by patient id. The ceiling, and a check on every grader."""

    name, reference = "oracle", True

    def __init__(self, dataset: Dataset):
        self.dataset, self.version = dataset, "oracle@1"

    def run(self, view: dict[str, Any]) -> dict[str, Any]:
        record = self.dataset.record(view["patient_id"])
        p = record.ground_truth.true_probability
        stated = {s.flag: {"present": "present", "hedged": "possible", "negated": "absent"}[s.stated]
                  for s in (record.plan.symptoms if record.plan else [])}
        symptoms = {k: stated.get(k, "not_mentioned") for k in SYMPTOM_KEYS}
        seen: set[tuple[str, str | None]] = set()
        warnings: list[dict[str, Any]] = []
        for ann in [*record.noise, *record.tags]:
            if ann.type in WARNING_TYPES and (ann.type, ann.lab) not in seen:
                seen.add((ann.type, ann.lab))
                warnings.append({"type": ann.type, "lab": ann.lab})
        lo, hi = BORDERLINE_BAND
        return scored_report(view, p, uncertain=lo <= p <= hi, symptoms=symptoms, data_quality=warnings,
                             evidence=["Reference system: reads the hidden rule."])


class FloorSystem:
    """Always reports the training prevalence and reads nothing. The floor."""

    name, reference = "floor", True

    def __init__(self, dataset: Dataset):
        labels = [r.ground_truth.label for r in dataset.by_split["train"]]
        self.prevalence = sum(labels) / len(labels)
        self.version = "floor@1"

    def run(self, view: dict[str, Any]) -> dict[str, Any]:
        return scored_report(view, self.prevalence, uncertain=False, evidence=["Reference system: prevalence only."])


class LabOnlySystem:
    """Logistic regression on the lab panel alone, fit with numpy on train excluding dev. It ignores the note and the
    units, so it degrades on unit-mismatch and missing-lab records: a floor for the data-quality categories."""

    name, reference = "lab_only", True

    def __init__(self, dataset: Dataset, l2: float = 1e-3, iterations: int = 30):
        self.version = "lab_only@1"
        usable = set(train_ids(dataset))
        records = [r for r in dataset.by_split["train"] if r.patient_id in usable]
        x = np.array([self._raw(r.input_view()) for r in records], dtype=float)
        y = np.array([r.ground_truth.label for r in records], dtype=float)
        observed = ~np.isnan(x)
        self.mean = np.nanmean(x, axis=0)
        self.std = np.nanstd(x, axis=0) + 1e-9
        self.weights = self._fit(self._features(x), y, l2, iterations)
        self.n_fit = len(records)

    @staticmethod
    def _raw(view: dict[str, Any]) -> list[float]:
        by_lab = {e["lab"]: e["value"] for e in view["panel"]}
        return [np.nan if by_lab.get(k) is None else float(by_lab[k]) for k in LAB_KEYS]

    def _features(self, raw: np.ndarray) -> np.ndarray:
        missing = np.isnan(raw)
        z = np.where(missing, 0.0, (raw - self.mean) / self.std)  # a missing lab sits at the mean
        return np.hstack([np.ones((len(raw), 1)), z, missing.astype(float)])

    @staticmethod
    def _fit(features: np.ndarray, y: np.ndarray, l2: float, iterations: int) -> np.ndarray:
        w = np.zeros(features.shape[1])
        ridge = l2 * np.eye(features.shape[1])
        ridge[0, 0] = 0.0
        for _ in range(iterations):  # Newton / IRLS, deterministic
            p = 1 / (1 + np.exp(-features @ w))
            gradient = features.T @ (p - y) + ridge @ w
            hessian = (features * (p * (1 - p))[:, None]).T @ features + ridge + 1e-9 * np.eye(len(w))
            step = np.linalg.solve(hessian, gradient)
            w -= step
            if np.max(np.abs(step)) < 1e-9:
                break
        return w

    def probability(self, view: dict[str, Any]) -> float:
        feats = self._features(np.array([self._raw(view)]))
        return float(1 / (1 + np.exp(-(feats @ self.weights)[0])))

    def run(self, view: dict[str, Any]) -> dict[str, Any]:
        p = self.probability(view)
        return scored_report(view, p, uncertain=abs(p - 0.5) <= 0.1, evidence=["Reference system: labs only."])
