"""Prompts for LLM-written notes, built from the note plan ONLY.

The builder takes a plan and nothing else, so the label, true probability, true symptom flags and the
scoring rule cannot reach the model. Prompt text lives in versioned files next to this module; the text
hash is part of the cache key, so editing a prompt invalidates exactly its cached notes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..traits import trait_lines
from ..labs import LAB_BY_KEY, SYMPTOM_BY_KEY
from ..render import ADDENDUM
from ..schema import NotePlanV2, PlanLabV2, PlanSymptomV2

PROMPT_DIR = Path(__file__).with_name("prompts")
ADDENDUM_MARKER = "[[ADDENDUM]]"

_STATED_WORD = {"present": "present", "hedged": "possible (uncertain)", "negated": "denied"}


class MarkerError(ValueError):
    """The model did not keep (or wrongly added) the injection marker line."""


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    text_hash: str  # hash of the prompt files used, for the cache key


def _load(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text().strip()


def system_prompt(setting: str) -> str:
    return f"{_load('common')}\n\n{_load(setting)}"


_exemplar_cache: dict[str, list[str]] = {}
EXEMPLAR_INTRO = (
    "Examples of how real notes of this kind read. They are about other patients: do not reuse their wording, "
    "findings, numbers or structure beyond what the style lines say. Match their register and rhythm only."
)


def exemplars(setting: str) -> list[str]:
    """The setting's exemplar notes (original fictional text, six per setting)."""
    if setting not in _exemplar_cache:
        text = (PROMPT_DIR / "exemplars" / f"{setting}.txt").read_text()
        _exemplar_cache[setting] = [part.strip() for part in text.split("\n=====\n") if part.strip()]
    return _exemplar_cache[setting]


def prompt_text_hash(setting: str) -> str:
    blob = system_prompt(setting) + "\n" + "\n=====\n".join(exemplars(setting))
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _fmt_range(lo: float, hi: float, unit: str) -> str:
    return f"reference {lo:g}-{hi:g} {unit}"


def display_value(value: float) -> str:
    """The value as a lab report would print it: three significant figures. That is within 0.5% of the plan value,
    inside the 1% the checks allow, and avoids tells such as 4.199 or 30.93."""
    return f"{float(f'{value:.3g}'):g}"


def _lab_line(lab: PlanLabV2) -> str:
    d = LAB_BY_KEY[lab.lab]
    parts = [f"- {d.name} (abbreviation {d.abbr}): {display_value(lab.value)} {lab.unit}"]
    if lab.flag:
        parts.append(f"flag {lab.flag}")
    if lab.ref_range:
        parts.append(_fmt_range(lab.ref_range[0], lab.ref_range[1], lab.unit))
    return ", ".join(parts)


def _symptom_line(s: PlanSymptomV2) -> str:
    phrases = " | ".join(f'"{p}"' for p in s.phrases)
    line = f"- {_STATED_WORD[s.stated]}: allowed phrases {phrases}"
    if s.quote:
        line += "; include a short quote from the patient in their own words"
    return line


def build_prompt(plan: NotePlanV2) -> Prompt:
    labs = "\n".join(_lab_line(l) for l in plan.labs)
    labs_block = (
        f"Lab results to state (copy the values and units exactly; state no other lab results):\n{labs}"
        if plan.labs else "State no lab results at all."
    )
    symptoms = "\n".join(_symptom_line(s) for s in plan.symptoms)
    symptoms_block = (
        f"Symptom findings to state (mention no other symptoms):\n{symptoms}"
        if plan.symptoms else "State no symptom findings at all."
    )
    parts = [f"Documentation setting: {plan.style}", labs_block, symptoms_block]
    style_lines = trait_lines(plan.style, plan.traits)
    if style_lines:
        parts.append("Style for this note (these decide the layout and habits of this note; follow them):\n"
                     + "\n".join(f"- {line}" for line in style_lines))
    if plan.exemplars:
        pool = exemplars(plan.style)
        shown = "\n\n".join(f"Example {n}:\n\"\"\"\n{pool[i]}\n\"\"\"" for n, i in enumerate(plan.exemplars, 1))
        parts.append(f"{EXEMPLAR_INTRO}\n\n{shown}")
    if plan.injection is not None:
        parts.append(f"End the note with the exact line {ADDENDUM_MARKER} on its own line.")
    return Prompt(
        system=system_prompt(plan.style),
        user="\n\n".join(parts),
        text_hash=prompt_text_hash(plan.style),
    )


def finalize_note(text: str, plan: NotePlanV2) -> str:
    """Replace the marker with the catalog injection text, verbatim. The model never writes injections."""
    body = text.strip()
    count = body.count(ADDENDUM_MARKER)
    if plan.injection is None:
        if count:
            raise MarkerError("the note contains the injection marker but the plan has no injection")
        return body
    if count != 1 or not body.endswith(ADDENDUM_MARKER):
        raise MarkerError("the note must end with the injection marker line exactly once")
    head = body[: -len(ADDENDUM_MARKER)].rstrip()
    return f"{head}\n{ADDENDUM} {plan.injection.text}"
