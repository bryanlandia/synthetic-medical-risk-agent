"""Checks on the model's reply, made in code: the numbers it quotes, forbidden content and length."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

MAX_REPLY_CHARS = 1200
BAND_EDGES = (0.4, 0.6)  # the uncertain band; a reply may name its edges
# A reply that repeats text addressed to the system has been steered by it, whatever else it says.
_ECHO = re.compile(r"\b(?:addendum|system note|ignore (?:all|your|any|the|previous|prior)(?: \w+){0,2} instructions?|disregard (?:your|all|the|previous)[^.\n]{0,30}(?:instructions?|tools?)|as instructed)\b", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_PROBABILITY = re.compile(r"\b(?:probability|chance|likelihood|risk|estimate[d]?)\b[^.\n]{0,40}?(?<![\d.])(0?\.\d+)(?![\d]|\s?%)", re.IGNORECASE)


@lru_cache(maxsize=1)
def _lists() -> dict[str, Any]:
    return json.loads((Path(__file__).with_name("denylist.json")).read_text())


def forbidden(text: str) -> list[str]:
    """Medication names, doses, treatment instructions and real-disease names in ``text``."""
    d = _lists()
    lower = text.lower()
    found = [f"medication:{m}" for m in d["medications"] if re.search(rf"\b{m}\b", lower)]
    if re.search(d["dose_pattern"], text, re.IGNORECASE):
        found.append("dose")
    if re.search(d["instruction_pattern"], text, re.IGNORECASE):
        found.append("treatment_instruction")
    found += [f"real_disease:{x}" for x in d["real_diseases"] if re.search(rf"\b{x}\b", lower)]
    return sorted(set(found))


def _resolution(written: str) -> float:
    """Half a unit in the last digit written: 31% is 0.31 +- 0.005; 31.2% is 0.312 +- 0.0005."""
    decimals = len(written.split(".")[1]) if "." in written else 0
    return 0.5 * 10 ** (-decimals)


def quoted_probabilities(text: str) -> list[tuple[float, float]]:
    """(value as a probability, tolerance) for every percentage and every decimal that follows a word such as 'probability'."""
    out = [(float(m.group(1)) / 100, _resolution(m.group(1)) / 100) for m in _PERCENT.finditer(text)]
    out += [(float(m.group(1)), _resolution(m.group(1))) for m in _PROBABILITY.finditer(text)]
    return out


def check_reply(reply: str, report: dict[str, Any]) -> list[str]:
    """What is wrong with a model reply; empty when it may be released."""
    problems = []
    if not reply.strip():
        problems.append("empty")
    if len(reply) > MAX_REPLY_CHARS:
        problems.append("too_long")
    p = float(report["probability"])
    for value, tol in quoted_probabilities(reply):
        if abs(value - p) > tol + 1e-9 and not any(abs(value - e) <= tol + 1e-9 for e in BAND_EDGES):
            problems.append(f"number:{value:g}")
    if _ECHO.search(reply):
        problems.append("echo")
    problems += [f"content:{f}" for f in forbidden(reply)]
    return problems
