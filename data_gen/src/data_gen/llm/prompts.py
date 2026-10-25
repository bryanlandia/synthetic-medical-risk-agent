"""Prompts for LLM-written notes, built from the note plan ONLY.

The builder takes a plan and nothing else, so the label, true probability, true symptom flags and the
scoring rule cannot reach the model. Prompt text lives in versioned files next to this module; the text
hash is part of the cache key, so editing a prompt invalidates exactly its cached notes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

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


def prompt_text_hash(setting: str) -> str:
    return hashlib.sha256(system_prompt(setting).encode()).hexdigest()[:12]


def _fmt_range(lo: float, hi: float, unit: str) -> str:
    return f"reference {lo:g}-{hi:g} {unit}"


def _lab_line(lab: PlanLabV2) -> str:
    d = LAB_BY_KEY[lab.lab]
    parts = [f"- {d.name} (abbreviation {d.abbr}): {lab.value:g} {lab.unit}"]
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
        f"Lab results to state (use values and units exactly; state no other lab results):\n{labs}"
        if plan.labs else "State no lab results at all."
    )
    symptoms = "\n".join(_symptom_line(s) for s in plan.symptoms)
    symptoms_block = (
        f"Symptom findings to state (mention no other symptoms):\n{symptoms}"
        if plan.symptoms else "State no symptom findings at all."
    )
    parts = [f"Documentation setting: {plan.style}", labs_block, symptoms_block]
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
