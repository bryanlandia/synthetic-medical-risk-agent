"""The packet's evidence summary: a verifier for a model's draft and the fixed-template summary used when it fails.

A draft is a list of sentences, each ``{"criterion", "status", "text", "cites"}``. Code, not the model, decides whether it is
shown. A draft is rejected as a whole (never repaired) when any sentence breaks a rule, so the fallback rate stays honest.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from . import policy
from .labs import LABS

MAX_SENTENCES = 12
MAX_TEXT_CHARS = 500  # a faithful sentence about C1 can quote three labs with their thresholds and ranges
SENTENCE_KEYS = {"criterion", "status", "text", "cites"}
STATUSES = ("met", "unmet", "unknown")

# Wording a packet must never use: a verdict on the request, urgency, a diagnosis or treatment, coaching the request,
# or text addressed to the system. A reply may not echo the note's instructions either.
BANNED = re.compile(
    r"\b(?:qualif\w*|eligib\w*|approv\w*|den(?:y|ied|ies|ial)|authori[sz]\w*|reimburs\w*|will be covered|"
    r"diagnos\w*|treat\w*|therap\w*|medicat\w*|prescri\w*|doses?|dosage|"
    r"urgen\w*|emergen\w*|immediate\w*|asap|critical|"
    r"should (?:not )?(?:be )?(?:scan\w*|image\w*|proceed)|must (?:be )?scan\w*|delay\w*|withh[eo]ld\w*|"
    r"(?:phrase|word|frame|rewrite|reword)\w*(?: \w+){0,3} (?:request|rationale|justification)|to (?:ensure|secure|improve) (?:approval|coverage)|"
    r"addendum|ignore (?:all|any|previous|prior)|instructions?)\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
_CRITERION_ID = re.compile(r"\bC[1-6]\b")
_STATUS_WORDS = ((re.compile(r"\bnot met\b|\bunmet\b", re.I), "unmet"), (re.compile(r"\bunknown\b", re.I), "unknown"),
                 (re.compile(r"(?<!not )\bmet\b", re.I), "met"))
_UNITS = sorted({u for lab in LABS for u in (lab.unit, lab.alt_unit) if u and u != "ratio"}, key=len, reverse=True)


def _numbers(text: str) -> set[float]:
    return {float(m) for m in _NUMBER.findall(_CRITERION_ID.sub(" ", text))}


def _unit_tokens(text: str) -> set[str]:
    lower = text.lower()
    return {u.lower() for u in _UNITS if re.search(rf"(?<![\w/]){re.escape(u.lower())}(?![\w/])", lower)}


def _lab_mentions(text: str) -> set[str]:
    lower = text.lower()
    out = set()
    for lab in LABS:
        if re.search(rf"\b{re.escape(lab.name.lower())}\b", lower) or re.search(rf"\b{re.escape(lab.abbr.lower())}\b", lower):
            out.add(lab.key)
    return out


def _well_formed(s: Any) -> bool:
    return (isinstance(s, dict) and set(s) == SENTENCE_KEYS and isinstance(s["text"], str)
            and isinstance(s["cites"], list) and all(isinstance(c, str) for c in s["cites"]))


def _wording_problems(text: str, extra_forbidden: Callable[[str], list[str]] | None) -> list[str]:
    out = [f"banned:{m.group(0).lower()}"] if (m := BANNED.search(text)) else []
    if extra_forbidden:
        out += [f"content:{f}" for f in extra_forbidden(text)]
    return out


def _sentence_problems(i: int, s: dict[str, Any], packet: dict[str, Any], extra_forbidden: Callable[[str], list[str]] | None) -> list[str]:
    table = {r["id"]: r for r in packet["criteria"]}
    evidence = {e["id"]: e for e in packet["evidence"]}
    text, cites, cid = s["text"], s["cites"], s["criterion"]
    if cid not in table:
        return [f"criterion:{i}"]
    problems = [f"too_long:{i}"] if len(text) > MAX_TEXT_CHARS else []
    status = table[cid]["status"]
    if s["status"] != status:
        problems.append(f"status:{cid}")
    if {st for pattern, st in _STATUS_WORDS if pattern.search(text)} - {status}:
        problems.append(f"status_text:{cid}")
    if not cites:
        problems.append(f"no_citation:{i}")
    problems += [f"bad_citation:{c}" for c in cites if c not in evidence]
    cited = " ".join(evidence[c]["text"] for c in cites if c in evidence)
    wording = policy.wording()[cid]
    problems += [f"number:{n:g}" for n in sorted(_numbers(text) - (_numbers(cited) | _numbers(wording)))]
    problems += [f"unit:{u}" for u in sorted(_unit_tokens(text) - _unit_tokens(cited + " " + wording))]
    problems += [f"lab:{k}" for k in sorted(_lab_mentions(text) - _lab_mentions(cited))]
    return problems + _wording_problems(text, extra_forbidden)


def verify(draft: Any, packet: dict[str, Any], extra_forbidden: Callable[[str], list[str]] | None = None) -> list[str]:
    """Reasons a draft may not be shown; empty when every sentence passes."""
    if not isinstance(draft, list) or not draft:
        return ["shape:not_a_list" if not isinstance(draft, list) else "shape:empty"]
    if len(draft) > MAX_SENTENCES:
        return ["shape:too_many"]
    problems: list[str] = []
    for i, s in enumerate(draft):
        problems += _sentence_problems(i, s, packet, extra_forbidden) if _well_formed(s) else [f"shape:{i}"]
    return sorted(set(problems))



def template_summary(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """One fixed-template sentence per criterion, built only from the table and its cited evidence."""
    evidence = {e["id"]: e for e in packet["evidence"]}
    out = []
    for row in packet["criteria"]:
        facts = "; ".join(evidence[c]["text"] for c in row["cites"])
        if row["status"] == "unknown":
            text = f"{row['id']} is unknown: the record does not settle it yet."
        else:
            text = f"{row['id']} is {row['status']}: {facts}."
        out.append({"criterion": row["id"], "status": row["status"], "text": text, "cites": list(row["cites"])})
    return out
