"""A code-only check of what a message is for: score it, or decline it with a reason from the report contract's closed set.

The chat agent leaves this choice to its model, and the scripted test model uses these rules as what a sensible model would do.
The packet endpoint has no routing model, so it applies the same rules in code before anything is scored or paid for.
"""

from __future__ import annotations

import re

from risk_model import labvalues

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b(?:dob|date of birth)\b", re.IGNORECASE)
_TREATMENT = re.compile(r"\b(?:what|which)\b[^.?\n]{0,30}\b(?:medication|medicine|drug|dose|dosage|pill)s?\b|\bshould (?:i|we|he|she|they)\b[^.?\n]{0,30}"
                        r"\b(?:take|give|start|stop|prescribe)\b|\bprescribe\b|\bhow (?:do|can|should) (?:i|we)\b[^.?\n]{0,20}\btreat", re.IGNORECASE)
_REAL = re.compile(r"\b(?:diabetes|cancer|hypertension|covid|influenza|asthma|stroke|alzheimer|parkinson)\b", re.IGNORECASE)
_SYMPTOM = re.compile(r"tremor|shak|fatigue|tired|dizz|lighthead|light sensitiv|photophob|stiff|woozy", re.IGNORECASE)


def decide(message: str) -> tuple[str, str | None]:
    """('score', None) or ('decline', reason): what a sensible model would do."""
    if _SSN.search(message):
        return "decline", "phi"
    if _TREATMENT.search(message):
        return "decline", "treatment_request"
    has_payload = bool(labvalues.read(message)) or bool(_SYMPTOM.search(message))
    if _REAL.search(message) and not has_payload:
        return "decline", "real_disease"
    if has_payload:
        return "score", None
    return "decline", "out_of_scope"


NOTE_MARKER = re.compile(r"^Note:[ \t]*$", re.MULTILINE)


def decide_chart(message: str) -> tuple[str, str | None]:
    """The packet's check. A chart message has a "Labs:" part and a "Note:" part, and the note is data: words in it such as
    "prescribe" are not a request to this service. Personal identifiers are declined wherever they are; the treatment and
    real-disease rules read only the text outside the note. A message with no "Note:" section is checked whole."""
    marker = NOTE_MARKER.search(message)
    if marker is None:
        return decide(message)
    if _SSN.search(message):
        return "decline", "phi"
    head = message[: marker.start()]
    if _TREATMENT.search(head):
        return "decline", "treatment_request"
    has_payload = bool(labvalues.read(message)) or bool(_SYMPTOM.search(message))
    if _REAL.search(head) and not has_payload:
        return "decline", "real_disease"
    return ("score", None) if has_payload else ("decline", "out_of_scope")
