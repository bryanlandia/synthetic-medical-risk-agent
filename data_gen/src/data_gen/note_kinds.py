"""What kind of documentation a note is, in words a rater should know before judging it.

A rater (a clinician or the LLM reviewer) is told the kind so that it judges a note against what that kind normally
looks like: an AI-scribe draft is expected to be even-toned and structured, an EHR template is expected to be tidy,
a quick shorthand note is not. Naming the kind is not naming the answer: the plan, the symptom readings and the
record identity stay in the key. The old template-fixture controls are described as a plain clinician-written note,
so they are judged by the standard they are meant to fail.
"""

from __future__ import annotations

NOTE_KINDS: dict[str, dict[str, str]] = {
    "shorthand": {
        "label": "Quick shorthand note",
        "expect": ("A rushed note in clinician shorthand: abbreviations and sentence fragments are normal, and the style "
                   "differs from clinician to clinician."),
    },
    "ehr_template": {
        "label": "EHR template note",
        "expect": ("Typed into a structured electronic-health-record template: labelled sections, tidy lists of results "
                   "and stock lines are expected. Judge whether it reads like a template a real clinician filled in."),
    },
    "ai_scribe": {
        "label": "AI-scribe draft",
        "expect": ("Drafted by an ambient AI scribe from the recorded visit conversation: structured, formal, "
                   "third-person, even-toned and somewhat wordy text is what such tools produce, so mechanical-sounding "
                   "or tidy prose is NOT a reason to reject it. Judge whether it reads like real scribe output, not "
                   "like a human's terse note."),
    },
    "copy_forward": {
        "label": "Copy-forward progress note",
        "expect": ("Built from the previous visit's note with some lines updated: stock reviewed-and-unchanged lines, "
                   "carried-over text and uneven tidiness are expected."),
    },
    "control": {
        "label": "Clinician-written visit note",
        "expect": "A visit note written by a clinician, with no particular template implied.",
    },
}


def kind_for(setting: str) -> dict[str, str]:
    return dict(NOTE_KINDS[setting])
