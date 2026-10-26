"""The harness self-check: the oracle knows the answers, so every grader must score it as expected. A grader that
does not is reported as broken, instead of being blamed on a system under test."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import consistency, graders, injection
from .harness import run_system
from .records import Dataset
from .systems import System

CEILING_TOLERANCE = 0.0005

# name -> the grader function; tests substitute one to prove a broken grader is caught
GRADERS: dict[str, Callable[..., Any]] = {
    "happy_path": graders.happy_path, "symptom_reading": graders.symptom_reading,
    "fabrication": graders.fabrication, "safety": graders.safety, "data_quality": graders.data_quality,
    "borderline": graders.borderline, "injection": injection.injection,
    "matched_pair_spread": consistency.matched_pair_spread,
}


def _expectations(dataset: Dataset) -> dict[str, Callable[[Any], str | None]]:
    """name -> function returning None if the oracle's result is right, else a description of what is wrong."""
    ceiling = dataset.manifest["splits"]["test"]["bayes_ceiling"]

    def happy(r):
        bad = [m for m in ("auc", "brier", "log_loss") if abs(r[m] - ceiling[m]) > CEILING_TOLERANCE]
        return f"oracle misses the ceiling on {bad}" if bad else None

    def dq(r):
        bad = [t for t, v in r["per_type"].items() if v["records_with"] and (v["recall"] != 1.0 or v["precision"] != 1.0)]
        return f"oracle recall or precision below 1 for {bad}" if bad else None

    return {
        "happy_path": happy,
        "symptom_reading": lambda r: None if r["accuracy"] == 1.0 else f"oracle accuracy {r['accuracy']:.3f}",
        "fabrication": lambda r: None if r["rate"] == 0.0 else f"oracle fabricates {r['rate']:.3f}",
        "safety": lambda r: None if r["pass_rate"] == 1.0 else f"oracle safety pass rate {r['pass_rate']:.3f}",
        "data_quality": dq,
        "borderline": lambda r: None if (r["borderline_uncertain_rate"] == 1.0 and r["clear_uncertain_rate"] == 0.0)
        else f"oracle uncertain on borderline {r['borderline_uncertain_rate']}, on clear {r['clear_uncertain_rate']}",
        "injection": lambda r: None if r["resistance_rate"] == 1.0 else f"oracle resistance {r['resistance_rate']:.3f}",
        "matched_pair_spread": lambda r: None if r["max_sd"] == 0.0 else f"oracle spread {r['max_sd']}",
    }


def self_check(dataset: Dataset, oracle: System, grader_fns: dict[str, Callable[..., Any]] | None = None) -> dict[str, str]:
    """Run every grader on the oracle; return {grader name: problem} for each one that is not as expected."""
    fns = {**GRADERS, **(grader_fns or {})}
    expect = _expectations(dataset)
    test, adversarial = dataset.by_split["test"], dataset.by_split["adversarial"]
    test_trials = run_system(oracle, test)
    adv_trials = run_system(oracle, adversarial)
    both = list(zip(test, test_trials)) + list(zip(adversarial, adv_trials))
    inputs: dict[str, Any] = {
        "happy_path": list(zip(test, test_trials)),
        "matched_pair_spread": list(zip(test, test_trials)),
        "injection": injection.run_injection_pairs(oracle, adversarial),
    }
    broken: dict[str, str] = {}
    for name, fn in fns.items():
        result = fn(inputs.get(name, both))
        problem = expect[name](result)
        if problem:
            broken[name] = problem
    return broken
