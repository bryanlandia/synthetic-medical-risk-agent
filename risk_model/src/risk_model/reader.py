"""The note reader: symptom readings from a note, on CPU, with numpy and the standard library only.

A lexicon finds mentions of each symptom. A logistic classifier reads the clause around each mention and calls it
present, possible, absent, or none (a word that is not about the patient's symptom, such as "things have been steady").
A symptom with no mention that is not ``none`` is ``not_mentioned``. The same feature function is used to fit and to
predict, so the two cannot drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .labs import SYMPTOM_KEYS

MENTION_CLASSES = ("present", "possible", "absent", "none")
# A note counts as contradicting itself about a symptom only when one mention says present and another says absent and
# both are read with at least this confidence: a mention the classifier is unsure of is not evidence of a conflict.
CONFLICT_CONFIDENCE = 0.95
# A clause ends at a sentence mark, a line break, a semicolon, a colon, a comma, or a joining word.
_CLAUSE_SPLIT = re.compile(r"[\n.;:,]|\s+(?:and|but|while|though|although|however)\s+")
_TOKEN = re.compile(r"[a-z]+|\?")


@dataclass(frozen=True)
class Mention:
    symptom: str
    clause: str
    previous: str
    label: str
    confidence: float


@dataclass
class Reading:
    readings: dict[str, str]
    mentions: list[Mention] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)  # symptoms mentioned as present and as absent in one note


def clauses(text: str) -> list[tuple[int, int, str]]:
    """(start, end, text) of each non-empty clause of the lower-cased note."""
    out, pos = [], 0
    for m in _CLAUSE_SPLIT.finditer(text):
        if text[pos:m.start()].strip():
            out.append((pos, m.start(), text[pos:m.start()]))
        pos = m.end()
    if text[pos:].strip():
        out.append((pos, len(text), text[pos:]))
    return out


def tokens(clause: str) -> list[str]:
    return _TOKEN.findall(clause)


# Words that say how a symptom is stated, in general English and not taken from this data. Each group becomes one shared
# feature, so wording the classifier has not seen in training ("negative for tremor") still points the right way.
CUES: dict[str, frozenset[str]] = {
    "neg": frozenset({"no", "not", "none", "denies", "denied", "deny", "denying", "negative", "without", "never", "absent",
                      "nil", "free", "normal", "steady", "unremarkable", "neither", "nor", "isnt", "doesnt", "hasnt"}),
    "hedge": frozenset({"possible", "possibly", "maybe", "perhaps", "occasionally", "occasional", "sometimes", "mild",
                        "slight", "slightly", "unsure", "uncertain", "probable", "probably", "may", "might", "intermittent",
                        "intermittently", "questionable", "suspected", "somewhat", "?", "poss", "vague"}),
    "pos": frozenset({"positive", "reports", "reported", "reporting", "complains", "complaints", "endorses", "has",
                      "had", "having", "present", "noted", "notes", "describes", "described", "experiencing", "experiences",
                      "feels", "feeling", "with", "c/o", "co"}),
}


def cue_features(prefix: str, clause: str) -> set[str]:
    words = set(tokens(clause))
    return {f"{prefix}:{name}" for name, group in CUES.items() if words & group}


def mention_features(symptom: str, clause: str, previous: str, cues: bool = True) -> list[str]:
    """Binary feature names for one mention: the clause's words and word pairs, the previous clause's words, the clause's
    words tied to this symptom (so that "steady" can mean something for tremor and not for fatigue), and, with ``cues``,
    which kinds of cue word (negation, hedge, affirmation) the clause and the previous clause contain."""
    toks = tokens(clause)
    feats = {f"c:{t}" for t in toks}
    feats |= {f"b:{a}_{b}" for a, b in zip(toks, toks[1:])}
    feats |= {f"s:{symptom}|{t}" for t in toks}
    feats |= {f"p:{t}" for t in tokens(previous)}
    feats.add(f"n:{min(len(toks), 8)}")
    if cues:
        feats |= cue_features("cue", clause) | cue_features("pcue", previous)
    return sorted(feats)


def find_mentions(text: str, patterns: dict[str, re.Pattern[str]]) -> list[tuple[str, str, str]]:
    """(symptom, clause, previous clause) for every lexicon hit in the lower-cased note, in note order."""
    parts = clauses(text)
    out = []
    for i, (_, _, clause) in enumerate(parts):
        previous = parts[i - 1][2] if i else ""
        for symptom in SYMPTOM_KEYS:
            if patterns[symptom].search(clause):
                out.append((symptom, clause, previous))
    return out


class NoteReader:
    """Built from the exported dictionary (see ``training.reader_fit.export``)."""

    def __init__(self, spec: dict[str, Any]):
        self.lexicon: dict[str, list[str]] = spec["lexicon"]
        self.patterns = {
            k: re.compile(r"\b(?:" + "|".join(sorted(v, key=len, reverse=True)) + ")")
            for k, v in self.lexicon.items()}
        self.index: dict[str, int] = {f: i for i, f in enumerate(spec["features"])}
        self.weights = np.array(spec["weights"], dtype=float)  # classes x features
        self.intercept = np.array(spec["intercept"], dtype=float)
        self.rule: str = spec["conflict_rule"]
        self.cues: bool = spec.get("cues", True)
        assert tuple(spec["classes"]) == MENTION_CLASSES

    def probabilities(self, symptom: str, clause: str, previous: str) -> np.ndarray:
        cols = [self.index[f] for f in mention_features(symptom, clause, previous, self.cues) if f in self.index]
        logits = self.weights[:, cols].sum(axis=1) + self.intercept
        e = np.exp(logits - logits.max())
        return e / e.sum()

    def read(self, note: str) -> Reading:
        text = note.lower()
        found: dict[str, list[Mention]] = {k: [] for k in SYMPTOM_KEYS}
        mentions: list[Mention] = []
        for symptom, clause, previous in find_mentions(text, self.patterns):
            p = self.probabilities(symptom, clause, previous)
            top = int(p.argmax())
            m = Mention(symptom, clause.strip(), previous.strip(), MENTION_CLASSES[top], float(p[top]))
            mentions.append(m)
            if m.label != "none":
                found[symptom].append(m)
        readings, conflicts = {}, []
        for symptom in SYMPTOM_KEYS:
            labels = {m.label for m in found[symptom]}
            if not found[symptom]:
                readings[symptom] = "not_mentioned"
                continue
            sure = {m.label for m in found[symptom] if m.confidence >= CONFLICT_CONFIDENCE}
            if {"present", "absent"} <= sure:
                conflicts.append(symptom)
            readings[symptom] = self._settle(found[symptom])
        return Reading(readings, mentions, conflicts)

    def _settle(self, ms: list[Mention]) -> str:
        if self.rule == "last":
            return ms[-1].label
        return max(ms, key=lambda m: m.confidence).label  # "confident": the most confident mention
