"""The frontier baseline report: results against targets v1, the prompt iteration record, the spend, and the reading.

The reading file (``results/frontier/reading.json``) records, for each grader the final system fails, which failing
transcripts a person read and what they showed. Each transcript id is checked against the real failing transcripts,
so the file cannot claim a reading that did not happen. Without it the report is marked INCOMPLETE.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_gen import SYNTHETIC_NOTICE

from . import protocol
from .frontier import FINAL_MODEL, RESULTS_DIR
from .targets import CLEARLY_MET, CLEARLY_NOT_MET
from .transcripts import GRADER_NAMES, read_transcripts

READING_PATH = RESULTS_DIR / "reading.json"
MIN_READ = 10
FINAL_STAGES = ("test", "adversarial", "trials")
CATEGORY_GRADER = {"adversarial": "injection"}  # the summary's category name -> the transcript grader name


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def failing_ids(rows: list[dict[str, Any]], grader: str) -> set[str]:
    """``suite:sample_id:trial`` for every transcript that failed the grader."""
    return {f"{r['suite']}:{r['sample_id']}:{r['trial_index']}" for r in rows
            if r.get("variant") != "addendum_removed" and grader in r.get("graders", {})
            and not r["graders"][grader]["passed"]}


def final_runs(root: Path, model: str) -> dict[str, dict[str, Any]]:
    out = {}
    for stage in FINAL_STAGES:
        d = root / model / stage
        if (d / "summary.json").exists():
            out[stage] = {"summary": _json(d / "summary.json"), "run": _json(d / "run.json"),
                          "rows": read_transcripts(d / "trials.jsonl")}
    return out


def failed_graders(runs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """grader -> the 'stage: category.metric' entries that did not reach their target."""
    out: dict[str, list[str]] = {}
    for stage, run in runs.items():
        for row in run["summary"]["rows"]:
            if row.get("reached") is False:
                grader = CATEGORY_GRADER.get(row["category"], row["category"])
                out.setdefault(grader, []).append(f"{stage}: {row['category']}.{row['metric']}")
    return out


def check_reading(runs: dict[str, dict[str, Any]], reading: dict[str, Any] | None) -> list[str]:
    """What is missing from the reading file; empty when every failed grader was read properly."""
    problems = []
    entries = {e["grader"]: e for e in (reading or {}).get("readings", [])}
    all_rows = [r for run in runs.values() for r in run["rows"]]
    for grader in sorted(failed_graders(runs)):
        if grader not in GRADER_NAMES:
            continue
        failing = failing_ids(all_rows, grader)
        entry = entries.get(grader)
        if entry is None:
            problems.append(f"{grader}: no entry in the reading file ({len(failing)} failing transcripts)")
            continue
        read = set(entry.get("transcripts", []))
        need = min(MIN_READ, len(failing))
        if not read <= failing:
            problems.append(f"{grader}: {len(read - failing)} transcript id(s) are not failing transcripts of this grader")
        elif len(read) < need:
            problems.append(f"{grader}: read {len(read)} of the {need} required")
        if not str(entry.get("findings", "")).strip():
            problems.append(f"{grader}: no findings written")
    return problems


def _table(summary: dict[str, Any]) -> list[str]:
    lines = ["| Category | Metric | Value | 95% interval | n (patients) | MDD | Target | Against target |",
             "|---|---|---|---|---|---|---|---|"]
    for r in summary["rows"]:
        tail = (f"{'>=' if r['direction'] == 'higher' else '<='} {r['target']:.4f} | "
                f"{'reached' if r['reached'] else 'not reached'}, {r['label']}") if "target" in r else " | "
        lines.append(f"| {r['category']} | {r['metric']} | {r['value']:.4f} | [{r['lo']:.4f}, {r['hi']:.4f}] | "
                     f"{r['n']} ({r['patients']}) | {r['mdd']:.4f} | {tail} |")
    return lines


def _tally(summary: dict[str, Any]) -> str:
    rows = [r for r in summary["rows"] if "label" in r]
    count = lambda label: sum(r["label"] == label for r in rows)  # noqa: E731
    return (f"{len(rows)} metrics with a target: {sum(r['reached'] for r in rows)} reached; "
            f"{count(CLEARLY_MET)} clearly met, {count('not distinguishable')} not distinguishable, "
            f"{count(CLEARLY_NOT_MET)} clearly not met")


def generate(root: Path | None = None, model: str = FINAL_MODEL, *, reading_path: Path | None = None,
             protocol_path: Path | None = None) -> tuple[str, list[str]]:
    """The report text and the list of what is missing (empty when it is complete)."""
    root = root or RESULTS_DIR
    reading_path = reading_path or (root / "reading.json")
    chain = protocol.load_chain(protocol_path)
    frozen = next((e for e in chain if e["kind"] == "freeze"), None)
    runs = final_runs(root, model)
    reading = _json(reading_path) if reading_path.exists() else None
    missing = [f"final stage not run: {s}" for s in FINAL_STAGES if s not in runs]
    if frozen is None:
        missing.append("the prompt is not frozen")
    missing += check_reading(runs, reading)
    spend = sum(_json(p)["spend_usd"] for p in sorted(root.rglob("run.json")))
    L = ["# Frontier baseline", "", SYNTHETIC_NOTICE, ""]
    if missing:
        L += ["> **INCOMPLETE.** " + "; ".join(missing), ""]
    L += [f"- Final model: `{model}`, running the frozen prompt. The dev section lists every model the prompt was scored on there.",
          f"- Frozen prompt hash: `{frozen['prompt_hash'] if frozen else 'not frozen'}`"
          f" (version file `{next((e['prompt_version'] for e in chain if frozen and e['prompt_hash'] == frozen['prompt_hash']), '?')}`).",
          f"- Total spend recorded by the runs: ${spend:.2f}.",
          "- The prompt is a qualitative briefing of the fictional disease: which markers raise or lower risk and which "
          "symptoms weigh more, in words. It has no weights, thresholds or intercept and no record from any split; this "
          "is the information the comparison grants the frontier model, and a trained model has to learn it from data.",
          "- Targets are targets v1 (`results/targets_v1.json`), derived on dev from the reference baselines. "
          "'Reached' is the plain fact; the label says whether the 95% interval settles it.", ""]
    L += ["## Prompt versions scored on dev", "",
          "| # | Kind | Prompt | Model | AUC | Brier | Spend | Decision |", "|---|---|---|---|---|---|---|---|"]
    for e in chain:
        if e["kind"] == "freeze":
            L.append(f"| {e['index']} | freeze | `{e['prompt_hash']}` | | | | | frozen as the final prompt |")
            continue
        m = e.get("metrics", {})
        cell = lambda k: f"{m[k]['value']:.3f} [{m[k]['lo']:.3f}, {m[k]['hi']:.3f}]" if k in m else ""  # noqa: E731
        L.append(f"| {e['index']} | {e['kind']} | `{e['prompt_hash']}` ({e['prompt_version']}) | {e['model']} | "
                 f"{cell('happy_path.auc')} | {cell('happy_path.brier')} | ${e['spend_usd']:.2f} | {e.get('note', '')} |")
    L += [""]
    dev = sorted(root.glob("dev/*/summary.json"))
    for path in dev:
        if "_smoke" in path.parent.name:
            continue
        s = _json(path)
        L += [f"## Dev: {path.parent.name}", "", _tally(s), "", *_table(s), ""]
    labels = {"test": "Test (one final run)", "adversarial": "Adversarial (one final run)",
              "trials": "Matched pairs, three trials (test split)"}
    for stage, run in runs.items():
        run_info = run["run"]
        L += [f"## {labels[stage]}", "", f"System `{run['summary']['system_version']}`; {run_info['calls_made']} paid calls, "
              f"${run_info['spend_usd']:.2f}.", "", _tally(run["summary"]), "", *_table(run["summary"]), ""]
    L += ["## What was read", ""]
    failed = failed_graders(runs)
    if not failed:
        L += ["No grader failed a target, so no failing transcripts needed reading.", ""]
    for grader, where in sorted(failed.items()):
        entry = next((e for e in (reading or {}).get("readings", []) if e["grader"] == grader), None)
        L += [f"### {grader}", "", f"Missed targets: {', '.join(where)}.", ""]
        if entry:
            fault = entry.get("grader_fault")
            L += [f"Read {len(entry.get('transcripts', []))} failing transcripts. {entry.get('findings', '')}",
                  f"Grader at fault: {fault}." if fault else "", ""]
        else:
            L += ["Not yet read.", ""]
    return "\n".join(L), missing
