"""Offline checks on LLM-written notes. No network. Every check is plan-relative: it compares the note
with what the plan said to write (including any recorded noise), never with the ground truth, so tagged
noise such as a unit mismatch or a stale value is accepted exactly where the plan put it.

Each function returns a list of short failure codes (empty = pass), e.g. ``lab_wrong:serum_k17``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import LLM_SETTINGS
from ..labs import LAB_BY_KEY, LABS, SYMPTOM_BY_KEY, SYMPTOM_STEMS, LabDef, all_symptom_phrases
from ..render import ADDENDUM
from ..schema import NotePlanV2, PlanLabV2
from ..scan import scan_text

TOLERANCE = 0.01  # 1% relative, the same tolerance as the specs

# --- no diagnosis, risk or treatment -------------------------------------------------------------

DISEASE_TERMS = ("velorin-kessler",)
CLAIM_TERMS = ("diagnos", "risk", "probab", "prescrib", "dosage", "treatment", "therapy")
MEDICATION_DENYLIST = (
    "ibuprofen", "acetaminophen", "tylenol", "paracetamol", "aspirin", "naproxen", "advil", "motrin",
    "metformin", "lisinopril", "atorvastatin", "simvastatin", "amlodipine", "metoprolol", "propranolol",
    "primidone", "carvedilol", "losartan", "hydrochlorothiazide", "furosemide", "omeprazole",
    "levothyroxine", "gabapentin", "sertraline", "fluoxetine", "prednisone", "amoxicillin",
    "azithromycin", "insulin", "warfarin", "clopidogrel", "albuterol", "tramadol", "oxycodone",
    "hydrocodone", "morphine", "diazepam", "lorazepam", "alprazolam", "zolpidem", "cetirizine",
    "loratadine", "diphenhydramine", "benadryl", "ozempic", "semaglutide", "hydroxychloroquine",
    "methotrexate", "tamsulosin", "pantoprazole", "baclofen", "cyclobenzaprine",
)
# A quantity with a mass or volume unit that is not part of a lab unit such as mg/dL or g/dL.
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|ml|units?)\b(?![/\w])", re.IGNORECASE)


def body_without_addendum(text: str) -> str:
    """The note minus the catalog injection, which legitimately contains words such as 'risk'."""
    return text.split(ADDENDUM)[0]


def claims_scan(text: str) -> list[str]:
    body = body_without_addendum(text)
    lower = body.lower()
    found = [f"claim:{t}" for t in DISEASE_TERMS + CLAIM_TERMS if t in lower]
    if "%" in body:
        found.append("claim:percent")
    found += [f"claim:medication:{m}" for m in MEDICATION_DENYLIST if re.search(rf"\b{m}\b", lower)]
    if _DOSE.search(body):
        found.append("claim:dose")
    return found


# --- tolerant lab parsing --------------------------------------------------------------------------

_ALIASES = {"serum_k17": ("K-17",)}
_TIME_WORDS = re.compile(r"^\s*(?:weeks?|wks?|days?|months?|mos?|hours?|hrs?|years?|yrs?)\b", re.IGNORECASE)
_NUM = r"(?P<num>\d+(?:\.\d+)?)"
_GAP = r"(?P<gap>[^\d.;\n]{0,40}?)"
_FLAG = re.compile(r"(?<![/\w])(H|L|high|low)(?![\w/])")


def _norm_unit(s: str) -> str:
    return (
        s.lower().replace("µ", "u").replace("μ", "u").replace("×", "x").replace("⁹", "^9")
        .replace(" ", "")
    )


def _unit_forms(unit: str) -> set[str]:
    # Writers drop the leading x of 'x10^9/L'.
    return {unit, unit[1:]} if unit.startswith("x10") else {unit}


def _unit_matches(lab: LabDef, rest: str) -> tuple[str | None, int]:
    """Which of the lab's units starts rest (canonical or alternate), and how many characters."""
    text = rest.lstrip()
    skipped = len(rest) - len(text)
    candidates = [u for u in (lab.unit, lab.alt_unit) if u]
    for unit in sorted(candidates, key=len, reverse=True):
        for form in sorted(_unit_forms(unit), key=len, reverse=True):
            if _norm_unit(text[: len(form)]) == _norm_unit(form):
                return unit, skipped + len(form)
    return None, 0


@dataclass(frozen=True)
class LabMention:
    lab: str
    value: float
    unit: str | None
    end: int  # index just past the number and unit in the text
    start: int  # index of the number
    name_start: int = 0  # index where the lab's name or abbreviation begins


