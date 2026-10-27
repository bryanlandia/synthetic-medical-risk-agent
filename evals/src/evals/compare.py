"""Compare two systems on the same patients: paired differences with patient-clustered bootstrap intervals.

Both systems must have been run on the same split. The probability metrics use the happy-path suite, one record per
patient; a patient one system failed to score counts with the neutral failed-report probability, as in the summaries.
The other rows are each system's own summary side by side, unpaired, with the interval of each."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION
from .frontier import RESULTS_DIR as FRONTIER_RESULTS
from .graders import FAILED_PROBABILITY
from .metrics import auc, brier, compare, log_loss
from .records import Dataset, patient_key
from .transcripts import read_transcripts

CLASSIFIER_RESULTS = FRONTIER_RESULTS.parent / "classifier"
METRICS: tuple[tuple[str, Callable[..., float], str], ...] = (("auc", auc, "higher"), ("brier", brier, "lower"),
                                                              ("log_loss", log_loss, "lower"))
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}


def stage_dir(system: str, split: str, model: str = "haiku", root: Path | None = None) -> Path:
    """Where a system's run on a split was written ("trials" and "scope" stages have their own folders)."""
    model_id = MODELS.get(model, model)
    if system == "classifier":
        return (root or CLASSIFIER_RESULTS) / split
    if system == "agent":  # the live runs; scripted runs are in results/agent_scripted and are never compared
        return (root or CLASSIFIER_RESULTS.parent / "agent") / split
    if system == "frontier":
        base = root or FRONTIER_RESULTS
        if split == "dev":
            found = sorted((base / "dev").glob(f"v*_{model_id}"))
            if not found:
                raise FileNotFoundError(f"no frontier dev run for {model_id} in {base / 'dev'}")
            return found[-1]
        return base / model_id / split
    raise ValueError(f"unknown system {system!r}: choose classifier, agent or frontier, or pass a directory")


def probabilities(rows: list[dict[str, Any]], dataset: Dataset) -> dict[str, tuple[float, float, str]]:
    """Patient key -> (label, probability, record id) over the first trial of the happy-path suite, one record per patient."""
    out: dict[str, tuple[float, float, str]] = {}
    for row in sorted(rows, key=lambda r: r["record_id"]):
        if row["suite"] != "happy_path" or row["trial_index"] != 0:
            continue
        record = dataset.record(row["record_id"])
        key = patient_key(record)
        if key in out:
            continue
        report = row.get("report")
        p = report["probability"] if report and report.get("status") == "scored" else FAILED_PROBABILITY
        out[key] = (float(record.ground_truth.label), float(p), row["record_id"])
    return out


def verdict(direction: str, diff: float, lo: float, hi: float, a: str, b: str) -> str:
    """Better, worse or not distinguishable from the interval of A minus B (a lower-is-better metric flips the sign)."""
    sign = 1 if direction == "higher" else -1
    if sign * lo > 0:
        return f"{a} is better"
    if sign * hi < 0:
        return f"{b} is better"
    return "not distinguishable"


def paired(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], dataset: Dataset, a: str = "A", b: str = "B",
           n_boot: int = 1000, seed: int = 0) -> dict[str, Any]:
    pa, pb = probabilities(rows_a, dataset), probabilities(rows_b, dataset)
    keys = sorted(set(pa) & set(pb))
    if not keys:
        raise ValueError("the two runs share no happy-path patients")
    y = np.array([pa[k][0] for k in keys])
    xa, xb = np.array([pa[k][1] for k in keys]), np.array([pb[k][1] for k in keys])
    rows = []
    for name, fn, direction in METRICS:
        c = compare(fn, [y, xa], [y, xb], keys, n_boot=n_boot, seed=seed)
        rows.append({"metric": name, "direction": direction, "a": float(fn(y, xa)), "b": float(fn(y, xb)),
                     "diff": c["diff"], "lo": c["lo"], "hi": c["hi"], "mdd": c["mdd"],
                     "verdict": verdict(direction, c["diff"], c["lo"], c["hi"], a, b)})
    return {"patients": len(keys), "only_a": len(set(pa) - set(pb)), "only_b": len(set(pb) - set(pa)), "rows": rows}


def side_by_side(summary_a: dict[str, Any], summary_b: dict[str, Any]) -> list[dict[str, Any]]:
    by_b = {(r["category"], r["metric"]): r for r in summary_b["rows"]}
    out = []
    for r in summary_a["rows"]:
        other = by_b.get((r["category"], r["metric"]))
        if other:
            out.append({"category": r["category"], "metric": r["metric"], "a": r, "b": other})
    return out


def render(result: dict[str, Any], a: str, b: str, split: str, extra: list[dict[str, Any]] | None = None,
           versions: tuple[str, str] = ("", "")) -> str:
    L = [f"# {a} compared with {b} on {split}", "", SYNTHETIC_NOTICE, "",
         f"Harness {HARNESS_VERSION}. Systems: {a} `{versions[0]}`, {b} `{versions[1]}`. Same patients, one record each: "
         f"{result['patients']} patients ({result['only_a']} only in {a}'s run, {result['only_b']} only in {b}'s, left out).",
         "", "## Paired differences (A minus B, 95% interval from a patient-clustered bootstrap)", "",
         f"| Metric | {a} | {b} | Difference | 95% interval | MDD | Verdict |", "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        better = "higher is better" if r["direction"] == "higher" else "lower is better"
        L.append(f"| {r['metric']} ({better}) | {r['a']:.4f} | {r['b']:.4f} | {r['diff']:+.4f} | "
                 f"[{r['lo']:+.4f}, {r['hi']:+.4f}] | {r['mdd']:.4f} | {r['verdict']} |")
    L += ["", "MDD: the smallest difference this sample could detect at 80% power. A verdict says better or worse only when "
              "the whole interval is on one side of zero.", ""]
    if extra:
        L += ["## Every other metric, side by side (not paired)", "",
              f"| Category | Metric | {a} | {b} |", "|---|---|---|---|"]
        for e in extra:
            cell = lambda r: f"{r['value']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}]"  # noqa: E731
            L.append(f"| {e['category']} | {e['metric']} | {cell(e['a'])} | {cell(e['b'])} |")
        L.append("")
    return "\n".join(L)


def cmd_compare(args: Any, dataset: Dataset) -> int:
    try:
        dir_a = Path(args.a_dir) if args.a_dir else stage_dir(args.a, args.split, args.model)
        dir_b = Path(args.b_dir) if args.b_dir else stage_dir(args.b, args.split, args.model)
        rows_a, rows_b = read_transcripts(dir_a / "trials.jsonl"), read_transcripts(dir_b / "trials.jsonl")
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = paired(rows_a, rows_b, dataset, args.a, args.b)
    sums = [json.loads((d / "summary.json").read_text()) for d in (dir_a, dir_b)]
    text = render(result, args.a, args.b, args.split, side_by_side(*sums), (sums[0]["system_version"], sums[1]["system_version"]))
    out = Path(args.out) if args.out else CLASSIFIER_RESULTS / f"comparison_{args.split}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n")
    for r in result["rows"]:
        print(f"{r['metric']:<9} {args.a} {r['a']:.4f} vs {args.b} {r['b']:.4f}: {r['diff']:+.4f} "
              f"[{r['lo']:+.4f}, {r['hi']:+.4f}] {r['verdict']}")
    print(f"wrote {out}")
    return 0
