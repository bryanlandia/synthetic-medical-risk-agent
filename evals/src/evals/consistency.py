"""Consistency: spread of the probability across the four settings of a matched pair, and pass@k / pass^k over trials."""

from __future__ import annotations

from collections import defaultdict
from math import comb
from typing import Any

import numpy as np

from .harness import Trial

Pair = tuple[Any, Trial]


def matched_pair_spread(pairs: list[Pair]) -> dict[str, Any]:
    """Standard deviation of the probability across the members of each matched-pair group (0 means perfectly
    consistent). A group with an invalid report is counted as incomplete, not dropped."""
    groups: dict[str, list[Trial]] = defaultdict(list)
    for record, trial in pairs:
        if record.pair_group:
            groups[record.pair_group].append(trial)
    spreads, incomplete = [], 0
    for members in groups.values():
        if len(members) < 2:
            continue
        if not all(t.parsed and t.report.status == "scored" for t in members):
            incomplete += 1
            continue
        spreads.append(float(np.std([t.report.probability for t in members])))
    return {"groups": len(spreads) + incomplete, "incomplete_groups": incomplete,
            "mean_sd": float(np.mean(spreads)) if spreads else float("nan"),
            "max_sd": float(np.max(spreads)) if spreads else float("nan")}


def pass_at_k(successes: int, trials: int, k: int) -> float:
    """Probability that at least one of k trials succeeds (unbiased estimate from ``trials`` attempts)."""
    if k > trials:
        raise ValueError("k cannot exceed the number of trials")
    return 1.0 - comb(trials - successes, k) / comb(trials, k)


def pass_hat_k(successes: int, trials: int, k: int) -> float:
    """Probability that all k trials succeed (pass^k): the consistency metric."""
    if k > trials:
        raise ValueError("k cannot exceed the number of trials")
    return comb(successes, k) / comb(trials, k)


def trial_consistency(outcomes: dict[str, list[bool]], k: int) -> dict[str, float]:
    """pass@k and pass^k averaged over tasks; ``outcomes`` maps a task id to the success of each of its trials."""
    at = [pass_at_k(sum(v), len(v), k) for v in outcomes.values()]
    hat = [pass_hat_k(sum(v), len(v), k) for v in outcomes.values()]
    return {"tasks": len(outcomes), "k": k, "pass_at_k": float(np.mean(at)), "pass_hat_k": float(np.mean(hat))}