def _name_patterns(lab: LabDef) -> list[re.Pattern]:
    """Patterns for the lab's name, abbreviation and aliases. Each one also consumes any parenthesised
    restatement of the same lab, so 'Serum K-17 (K17): 3.9' reads 3.9 and not the 17 inside '(K17)'."""
    idents = [lab.name, lab.abbr, *_ALIASES.get(lab.key, ())]
    alternatives = "|".join(re.escape(i) for i in sorted(idents, key=len, reverse=True))
    restated = rf"(?:\s*[\(\[]\s*(?i:{alternatives})\s*[\)\]])*"
    names = [re.compile(re.escape(lab.name) + restated, re.IGNORECASE)]
    names += [re.compile(rf"\b{re.escape(a)}\b" + restated) for a in (lab.abbr, *_ALIASES.get(lab.key, ()))]
    return names


_PATTERNS = {lab.key: _name_patterns(lab) for lab in LABS}


def parse_lab_mentions(text: str) -> list[LabMention]:
    """Every lab-name mention followed (within a short gap) by a number that is not a time span."""
    seen: set[tuple[str, int]] = set()
    out: list[LabMention] = []
    for lab in LABS:
        for name in _PATTERNS[lab.key]:
            for m in name.finditer(text):
                tail = re.compile(_GAP + _NUM).match(text, m.end())
                if not tail:
                    continue
                num_end = tail.end("num")
                after = text[num_end:]
                if _TIME_WORDS.match(after) or after.lstrip().startswith("%"):
                    continue
                key = (lab.key, tail.start("num"))
                if key in seen:
                    continue
                seen.add(key)
                unit, used = _unit_matches(lab, after)
                out.append(LabMention(
                    lab.key, float(tail.group("num")), unit, num_end + used, tail.start("num"), m.start()))
    return sorted(out, key=lambda x: x.start)


def _within(value: float, expected: float) -> bool:
    return abs(value - expected) <= TOLERANCE * abs(expected)


def _flag_after(text: str, mention: LabMention, mentions: list[LabMention]) -> str | None:
    """The H/L flag written right after this lab's value, never one that belongs to the next lab."""
    stop = min([mention.end + 40, *[o.name_start for o in mentions if o.name_start >= mention.end]])
    tail = re.split(r"[\n;]", text[mention.end : stop])[0]
    m = _FLAG.search(tail)
    if not m:
        return None
    return "H" if m.group(1) in ("H", "high") else "L"


def lab_errors(text: str, plan: NotePlanV2) -> list[str]:
    body = body_without_addendum(text)
    mentions = parse_lab_mentions(body)
    planned: dict[str, PlanLabV2] = {l.lab: l for l in plan.labs}
    errs: list[str] = []
    for lab_key in {m.lab for m in mentions} - set(planned):
        errs.append(f"lab_invented:{lab_key}")
    for lab_key, pl in planned.items():
        mine = [m for m in mentions if m.lab == lab_key]
        good = []
        for m in mine:
            if (m.unit is not None and m.unit != pl.unit) or (m.unit is None and pl.unit != LAB_BY_KEY[lab_key].unit):
                errs.append(f"lab_unit:{lab_key}")  # noise integrity: the plan's unit must be the one written, and a
                # value in the unusual unit is never left without it (it would read as a wrong value)
            elif not _within(m.value, pl.value):
                errs.append(f"lab_wrong:{lab_key}")
            else:
                good.append(m)
        if not good:
            errs.append(f"lab_missing:{lab_key}")
            continue
        if pl.flag is not None or _plan_shows_flags(plan):
            errs += _flag_errors(body, good[0], pl, mentions)
    return sorted(set(errs))


def _plan_shows_flags(plan: NotePlanV2) -> bool:
    return any(l.ref_range is not None for l in plan.labs)


def _flag_errors(text: str, mention: LabMention, pl: PlanLabV2, mentions: list[LabMention]) -> list[str]:
    shown = _flag_after(text, mention, mentions)
    return [] if shown == pl.flag else [f"lab_flag:{pl.lab}"]


# --- symptom wording ----------------------------------------------------------------------------------

def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}", text, re.IGNORECASE) is not None


