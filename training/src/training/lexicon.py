"""The symptom lexicon: word-start terms (regular-expression fragments) whose presence in a note is a mention of that symptom.

``BASE`` is the generator's own vocabulary (``data_gen.labs`` stems and phrase bank). ``ADDED`` holds terms found by
reading the train notes in which a stated symptom had no mention under ``BASE`` (see ``coverage``). A term only starts a
mention; whether the mention says present, possible or absent, or is not about the patient at all, is decided later by
the mention classifier. Written to ``data/symptom_lexicon.json`` by ``training lexicon``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from data_gen.labs import SYMPTOM_KEYS
from evals.graders import true_symptom_readings

LEXICON_PATH = Path(__file__).resolve().parents[2] / "data" / "symptom_lexicon.json"

BASE: dict[str, tuple[str, ...]] = {
    "tremor": ("tremor", "tremul", "trembl", "shak", r"hands?\s+(?:\w+\s+){0,2}steady", r"steady\s+hands?", "steadiness"),
    "fatigue": ("fatigue", "tired", "exhaust", "low energy", "energy", "wiped"),
    "photophobia": ("photophob", "light sensitiv", "sensitive to bright light", "sensitive to light", "bright light", "squint"),
    "joint_stiffness": ("stiff",),
    "dizziness": ("dizz", "lighthead", "woozy", "woozi"),
}
# "tires easily" (fatigue) and "light bothers the eyes" (photophobia) are in the generator's phrase bank but not in its stems.
ADDED: dict[str, tuple[str, ...]] = {
    "fatigue": ("tires", "tire easily"),
    "photophobia": ("light bothers", "bothered by bright"),
}


def build() -> dict[str, list[str]]:
    out = {}
    for key in SYMPTOM_KEYS:
        terms = {t.lower().strip() for t in (*BASE.get(key, ()), *ADDED.get(key, ()))}
        out[key] = sorted(terms)
    return out


def pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(sorted(terms, key=len, reverse=True)) + ")")


def mentions_by_symptom(lexicon: dict[str, list[str]]) -> dict[str, re.Pattern[str]]:
    return {k: pattern(v) for k, v in lexicon.items()}


def coverage(records, lexicon: dict[str, list[str]]) -> dict[str, tuple[int, int]]:
    """Per symptom: (stated symptoms whose note has at least one mention, stated symptoms)."""
    pats = mentions_by_symptom(lexicon)
    seen = {k: [0, 0] for k in SYMPTOM_KEYS}
    for r in records:
        note = r.input.note.lower()
        for k, reading in true_symptom_readings(r).items():
            if reading == "not_mentioned":
                continue
            seen[k][1] += 1
            seen[k][0] += bool(pats[k].search(note))
    return {k: (a, b) for k, (a, b) in seen.items()}


def write(path: Path = LEXICON_PATH) -> dict[str, list[str]]:
    lex = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lex, indent=2, sort_keys=True) + "\n")
    return lex


def load(path: Path = LEXICON_PATH) -> dict[str, list[str]]:
    return json.loads(path.read_text())
