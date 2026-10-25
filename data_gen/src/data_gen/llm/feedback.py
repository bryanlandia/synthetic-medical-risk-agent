"""Tell the writer why its previous attempt was rejected, in plain words.

The model is nearly deterministic for an identical prompt, so a bare retry repeats the same mistake. Feedback
makes the retry a different, better-informed request. Only codes the writer can act on are explained.
"""

from __future__ import annotations

from ..labs import LAB_BY_KEY, SYMPTOM_BY_KEY, all_symptom_phrases
from ..schema import NotePlanV2
from .checks import _has_phrase

_EXPECT = {"present": "present", "possible": "possible", "absent": "denied (absent)", "not_mentioned": "not mentioned"}


def _symptom(key: str) -> str:
    return SYMPTOM_BY_KEY[key].name if key in SYMPTOM_BY_KEY else key


def _lab(key: str) -> str:
    return LAB_BY_KEY[key].name if key in LAB_BY_KEY else key


def explain(code: str, plan: NotePlanV2, text: str | None) -> str | None:
    kind, _, arg = code.partition(":")
    if kind == "symptom_repeated":
        used = [p for p in all_symptom_phrases(arg) if text and _has_phrase(text, p)]
        return (f"you described {_symptom(arg)} in several ways ({', '.join(repr(p) for p in used)}); "
                "mention it once, with a single wording")
    if kind == "phrase_missing":
        return f"{_symptom(arg)} was not mentioned in a recognisable way; state it once, plainly"
    if kind == "symptom_extra":
        return f"you mentioned {_symptom(arg)}, which is not listed; mention only the listed symptoms"
    if kind == "polarity":
        want = next((s.stated for s in plan.symptoms if s.flag == arg), None)
        word = {"present": "present", "hedged": "possible (uncertain)", "negated": "denied"}.get(want or "", "as listed")
        return f"{_symptom(arg)} did not read as {word}; make that unmistakable"
    if kind == "polarity_extra":
        return f"{_symptom(arg)} should not be mentioned"
    if kind in ("lab_wrong", "lab_missing", "lab_invented", "lab_unit", "lab_flag"):
        reason = {"lab_wrong": "has a value that differs from the list", "lab_missing": "is missing",
                  "lab_invented": "is not in the list and must not be mentioned",
                  "lab_unit": "is written in a different unit than listed", "lab_flag": "has a high/low flag that is "
                  "missing or wrong (flags only where listed)"}[kind]
        return f"{_lab(arg)} {reason}; copy the listed values, units and flags exactly"
    if kind == "meta_mention":
        return "you said something is fictional, synthetic, a study or test data; never mention that"
    if kind == "contradictory_phrasing":
        return 'you wrote "c/o denies" or similar; "c/o" is only for symptoms the patient has'
    if kind == "meta_commentary":
        return "you included drafts, corrections or comments about the rules; output only the final note"
    if kind == "exemplar_copied":
        return "you copied sentences from an example; write your own wording"
    if kind == "claim":
        return "you stated a diagnosis, risk, dose or treatment; state none"
    if kind == "identifier":
        return "you included an identifier-shaped string (number, phone, MRN); include none"
    if kind in ("truncated", "extractor_truncated"):
        return "the note was cut off; keep it short enough to finish"
    if kind == "setting_name":
        return "the note names its own kind (such as 'copy-forward' or 'EHR template'); never do that"
    return None


def feedback_text(codes: list[str], plan: NotePlanV2, text: str | None) -> str:
    """One paragraph for the next attempt's prompt, or an empty string if nothing is actionable."""
    reasons: list[str] = []
    for code in codes:
        reason = explain(code, plan, text)
        if reason and reason not in reasons:
            reasons.append(reason)
    if not reasons:
        return ""
    return ("Your previous attempt was rejected because " + "; ".join(reasons) +
            ". Write the note again, fixing this, and output only the note.")