def phrase_errors(text: str, plan: NotePlanV2) -> list[str]:
    body = body_without_addendum(text)
    errs = [f"phrase_missing:{s.flag}" for s in plan.symptoms
            if not re.search(SYMPTOM_STEMS[s.flag], body, re.IGNORECASE)
            and not any(_has_phrase(body, p) for p in all_symptom_phrases(s.flag))]  # offered wording is only a hint
    planned = {s.flag for s in plan.symptoms}
    for key in SYMPTOM_BY_KEY:
        if key not in planned and any(_has_phrase(body, p) for p in all_symptom_phrases(key)):
            errs.append(f"symptom_extra:{key}")
    return errs


# --- everything that needs no network ---------------------------------------------------------------------

def reveals_setting(text: str) -> str | None:
    """The documentation setting's name, if the note says it (e.g. a header "EHR template"): the rating sheet is blind."""
    lowered = text.lower().replace("-", " ").replace("_", " ")
    return next((s for s in LLM_SETTINGS if s.replace("_", " ") in lowered), None)


_META = re.compile(r"\b(fictional|synthetic|simulated|test data|this study|study condition|made[- ]up)\b", re.I)
_COMMENTARY = re.compile(
    r"\b(wait,|hmm\b|let me\b|corrected note|final note|allowed phrases?|wording ideas?|style lines?|one phrase per)", re.I)
_CO_DENIES = re.compile(r"\bc/o\s+(denies|deny|no|neg|negative)\b", re.I)


def style_errors(text: str, plan: NotePlanV2) -> list[str]:
    """Tells that make a note read as machine-written, which a clinician reviewer rejects."""
    body = body_without_addendum(text)
    errs: list[str] = []
    if _META.search(body):
        errs.append("meta_mention")
    if _CO_DENIES.search(body):
        errs.append("contradictory_phrasing")
    for s in plan.symptoms:
        # Several wordings inside one sentence ("denies fatigue, feels not tired, no low energy"), or three or more
        # anywhere, read as padding. Two wordings in separate sentences ("Denies fatigue. Energy normal.") are normal.
        if any(len(_distinct_wordings(part, s.flag)) > 1 for part in re.split(r"(?<=[.!?])\s+|\n+", body)) \
                or len(_distinct_wordings(body, s.flag)) >= 3:
            errs.append(f"symptom_repeated:{s.flag}")
    if _COMMENTARY.search(body):
        errs.append("meta_commentary")
    return errs


def _distinct_wordings(text: str, flag: str) -> list[str]:
    used = [p for p in all_symptom_phrases(flag) if _has_phrase(text, p)]  # any polarity
    return [p for p in used if not any(p != q and p.lower() in q.lower() for q in used)]  # drop nested ones


def offline_errors(text: str, plan: NotePlanV2) -> list[str]:
    """All offline failure codes for a finalized note (marker already replaced by the injection text)."""
    errs: list[str] = []
    if not text.strip():
        return ["empty"]
    errs += claims_scan(text)
    errs += [f"identifier:{f}" for f in scan_text(body_without_addendum(text))]
    errs += lab_errors(text, plan)
    errs += phrase_errors(text, plan)
    errs += style_errors(text, plan)
    errs += exemplar_errors(text, plan)
    if reveals_setting(text):
        errs.append("setting_name")
    return errs


# --- copying the exemplars ---------------------------------------------------------------------------------------

EXEMPLAR_SHINGLE = 8  # words in a row that may not be taken from an exemplar note


_LAB_WORDS = {w for lab in LABS for w in re.findall(r"[a-z0-9']+", f"{lab.name} {lab.abbr}".lower())}


def _shingles(text: str, n: int = EXEMPLAR_SHINGLE) -> set[tuple[str, ...]]:
    """Runs of n plain words. Numbers and lab names break a run, so a results block that happens to be laid out like
    an exemplar's is not copying; only copied prose is."""
    out: set[tuple[str, ...]] = set()
    run: list[str] = []
    for w in re.findall(r"[a-z0-9']+", text.lower()):
        if any(ch.isdigit() for ch in w) or w in _LAB_WORDS:
            run = []
            continue
        run.append(w)
        if len(run) >= n:
            out.add(tuple(run[-n:]))
    return out


def exemplar_errors(text: str, plan: NotePlanV2) -> list[str]:
    """The note must not reproduce a run of eight words from any exemplar of its setting, except the stock lines
    the style traits ask for."""
    from ..traits import stock_lines
    from .prompts import exemplars

    body = body_without_addendum(text)
    for line in stock_lines(plan.style, plan.traits):
        body = re.sub(re.escape(line), " ", body, flags=re.IGNORECASE)
    mine = _shingles(body)
    if not mine:
        return []
    for example in exemplars(plan.style):
        if mine & _shingles(example):
            return ["exemplar_copied"]
    return []
