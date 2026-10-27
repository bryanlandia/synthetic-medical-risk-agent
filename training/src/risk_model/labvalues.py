"""Lab values a note states, read by pattern: the lab (by name or abbreviation), the number and the unit as written."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .labs import LABS, Lab

_NUMBER = r"(-?\d+(?:\.\d+)?)"
_CONNECTOR = r"(?:\s*[:=]\s*|\s*,\s*|\s+was reviewed with the patient and was\s+|\s+(?:(?:level|result|value)\s+)?(?:of|at|was|is)\s+|\s+(?:(?:level|result|value)\s+)?)"
_UNIT = r"(?:\s*([a-z0-9^/]+))?"


@dataclass(frozen=True)
class Stated:
    lab: str
    value: float
    unit: str | None  # as written, or None when the note gives none
    decimals: int  # digits after the point as written: the resolution of the stated value


def _pattern(lab: Lab) -> re.Pattern[str]:
    name = re.escape(lab.name.lower())
    abbr = re.escape(lab.abbr.lower())
    return re.compile(rf"\b(?:{name}(?:\s*\({abbr}\))?|{abbr}(?:\s*\({name}\))?)(?:{_CONNECTOR}){_NUMBER}{_UNIT}")


_PATTERNS = {lab.key: _pattern(lab) for lab in LABS}


def read(note: str) -> list[Stated]:
    """Every (lab, value, unit) the note states, in note order. A form it cannot read with confidence is left out."""
    text = note.lower()
    found: list[tuple[int, Stated]] = []
    for lab in LABS:
        known = {u.lower() for u in (lab.unit, lab.alt_unit) if u}
        for m in _PATTERNS[lab.key].finditer(text):
            number, written = m.group(1), m.group(2)
            unit = None
            if written and written in known:
                unit = lab.unit if written == lab.unit.lower() else lab.alt_unit
            decimals = len(number.split(".")[1]) if "." in number else 0
            found.append((m.start(), Stated(lab.key, float(number), unit, decimals)))
    return [s for _, s in sorted(found, key=lambda t: t[0])]


def usual_value(lab: Lab, stated: Stated) -> float:
    return lab.to_usual(stated.value, stated.unit)


def agrees(lab: Lab, stated: Stated, panel_value: float) -> bool:
    """Whether the stated value matches the panel after converting to the usual unit: within 1%, or within the rounding
    of the digits the note gives, whichever is looser."""
    scale = lab.factor if (stated.unit == lab.alt_unit and lab.factor) else 1.0
    tolerance = max(0.01 * abs(panel_value), 0.5 * 10 ** (-stated.decimals) / scale)
    return abs(usual_value(lab, stated) - panel_value) <= tolerance
