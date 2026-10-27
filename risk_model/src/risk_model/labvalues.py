"""Lab values a note states, read by pattern: the lab (by name or abbreviation), the number and the unit as written."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .labs import LABS, Lab

# A number may carry a decimal comma ("0,98") or a thousands separator ("1,040"); see ``resolve``. It must end cleanly, and a
# range such as "70-130" is not a single reading, so it is left out.
_NUMBER = r"(-?\d+(?:[.,]\d+)*)(?!\d|[.,]\d|-\d)"
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
_THOUSANDS = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
_DECIMAL_COMMA = re.compile(r"^-?\d+,\d+$")
_PLAIN = re.compile(r"^-?\d+(?:\.\d+)?$")


def resolve(token: str, lab: Lab, unit: str | None) -> tuple[float, int] | None:
    """The value and the number of decimals a written number means, or None if it cannot be read with confidence.

    A comma is a decimal comma ("0,98" is 0.98) or a thousands separator ("1,040" is 1040), and "1,040" could be either. The
    lab's plausible range decides: if exactly one reading is a value a patient could have, that is it; if both are, the
    number is ambiguous and is left out; if neither is, the number is an impossible value whatever it means, and it is passed
    on as the thousands reading so that the data-quality check flags it. A number with both separators ("1.234,5") takes the
    last one as the decimal point.
    """
    if _PLAIN.match(token):
        return float(token), len(token.split(".")[1]) if "." in token else 0
    if "," in token and "." in token:
        point = "," if token.rfind(",") > token.rfind(".") else "."
        whole, _, frac = token.rpartition(point)
        digits = whole.replace(",", "").replace(".", "")
        return (float(f"{digits}.{frac}"), len(frac)) if digits.lstrip("-").isdigit() else None
    options: list[tuple[float, int]] = []
    if _THOUSANDS.match(token):
        options.append((float(token.replace(",", "")), 0))
    if _DECIMAL_COMMA.match(token):
        options.append((float(token.replace(",", ".")), len(token.split(",")[1])))
    if not options:
        return None
    if len(options) == 1:
        return options[0]
    plausible = [o for o in options if lab.plaus_lo <= lab.to_usual(o[0], unit) <= lab.plaus_hi]
    if len(plausible) == 1:
        return plausible[0]
    return options[0] if not plausible else None  # neither fits: an impossible value, passed on; both fit: ambiguous


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
            resolved = resolve(number, lab, unit)
            if resolved is None:
                continue
            found.append((m.start(), Stated(lab.key, resolved[0], unit, resolved[1])))
    return [s for _, s in sorted(found, key=lambda t: t[0])]


def usual_value(lab: Lab, stated: Stated) -> float:
    return lab.to_usual(stated.value, stated.unit)


def agrees(lab: Lab, stated: Stated, panel_value: float) -> bool:
    """Whether the stated value matches the panel after converting to the usual unit: within 1%, or within the rounding
    of the digits the note gives, whichever is looser."""
    scale = lab.factor if (stated.unit == lab.alt_unit and lab.factor) else 1.0
    tolerance = max(0.01 * abs(panel_value), 0.5 * 10 ** (-stated.decimals) / scale)
    return abs(usual_value(lab, stated) - panel_value) <= tolerance
