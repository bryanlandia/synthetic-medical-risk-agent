"""The results summary: every category and metric with its 95% interval, sample size and minimum detectable difference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION, graders as g
from .content import fabricated_labs, safety_failures
from .consistency import matched_pair_spread
from .inspect_tasks import CONSISTENCY_MAX_SD
from .injection import InjectionPair, grade_pair
from .metrics import Z_ALPHA, Z_POWER, auc, brier, ece, interval, log_loss
from .records import patient_key, unique_patients
from .report import WARNING_TYPES
from .targets import attach_targets, load_targets
from .runner import RunResult

MDD_NOTE = ("MDD: the smallest difference between two systems this sample could detect at 80% power, approximated "
            "as 2.8 x sqrt(2) x the bootstrap standard error of the metric. A paired comparison is tighter.")


def _row(category: str, metric: str, stats: dict[str, float], **extra: Any) -> dict[str, Any]:
    se = stats.get("se", float("nan"))
    mdd = (Z_ALPHA + Z_POWER) * np.sqrt(2) * se if se == se else float("nan")
    return {"category": category, "metric": metric, "value": stats["value"], "lo": stats["lo"], "hi": stats["hi"],
            "n": stats["n"], "patients": stats["patients"], "mdd": mdd, **extra}


def _rate(category: str, metric: str, outcomes: list[bool | float], keys: list[str], n_boot: int, seed: int) -> dict[str, Any] | None:
    if not outcomes:
        return None
    return _row(category, metric, interval(np.mean, [np.array(outcomes, dtype=float)], keys, n_boot=n_boot, seed=seed))


def summarize(dataset: Any, run: RunResult, *, n_boot: int = 1000, seed: int = 0, reference: bool = True,
              targets: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every metric with its interval. A system under test is also compared with the targets file (or ``targets``)."""
    sink, rows = run.sink, []

    def add(row: dict[str, Any] | None) -> None:
        if row:
            rows.append(row)

    first = lambda suite: [(dataset.record(sid), ts[0]) for sid, ts in sink.trials.get(suite, {}).items()]  # noqa: E731
    # happy path and the per-record checks that share its records (one record per patient)
    pairs = unique_patients_pairs(first("happy_path"))
    if pairs:
        y = np.array([r.ground_truth.label for r, _ in pairs], dtype=float)
        p = np.array([t.report.probability if t.parsed and t.report.status == "scored" else g.FAILED_PROBABILITY
                      for _, t in pairs])
        keys = [patient_key(r) for r, _ in pairs]
        for name, fn in (("auc", auc), ("brier", brier), ("log_loss", log_loss), ("ece", ece)):
            add(_row("happy_path", name, interval(fn, [y, p], keys, n_boot=n_boot, seed=seed)))
        sym = [float(np.mean([bool(t.parsed and (t.report.symptoms or {}).get(k) == v)
                              for k, v in g.true_symptom_readings(r).items()])) for r, t in pairs]
        add(_rate("symptom_reading", "accuracy", sym, keys, n_boot, seed))
    allp = []  # one trial per sample, with its record (matched-pair groups contribute their members)
    for suite, samples in sink.trials.items():
        for sid, ts in samples.items():
            if suite == "consistency":
                allp += [(dataset.record(t.record_id), t) for t in ts[:4]]
            else:
                allp.append((dataset.record(sid), ts[0]))
    keys_all = [patient_key(r) for r, _ in allp]
    add(_rate("fabrication", "rate", [(not t.parsed) or bool(fabricated_labs(t.report, r.input_view())) for r, t in allp], keys_all, n_boot, seed))
    add(_rate("safety", "pass_rate", [t.parsed and not safety_failures(t.report) for r, t in allp], keys_all, n_boot, seed))
    add(_rate("parse", "failure_rate", [not t.parsed for _, t in allp], keys_all, n_boot, seed))
    # data quality: per warning type recall, and exact match
    dq = first("data_quality")
    for wtype in WARNING_TYPES:
        has = [(r, t) for r, t in dq if wtype in g.true_warning_types(r)]
        add(_rate("data_quality", f"recall:{wtype}", [bool(t.parsed and any(w.type == wtype for w in t.report.data_quality)) for _, t in has],
                  [patient_key(r) for r, _ in has], n_boot, seed))
    add(_rate("data_quality", "exact_match", [bool(t.parsed and {w.type for w in t.report.data_quality} == g.true_warning_types(r)) for r, t in dq],
              [patient_key(r) for r, _ in dq], n_boot, seed))
    # borderline
    bl = first("borderline")
    lo, hi = g.BORDERLINE_BAND
    border = [(r, t) for r, t in bl if lo <= r.ground_truth.true_probability <= hi]
    clear = [(r, t) for r, t in bl if r.ground_truth.true_probability < g.CLEAR_LOW or r.ground_truth.true_probability > g.CLEAR_HIGH]
    unc = lambda t: bool(t.parsed and t.report.status == "scored" and t.report.uncertain)  # noqa: E731
    add(_rate("borderline", "uncertain_rate", [unc(t) for _, t in border], [patient_key(r) for r, _ in border], n_boot, seed))
    add(_rate("borderline", "false_uncertain_rate", [unc(t) for _, t in clear], [patient_key(r) for r, _ in clear], n_boot, seed))
    # adversarial
    adv = [(dataset.record(sid), ts[0], sink.clean["adversarial"][sid][0]) for sid, ts in sink.trials.get("adversarial", {}).items()]
    add(_rate("adversarial", "resistance_rate", [grade_pair(InjectionPair(r, a, c))["resisted"] for r, a, c in adv],
              [patient_key(r) for r, _, _ in adv], n_boot, seed))
    # consistency
    groups = []
    for sid, ts in sink.trials.get("consistency", {}).items():
        members = ts[:4]
        recs = [dataset.record(t.record_id) for t in members]
        spread = matched_pair_spread(list(zip(recs, members)))
        groups.append((sid, spread))
    if groups:
        sds = np.array([s["max_sd"] if s["incomplete_groups"] == 0 else 1.0 for _, s in groups])
        add(_row("consistency", "mean_sd", interval(np.mean, [sds], [sid for sid, _ in groups], n_boot=n_boot, seed=seed)))
        add(_rate("consistency", "pass_rate", [bool(v <= CONSISTENCY_MAX_SD) for v in sds], [sid for sid, _ in groups], n_boot, seed))
    if targets is None and not reference:
        targets = load_targets()
    if targets is not None:
        attach_targets(rows, targets)
    return {"notice": SYNTHETIC_NOTICE, "harness_version": HARNESS_VERSION, "system_version": run.system_version,
            "reference": reference, "split": run.split, "dataset_config_hash": dataset.config_hash, "seed": seed,
            "n_boot": n_boot, "suites": run.suites, "rows": rows, "mdd_note": MDD_NOTE}


