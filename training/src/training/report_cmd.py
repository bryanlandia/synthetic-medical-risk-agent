"""``training report``: the classifier's final results, the paired comparison with the frontier baseline and the readings of
failing transcripts, in one file. Incomplete (exit 1) until each target the classifier misses has its transcripts read."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_gen import SYNTHETIC_NOTICE
from evals.baseline_report import FINAL_STAGES, check_reading, final_runs
from evals.summary import render_markdown

from . import pipeline
from .eval_cli import RESULTS_DIR

RESULTS_ROOT = RESULTS_DIR.parent  # evals/results; final_runs reads <root>/classifier/<stage>
READING = RESULTS_DIR / "reading.json"


def _table(summary: dict[str, Any]) -> str:
    """Just the results table of a summary (the report has its own title and notice)."""
    text = render_markdown(summary)
    start = text.index("| Category")
    return text[start:].split("\n\n")[0].rstrip()


def trials_identical(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """(records whose reports are identical in every trial, records) over the repeated-trials stage."""
    outputs: dict[str, set[str]] = {}
    for r in rows:
        outputs.setdefault(r["record_id"], set()).add(r["raw_output"])
    return sum(len(v) == 1 for v in outputs.values()), len(outputs)


def generate(root: Path = RESULTS_ROOT, reading_path: Path = READING, model_dir: Path = pipeline.MODEL_DIR,
             comparison: Path | None = None) -> tuple[str, list[str]]:
    runs = final_runs(root, "classifier")
    reading = json.loads(reading_path.read_text()) if reading_path.exists() else None
    manifest = json.loads((model_dir / "manifest.json").read_text())
    missing = [f"final stage not run: {s}" for s in FINAL_STAGES if s not in runs]
    missing += check_reading(runs, reading)
    L = ["# Classifier: final results", "", SYNTHETIC_NOTICE, ""]
    if missing:
        L += ["> **INCOMPLETE.** " + "; ".join(missing), ""]
    version = next((r["summary"]["system_version"] for r in runs.values()), "unknown")
    L += [f"- System `{version}`; model hash `{manifest['model_hash']}`. Each protected split was scored once with `--final` "
          "(the ledger records it).",
          "- The model was fitted on train without the dev ids; the regularisation and the conflict rule were chosen on dev.",
          "- Targets are targets v1; 'reached' is the plain fact and the label says whether the 95% interval settles it.", ""]
    if "trials" in runs:
        same, total = trials_identical(runs["trials"]["rows"])
        L += [f"- Determinism: {same} of {total} matched-pair records gave the identical report in all three trials. "
              "(The consistency metrics below are a different thing: the spread of one patient's probability across the four "
              "documentation settings, whose notes differ.)", ""]
    for stage in FINAL_STAGES:
        if stage in runs:
            L += [f"## {stage}", "", _table(runs[stage]["summary"]), ""]
    cmp_path = comparison or RESULTS_DIR / "comparison_test.md"
    if cmp_path.exists():
        body = cmp_path.read_text().split("\n", 1)[1]  # drop the comparison's own title line
        L += ["## Compared with the frontier baseline (test)", "", body.strip().replace("\n## ", "\n### "), ""]
    if reading:
        L += ["## Failing transcripts read", ""]
        for e in reading["readings"]:
            L += [f"### {e['grader']} ({len(e['transcripts'])} transcripts read)", "", e["findings"], ""]
            if e.get("grader_fault"):
                L += [f"Grader fault: {e['grader_fault']}", ""]
    return "\n".join(L), missing


def write(**kw: Any) -> tuple[Path, list[str]]:
    text, missing = generate(**kw)
    out = RESULTS_DIR / "report.md"
    out.write_text(text + "\n")
    return out, missing
