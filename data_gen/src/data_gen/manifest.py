"""Dataset manifest: provenance plus the Bayes-optimal ceiling for later model comparison."""

from __future__ import annotations

from collections import Counter

import numpy as np

from . import (
    GENERATOR_VERSION,
    PLAN_VERSION,
    PLAN_VERSION_LLM,
    SCHEMA_VERSION,
    SCHEMA_VERSION_LLM,
    SYNTHETIC_NOTICE,
)
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


def _unique(records: list[Record]) -> list[Record]:
    seen: set[str] = set()
    out = []
    for r in records:
        key = r.pair_group or r.patient_id
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build_manifest(cfg: GenConfig, by_split: dict[str, list[Record]], llm_stats: dict | None = None) -> dict:
    splits = {}
    for name in SPLITS:
        all_recs = by_split[name]
        recs = _unique(all_recs) if cfg.note_source == "llm" else all_recs  # matched pairs count once
        splits[name] = {
            "n": len(all_recs),
            "prevalence": round(float(np.mean([r.ground_truth.label for r in recs])), 6),
            "mean_true_probability": round(float(np.mean([r.ground_truth.true_probability for r in recs])), 6),
            "styles": dict(sorted(Counter(r.style for r in all_recs).items())),
            "noise_counts": dict(sorted(Counter(n.type for r in all_recs for n in r.noise).items())),
            "tag_record_counts": dict(sorted(Counter(t for r in all_recs for t in r.tag_types()).items())),
            "bayes_ceiling": bayes_ceiling(recs),
        }
        if cfg.note_source == "llm":
            splits[name]["n_unique_patients"] = len(recs)
    manifest = {
        "notice": SYNTHETIC_NOTICE,
        "synthetic": True,
        "seed": cfg.seed,
        "generator_version": GENERATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "plan_version": PLAN_VERSION,
        "injection_catalog_version": catalog_version(),
        "note_source": "template",
        "config": cfg.canonical_dump(),
        "config_hash": cfg.config_hash(),
        "llm_calls": 0,
        "excluded_records": 0,
        "splits": splits,
    }
    if cfg.note_source == "llm":
        stats = llm_stats or {}
        manifest.update(
            note_source="llm",
            plan_version=PLAN_VERSION_LLM,
            schema_version=SCHEMA_VERSION_LLM,
            llm=stats,
            llm_calls=stats.get("paid_calls"),
            excluded_records=sum(stats.get("excluded", {}).values()),
        )
    return manifest