def unique_patients_pairs(pairs: list[tuple[Any, Any]]) -> list[tuple[Any, Any]]:
    keep = {id(r) for r in unique_patients([r for r, _ in pairs])}
    return [(r, t) for r, t in pairs if id(r) in keep]


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [f"# Results: {summary['system_version']} on {summary['split']}", "", summary["notice"], "",
             f"Harness {summary['harness_version']}; dataset {summary['dataset_config_hash']}; "
             f"{summary['n_boot']} patient-level bootstrap resamples (seed {summary['seed']}).",
             "A reference system" if summary["reference"] else "A system under test", "",
             "| Category | Metric | Value | 95% interval | n (patients) | MDD |", "|---|---|---|---|---|---|"]
    with_targets = any("target" in r for r in summary["rows"])
    if with_targets:
        lines[-2:] = ["| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |",
                      "|---|---|---|---|---|---|---|---|"]
    for r in summary["rows"]:
        row = (f"| {r['category']} | {r['metric']} | {r['value']:.4f} | [{r['lo']:.4f}, {r['hi']:.4f}] | "
               f"{r['n']} ({r['patients']}) | {r['mdd']:.4f} |")
        if with_targets:
            row += (f" {'>=' if r['direction'] == 'higher' else '<='} {r['target']:.4f} | "
                    f"{'reached' if r['reached'] else 'not reached'}, {r['label']} |") if "target" in r else " | |"
        lines.append(row)
    lines += ["", summary["mdd_note"], ""]
    return "\n".join(lines)


def write_summary(summary: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    js, md = directory / "summary.json", directory / "summary.md"
    js.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    md.write_text(render_markdown(summary))
    return js, md
