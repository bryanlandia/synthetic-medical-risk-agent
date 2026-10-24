"""Dataset manifest: provenance plus the Bayes-optimal ceiling for later model comparison."""

from __future__ import annotations

from collections import Counter

import numpy as np

from . import GENERATOR_VERSION, PLAN_VERSION, SCHEMA_VERSION, SYNTHETIC_NOTICE
from .config import GenConfig
from .injections import catalog_version
from .schema import Record

SPLITS = ("train", "test", "adversarial")


def auc(p: np.ndarray, y: np.ndarray) -> float:
    """Rank-based AUC (probability a random positive scores above a random negative)."""
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    _, inv, counts = np.unique(p, return_inverse=True, return_counts=True)
    ranks = (np.bincount(inv, weights=ranks) / counts)[inv]  # average ranks over ties
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def bayes_ceiling(records: list[Record]) -> dict:
    p = np.array([r.ground_truth.true_probability for r in records])
    y = np.array([r.ground_truth.label for r in records])
    eps = 1e-12
    return {
        "auc": round(auc(p, y), 6),
        "brier": round(float(np.mean((p - y) ** 2)), 6),
        "log_loss": round(float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))), 6),
    }


def build_manifest(cfg: GenConfig, by_split: dict[str, list[Record]]) -> dict:
    splits = {}
    for name in SPLITS:
        recs = by_split[name]
        splits[name] = {
            "n": len(recs),
            "prevalence": round(float(np.mean([r.ground_truth.label for r in recs])), 6),
            "mean_true_probability": round(float(np.mean([r.ground_truth.true_probability for r in recs])), 6),
            "styles": dict(sorted(Counter(r.style for r in recs).items())),
            "noise_counts": dict(sorted(Counter(n.type for r in recs for n in r.noise).items())),
            "tag_record_counts": dict(sorted(Counter(t for r in recs for t in r.tag_types()).items())),
            "bayes_ceiling": bayes_ceiling(recs),
        }
    return {
        "notice": SYNTHETIC_NOTICE,
        "synthetic": True,
        "seed": cfg.seed,
        "generator_version": GENERATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "plan_version": PLAN_VERSION,
        "injection_catalog_version": catalog_version(),
        "note_source": "template",
        "config": cfg.model_dump(mode="json"),
        "config_hash": cfg.config_hash(),
        "llm_calls": 0,
        "excluded_records": 0,
        "splits": splits,
    }
