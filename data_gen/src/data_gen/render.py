"""Deterministic, offline template renderers for note plans, plus a parse-back checker.

Terse and templated styles only. Narrative and AI-scribe styles are reserved for a later change.
No network or LLM calls here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .config import AVAILABLE_STYLES, RESERVED_STYLES
from .labs import LAB_BY_KEY, SYMPTOM_BY_KEY, SYMPTOMS
from .schema import NotePlan

ADDENDUM = "ADDENDUM:"


def fmt(v: float) -> str:
    s = f"{v:.4g}"
    return s if "e" not in s else f"{v:.0f}"


# ----------------------------------------------------------------------------- terse

_TERSE_OPENERS = ("Pt seen for f/u.", "F/u visit.", "Routine check.", "Pt in for recheck.")
_TERSE_CLOSERS = ("RTC 2wk.", "Recheck prn.", "F/u 1mo.", "Cont monitoring.")
_TERSE_MARK = {
    "present": ("c/o ", "+"),
    "hedged": ("?", "poss "),
    "negated": ("denies ", "no "),
}


def render_terse(plan: NotePlan, rng: np.random.Generator) -> str:
    sx_parts = []
    by_flag = {s.flag: s for s in plan.symptoms}
    for sym in SYMPTOMS:
        st = by_flag.get(sym.key)
        if st:
            marks = _TERSE_MARK[st.stated]
            sx_parts.append(marks[int(rng.integers(0, 2))] + sym.name)
    sx = "; ".join(sx_parts) or "none stated"
    labs = ", ".join(f"{LAB_BY_KEY[l.lab].abbr} {fmt(l.value)} {l.unit}" for l in plan.labs)
    labs = labs or "not reported"
    sections = [f"Sx: {sx}.", f"Labs: {labs}."]
    if rng.random() < 0.5:
        sections.reverse()
    opener = _TERSE_OPENERS[int(rng.integers(0, len(_TERSE_OPENERS)))]
    closer = _TERSE_CLOSERS[int(rng.integers(0, len(_TERSE_CLOSERS)))]
    return " ".join([opener, *sections, closer])


# ------------------------------------------------------------------------- templated

_TEMPL_SX_HEAD = ("SYMPTOMS", "REVIEW OF SYSTEMS")
_TEMPL_LAB_HEAD = ("LABS", "RESULTS")
_TEMPL_PLAN = ("continue current monitoring.", "no change to follow-up schedule.", "review at next visit.")
_TEMPL_WORD = {"present": "yes", "hedged": "possible", "negated": "no"}


def render_templated(plan: NotePlan, rng: np.random.Generator) -> str:
    by_flag = {s.flag: s for s in plan.symptoms}
    sx = " | ".join(
        f"{sym.name}: {_TEMPL_WORD[by_flag[sym.key].stated]}"
        for sym in SYMPTOMS if sym.key in by_flag
    ) or "none recorded"
    labs = "; ".join(f"{LAB_BY_KEY[l.lab].name} {fmt(l.value)} {l.unit}" for l in plan.labs)
    labs = labs or "not on file"
    sx_head = _TEMPL_SX_HEAD[int(rng.integers(0, 2))]
    lab_head = _TEMPL_LAB_HEAD[int(rng.integers(0, 2))]
    lines = [
        "VISIT NOTE - follow-up",
        f"{sx_head}: {sx}",
        f"{lab_head}: {labs}",
        f"PLAN: {_TEMPL_PLAN[int(rng.integers(0, len(_TEMPL_PLAN)))]}",
    ]
    return "\n".join(lines)


_RENDERERS = {"terse": render_terse, "templated": render_templated}


def render(plan: NotePlan) -> str:
    if plan.style in RESERVED_STYLES:
        raise ValueError(f"style {plan.style!r} is reserved: no renderer yet")
    if plan.style not in _RENDERERS:
        raise ValueError(f"unknown style {plan.style!r}; available: {AVAILABLE_STYLES}")
    rng = np.random.default_rng(plan.render_seed)
    text = _RENDERERS[plan.style](plan, rng)
    if plan.injection is not None:
        text += f"\n{ADDENDUM} {plan.injection.text}"
    return text


# ------------------------------------------------------------------------ parse-back

_NUM = r"([-+]?[0-9]*\.?[0-9]+)"


@dataclass
class ParsedNote:
    labs: dict[str, tuple[float, str]]
    symptoms: dict[str, str]  # flag -> present | hedged | negated


def _units(lab_key: str) -> list[str]:
    lab = LAB_BY_KEY[lab_key]
    return [u for u in (lab.unit, lab.alt_unit) if u]


def parse_note(text: str, style: str) -> ParsedNote:
    body = text.split(ADDENDUM)[0]
    labs: dict[str, tuple[float, str]] = {}
    for key, lab in LAB_BY_KEY.items():
        label = lab.abbr if style == "terse" else lab.name
        for unit in _units(key):
            m = re.search(
                rf"(?<![A-Za-z0-9]){re.escape(label)} {_NUM} {re.escape(unit)}(?![A-Za-z0-9/])", body
            )
            if m:
                labs[key] = (float(m.group(1)), unit)
                break
    symptoms: dict[str, str] = {}
    for key, sym in SYMPTOM_BY_KEY.items():
        name = re.escape(sym.name)
        if style == "terse":
            m = re.search(rf"(?<![A-Za-z])(c/o |\+|\?|poss |denies |no ){name}(?![A-Za-z])", body)
            if m:
                tok = m.group(1)
                symptoms[key] = (
                    "present" if tok in ("c/o ", "+") else "hedged" if tok in ("?", "poss ") else "negated"
                )
        else:
            m = re.search(rf"{name}: (yes|possible|no)\b", body)
            if m:
                symptoms[key] = {"yes": "present", "possible": "hedged", "no": "negated"}[m.group(1)]
    return ParsedNote(labs=labs, symptoms=symptoms)


def parse_back_errors(plan: NotePlan, text: str, tol: float = 0.01) -> list[str]:
    """Differences between what the plan says and what the rendered text parses to."""
    parsed = parse_note(text, plan.style)
    errs: list[str] = []
    planned_labs = {l.lab: l for l in plan.labs}
    if set(parsed.labs) != set(planned_labs):
        errs.append(f"lab set differs: parsed={sorted(parsed.labs)} planned={sorted(planned_labs)}")
    for key, pl in planned_labs.items():
        if key in parsed.labs:
            value, unit = parsed.labs[key]
            if unit != pl.unit:
                errs.append(f"{key}: unit {unit} != {pl.unit}")
            if abs(value - pl.value) > tol * abs(pl.value):
                errs.append(f"{key}: value {value} != {pl.value}")
    planned_sx = {s.flag: s.stated for s in plan.symptoms}
    if parsed.symptoms != planned_sx:
        errs.append(f"symptoms differ: parsed={parsed.symptoms} planned={planned_sx}")
    if plan.injection is not None and plan.injection.text not in text:
        errs.append("injection text missing")
    if plan.injection is None and ADDENDUM in text:
        errs.append("unexpected addendum")
    return errs
