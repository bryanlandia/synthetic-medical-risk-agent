"""The text path against the structured path on dev: render a record as a message, run intake and the classifier, and compare
the probability with the one the classifier gives the record directly. Every record outside the tolerance is explained."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import risk_model
from evals.messages import render_message
from evals.records import input_view
from risk_model import intake
from risk_model.labs import LAB_KEYS, SYMPTOM_KEYS

from . import data
from .system import MODEL_DIR

TOLERANCE = 0.001
MIN_SHARE = 0.95


def _why(structured_view: dict[str, Any], text_view: dict[str, Any], rep_a: dict[str, Any], rep_b: dict[str, Any]) -> list[str]:
    reasons = []
    a = {e["lab"]: e["value"] for e in structured_view["panel"]}
    b = {e["lab"]: e["value"] for e in text_view["panel"]}
    for lab in LAB_KEYS:
        if a[lab] != b[lab]:
            reasons.append(f"{lab}: panel {a[lab]} became {b[lab]}")
    for k in SYMPTOM_KEYS:
        if rep_a["symptoms"][k] != rep_b["symptoms"][k]:
            reasons.append(f"{k}: read {rep_a['symptoms'][k]} from the note and {rep_b['symptoms'][k]} from the message")
    return reasons or ["probability differs with the same labs and readings"]


def check(dataset, directory: Path = MODEL_DIR, records=None) -> dict[str, Any]:
    model = risk_model.load(directory)
    records = records if records is not None else data.dev_records(dataset)
    rows, exceptions = 0, []
    for r in records:
        view = input_view(r)
        message = render_message(view)
        text_view = intake.view_from_text(message, r.patient_id)
        a, b = model.report(view), model.report(text_view)
        rows += 1
        diff = abs(a["probability"] - b["probability"])
        if diff > TOLERANCE:
            exceptions.append({"patient_id": r.patient_id, "structured": a["probability"], "text": b["probability"],
                               "difference": diff, "reasons": _why(view, text_view, a, b)})
    within = rows - len(exceptions)
    return {"records": rows, "within_tolerance": within, "share": within / rows, "tolerance": TOLERANCE,
            "min_share": MIN_SHARE, "meets_requirement": within / rows >= MIN_SHARE, "exceptions": exceptions}


def render(result: dict[str, Any]) -> str:
    L = ["# Text path against the structured path (dev)", "", "ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.", "",
         f"{result['within_tolerance']} of {result['records']} dev records ({result['share']:.1%}) give a probability within "
         f"{result['tolerance']} through render, intake and the classifier. Required: at least {result['min_share']:.0%}; "
         f"{'met' if result['meets_requirement'] else 'NOT met'}.", ""]
    if result["exceptions"]:
        L += ["## Records outside the tolerance", "", "| Patient | Structured | Text | Difference | Why |", "|---|---|---|---|---|"]
        for e in result["exceptions"]:
            L.append(f"| {e['patient_id']} | {e['structured']:.4f} | {e['text']:.4f} | {e['difference']:.4f} | {'; '.join(e['reasons'])} |")
        L.append("")
    return "\n".join(L)
