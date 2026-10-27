"""The words the service itself writes: fixed declines, the templated summary, and the disclaimer added by code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import guard

DISCLAIMER = "This is not medical advice. All data is synthetic and the disease is fictional."
NOTICE = "Everything here is a demonstration with invented data about a fictional syndrome."
REASONS = ("out_of_scope", "treatment_request", "real_disease", "phi", "other")

DECLINES = {
    "treatment_request": "I can't advise on treatment. I only estimate a probability for a fictional syndrome from fictional labs and a note. " + DISCLAIMER,
    "real_disease": "I only work with the fictional Velorin-Kessler syndrome, not real conditions or real people. " + DISCLAIMER,
    "phi": "Please don't paste personal or identifying details. Use invented labs and an invented note. " + DISCLAIMER,
    "out_of_scope": "I can only estimate a risk probability for the fictional Velorin-Kessler syndrome from labs and a clinical note. Paste some invented labs and a note to try it. " + DISCLAIMER,
    "other": "I can't help with that here. I estimate a risk probability for a fictional syndrome from invented labs and a note. " + DISCLAIMER,
}


@dataclass(frozen=True)
class Reply:
    text: str
    source: str  # "model" or "template"


def decline_text(reason: str | None) -> str:
    return DECLINES[reason if reason in DECLINES else "out_of_scope"]


def _readings(symptoms: dict[str, str]) -> str:
    names = {"tremor": "tremor", "fatigue": "fatigue", "photophobia": "light sensitivity", "joint_stiffness": "joint stiffness",
             "dizziness": "dizziness"}
    seen = [f"{names[k]} {v}" for k, v in symptoms.items() if v != "not_mentioned"]
    return "; ".join(seen) if seen else "none mentioned"


def template_reply(report: dict[str, Any]) -> str:
    """A summary written from the report alone, so it matches the report by construction."""
    p = report["probability"]
    parts = [f"Estimated probability of the fictional syndrome: {p:.0%}."]
    if report["uncertain"]:
        parts.append("That is in the uncertain band, so the findings point both ways.")
    labs = ", ".join(f"{u['lab'].replace('_', ' ')} {u['value']:g} {u['unit']}".strip() for u in report["labs_used"])
    parts.append(f"Labs read from your message: {labs or 'none'}.")
    parts.append(f"Symptoms read from your note: {_readings(report['symptoms'])}.")
    warned = sorted({f"{w['type'].replace('_', ' ')}{' (' + w['lab'].replace('_', ' ') + ')' if w['lab'] else ''}" for w in report["data_quality"]})
    if warned:
        parts.append("Data notes: " + ", ".join(warned) + ".")
    drivers = " ".join(e for e in report["evidence"][:-1])
    if drivers:
        parts.append("What drove it: " + drivers)
    text = " ".join(parts)
    return text if len(text) <= guard.MAX_REPLY_CHARS else text[: guard.MAX_REPLY_CHARS - 1].rstrip() + "…"


def finalize_scored(report: dict[str, Any], model_reply: str | None) -> Reply:
    """The model's reply if it passes the checks, else the template; the disclaimer and notice are added by code."""
    if model_reply is not None and not guard.check_reply(model_reply, report):
        body, source = model_reply.strip(), "model"
    else:
        body, source = template_reply(report), "template"
    return Reply(f"{body}\n\n{DISCLAIMER} {NOTICE}", source)


def finalize_declined(reason: str | None) -> Reply:
    return Reply(decline_text(reason), "template")
