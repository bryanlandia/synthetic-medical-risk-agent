"""Metrics and honest statistics: AUC, Brier, log-loss, calibration error, a patient-level bootstrap, and the
minimum detectable difference."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

Z_ALPHA = 1.959964  # two-sided 95%
Z_POWER = 0.841621  # 80% power


def auc(y: Sequence[float], p: Sequence[float]) -> float:
    """Rank-based AUC with ties counted as one half (the Mann-Whitney statistic)."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    values = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(values))
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1  # average rank of the tied block
        i = j + 1
    rank_of = np.empty(len(values))
    rank_of[order] = ranks
    return float((rank_of[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def brier(y: Sequence[float], p: Sequence[float]) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(y: Sequence[float], p: Sequence[float], eps: float = 1e-15) -> float:
    y, p = np.asarray(y, dtype=float), np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(y: Sequence[float], p: Sequence[float], bins: int = 10) -> float:
    """Expected calibration error with equal-width bins: the weighted gap between confidence and frequency."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(total)


def mean(values: Sequence[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=float)))


# --- patient-level bootstrap ---------------------------------------------------------------------------------

def _clusters(keys: Sequence[str]) -> list[np.ndarray]:
    groups: dict[str, list[int]] = {}
    for i, k in enumerate(keys):
        groups.setdefault(k, []).append(i)
    return [np.array(v) for v in groups.values()]


def bootstrap(statistic: Callable[..., float], arrays: Sequence[np.ndarray], keys: Sequence[str], *,
              n_boot: int = 1000, seed: int = 0, cluster: bool = True) -> np.ndarray:
    """The statistic over ``n_boot`` resamples. With ``cluster`` all records of a patient are drawn together, so
    matched-pair members count once; without it records are resampled independently."""
    arrays = [np.asarray(a) for a in arrays]
    rng = np.random.default_rng(np.random.SeedSequence([seed, 2718]))
    groups = _clusters(keys) if cluster else [np.array([i]) for i in range(len(keys))]
    out = np.empty(n_boot)
    for b in range(n_boot):
        picks = rng.integers(0, len(groups), size=len(groups))
        idx = np.concatenate([groups[g] for g in picks])
        out[b] = statistic(*[a[idx] for a in arrays])
    return out


def interval(statistic: Callable[..., float], arrays: Sequence[np.ndarray], keys: Sequence[str], *,
             n_boot: int = 1000, seed: int = 0, cluster: bool = True) -> dict[str, float]:
    point = float(statistic(*[np.asarray(a) for a in arrays]))
    draws = bootstrap(statistic, arrays, keys, n_boot=n_boot, seed=seed, cluster=cluster)
    draws = draws[~np.isnan(draws)]
    lo, hi = np.percentile(draws, [2.5, 97.5]) if len(draws) else (float("nan"), float("nan"))
    return {"value": point, "lo": float(lo), "hi": float(hi), "n": len(keys), "patients": len(_clusters(keys))}


def compare(statistic: Callable[..., float], arrays_a: Sequence[np.ndarray], arrays_b: Sequence[np.ndarray],
            keys: Sequence[str], *, n_boot: int = 1000, seed: int = 0) -> dict[str, float | bool]:
    """A minus B on the same records, with a paired patient bootstrap and the smallest difference this sample could
    detect at 80% power. ``below_mdd`` is true when the observed difference is smaller than that."""
    a = [np.asarray(x) for x in arrays_a]
    b = [np.asarray(x) for x in arrays_b]
    diff = float(statistic(*a) - statistic(*b))
    rng = np.random.default_rng(np.random.SeedSequence([seed, 2718]))
    groups = _clusters(keys)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = np.concatenate([groups[g] for g in rng.integers(0, len(groups), size=len(groups))])
        draws[i] = statistic(*[x[idx] for x in a]) - statistic(*[x[idx] for x in b])
    se = float(np.nanstd(draws, ddof=1))
    mdd = (Z_ALPHA + Z_POWER) * se
    return {"diff": diff, "se": se, "lo": float(np.nanpercentile(draws, 2.5)), "hi": float(np.nanpercentile(draws, 97.5)),
            "mdd": mdd, "below_mdd": abs(diff) < mdd}
