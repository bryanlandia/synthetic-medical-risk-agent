"""Fit the logistic classifier with cross-fitted Platt scaling, pick its settings on dev, and score the diagnostic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from evals import metrics
from evals.records import patient_key
from risk_model import features
from risk_model.classifier import RiskClassifier
from risk_model.labs import LAB_KEYS
from risk_model.reader import NoteReader
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

GRID_PATH = Path(__file__).resolve().parents[2] / "config" / "grid.json"
MIN_PLATT_GAIN = 1e-4  # Platt scaling is kept only if it lowers the out-of-fold log loss by more than this


def load_grid(path: Path = GRID_PATH) -> dict[str, Any]:
    grid = json.loads(Path(path).read_text())
    n = len(grid["logistic_c"])
    if n > grid["max_candidates"] or grid["max_candidates"] > 12:
        raise ValueError(f"the grid has {n} candidates; at most {min(grid['max_candidates'], 12)} are allowed")
    return grid


def lab_statistics(records) -> tuple[np.ndarray, np.ndarray]:
    """Mean and standard deviation of each lab over the observed, possible values of the training records."""
    cols = [[] for _ in LAB_KEYS]
    for r in records:
        values = features.panel_values(r.input_view())
        for i, k in enumerate(LAB_KEYS):
            if values[k] is not None:
                cols[i].append(values[k])
    return np.array([np.mean(c) for c in cols]), np.array([np.std(c) + 1e-9 for c in cols])


def matrix(records, reader: NoteReader, means: np.ndarray, sds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([features.build(r.input_view(), reader.read(r.input.note).readings, means, sds) for r in records])
    y = np.array([r.ground_truth.label for r in records], dtype=float)
    return x, y


def _logloss(y: np.ndarray, z: np.ndarray) -> float:
    return metrics.log_loss(y, 1.0 / (1.0 + np.exp(-z)))


def fit_platt(z: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def fit_logistic(x: np.ndarray, y: np.ndarray, c: float, seed: int, folds: int) -> dict[str, Any]:
    """The weights on all of x, and Platt scaling from out-of-fold logits, kept only if it lowers their log loss."""
    model = LogisticRegression(C=c, max_iter=5000, random_state=seed).fit(x, y)
    oof = np.zeros(len(y))
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed).split(x, y):
        oof[te] = LogisticRegression(C=c, max_iter=5000, random_state=seed).fit(x[tr], y[tr]).decision_function(x[te])
    a, b = fit_platt(oof, y)
    before, after = _logloss(y, oof), _logloss(y, a * oof + b)
    return {"coef": model.coef_[0], "intercept": float(model.intercept_[0]),
            "platt": {"a": a, "b": b} if after < before - MIN_PLATT_GAIN else None,
            "oof_log_loss": {"before": before, "after": after}}


def spec_for(fitted: dict[str, Any], means: np.ndarray, sds: np.ndarray, extra: dict[str, Any]) -> dict[str, Any]:
    return {"features": list(features.FEATURE_NAMES), "labs": list(LAB_KEYS), "means": means.tolist(), "sds": sds.tolist(),
            "coef": np.asarray(fitted["coef"]).tolist(), "intercept": fitted["intercept"], "platt": fitted["platt"],
            "fit": extra}


def select(x_tr, y_tr, x_dev, y_dev, grid: dict[str, Any], means, sds) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fit every candidate on train, score each on dev by log loss, and return the best spec and all scores."""
    seed, folds = grid["seed"], grid["folds"]
    scored = []
    for c in grid["logistic_c"]:
        fitted = fit_logistic(x_tr, y_tr, c, seed, folds)
        spec = spec_for(fitted, means, sds, {"c": c, "seed": seed, "folds": folds, "oof_log_loss": fitted["oof_log_loss"]})
        clf = RiskClassifier(spec)
        p = np.array([1 / (1 + np.exp(-clf.logit(row))) for row in x_dev])
        scored.append({"c": c, "dev_log_loss": metrics.log_loss(y_dev, p), "platt": spec["platt"] is not None, "spec": spec})
    best = min(scored, key=lambda s: (s["dev_log_loss"], s["c"]))
    return best["spec"], [{k: v for k, v in s.items() if k != "spec"} for s in scored]


def dev_probabilities(spec: dict[str, Any], x_dev: np.ndarray) -> np.ndarray:
    clf = RiskClassifier(spec)
    return np.array([1 / (1 + np.exp(-clf.logit(row))) for row in x_dev])


def gbm_diagnostic(x_tr, y_tr, x_dev, grid: dict[str, Any]) -> np.ndarray:
    """Dev probabilities of a small gradient-boosted model. Reported next to the logistic model and never served."""
    g = grid["gbm_diagnostic"]
    model = HistGradientBoostingClassifier(max_depth=g["max_depth"], learning_rate=g["learning_rate"], max_iter=g["max_iter"],
                                           min_samples_leaf=g["min_samples_leaf"], random_state=grid["seed"])
    return model.fit(x_tr, y_tr).predict_proba(x_dev)[:, 1]


def dev_metrics(records, p: np.ndarray, n_boot: int = 1000, seed: int = 0) -> dict[str, dict[str, float]]:
    y = np.array([r.ground_truth.label for r in records], dtype=float)
    keys = [patient_key(r) for r in records]
    out = {}
    for name, fn in (("auc", metrics.auc), ("brier", metrics.brier), ("log_loss", metrics.log_loss), ("ece", metrics.ece)):
        out[name] = metrics.interval(fn, [y, p], keys, n_boot=n_boot, seed=seed)
    return out
