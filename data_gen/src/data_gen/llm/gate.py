"""The human realism gate: load the owner's blind ratings, join them to the key, and decide pass or fail.

Two thresholds block the full paid run:
- every setting: at least 80% of its rated notes plausible (minimum ``llm.pilot_per_setting`` rated);
- the symptom extractor agrees with the owner's hand labels on at least 95% of notes, for every flag.

Template-fixture controls are reported but never gated. A later round (a revised prompt, fresh notes)
replaces only the settings it contains.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import LLM_SETTINGS, GenConfig
from ..labs import SYMPTOM_KEYS
from .pilot import PLAUSIBLE_VALUES, SYMPTOM_VALUES

PLAUSIBLE_THRESHOLD = 0.80
EXTRACTOR_THRESHOLD = 0.95
_LABEL_TO_STATUS = {"present": "present", "possible": "possible", "absent": "absent", "none": "not_mentioned"}
_SECTION = re.compile(r"^## (n\d+)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^([a-z_]+):[ \t]*(.*)$", re.MULTILINE)


@dataclass
class Rating:
    plausible: str | None = None
    symptoms: dict[str, str | None] = field(default_factory=dict)
    comment: str = ""

    @property
    def complete(self) -> bool:
        return self.plausible is not None and all(self.symptoms.get(k) for k in SYMPTOM_KEYS)


def parse_ratings(text: str) -> tuple[dict[str, Rating], list[str]]:
    """Parse a filled sheet. Returns (ratings by note id, format problems). Blank fields are left None."""
    problems: list[str] = []
    ratings: dict[str, Rating] = {}
    parts = _SECTION.split(text)  # [preamble, id1, body1, id2, body2, ...]
    for note_id, body in zip(parts[1::2], parts[2::2]):
        after = body.split("```")[-1] if body.count("```") >= 2 else body
        fields = {k: v.strip() for k, v in _FIELD.findall(after)}
        r = Rating(comment=fields.get("comment", ""))
        plausible = fields.get("plausible", "").lower()
        if plausible:
            plausible = {"yes": "y", "no": "n"}.get(plausible, plausible)
            if plausible in PLAUSIBLE_VALUES:
                r.plausible = plausible
            else:
                problems.append(f"{note_id}: plausible must be y or n, got {fields['plausible']!r}")
        for key in SYMPTOM_KEYS:
            value = fields.get(key, "").lower()
            if value in SYMPTOM_VALUES:
                r.symptoms[key] = value
            elif value:
                problems.append(f"{note_id}: {key} must be one of {', '.join(SYMPTOM_VALUES)}, got {fields[key]!r}")
        ratings[note_id] = r
    if not ratings:
        problems.append("no '## nNN' sections found: is this the filled rating sheet?")
    return ratings, problems


@dataclass
class SettingResult:
    rated: int
    plausible: int
    needed: int

    @property
    def rate(self) -> float:
        return self.plausible / self.rated if self.rated else 0.0

    @property
    def passed(self) -> bool:
        return self.rated >= self.needed and self.rate >= PLAUSIBLE_THRESHOLD


@dataclass
class GateReport:
    settings: dict[str, SettingResult]
    extractor_accuracy: dict[str, float]
    extractor_notes: int
    extractor_needed: int
    fidelity: dict[str, float]
    controls_rated: int
    controls_plausible: int
    exclusion_rates: dict[str, float]
    exclusion_threshold: float
    problems: list[str]

    @property
    def extractor_passed(self) -> bool:
        return (self.extractor_notes >= self.extractor_needed
                and all(a >= EXTRACTOR_THRESHOLD for a in self.extractor_accuracy.values()))

    @property
    def exclusion_passed(self) -> bool:
        return all(r <= self.exclusion_threshold for r in self.exclusion_rates.values())

    @property
    def passed(self) -> bool:
        return (not self.problems and all(s.passed for s in self.settings.values())
                and self.extractor_passed and self.exclusion_passed)

    def render(self) -> str:
        lines = ["Realism gate"]
        for name, s in self.settings.items():
            mark = "PASS" if s.passed else "FAIL"
            lines.append(f"  {mark}  {name:13s} {s.plausible}/{s.rated} plausible ({s.rate:.0%}; need >= "
                         f"{PLAUSIBLE_THRESHOLD:.0%} of at least {s.needed} rated)")
        acc = ", ".join(f"{k} {v:.2f}" for k, v in self.extractor_accuracy.items())
        lines.append(f"  {'PASS' if self.extractor_passed else 'FAIL'}  extractor accuracy per flag on "
                     f"{self.extractor_notes}/{self.extractor_needed} hand-labelled notes (need >= {EXTRACTOR_THRESHOLD}): {acc}")
        if self.exclusion_rates:
            ex = ", ".join(f"{k} {v:.0%}" for k, v in self.exclusion_rates.items())
            lines.append(f"  {'PASS' if self.exclusion_passed else 'FAIL'}  pilot exclusion rate (max {self.exclusion_threshold:.0%}): {ex}")
        if self.controls_rated:
            lines.append(f"  info  controls (old template notes, not gated): {self.controls_plausible}/{self.controls_rated} rated plausible")
        fid = ", ".join(f"{k} {v:.2f}" for k, v in self.fidelity.items())
        lines.append(f"  info  owner labels agree with the plan (not gated): {fid}")
        lines += [f"  problem: {p}" for p in self.problems]
        lines.append("RESULT: " + ("PASS - the full paid run may proceed" if self.passed else "FAIL - the full paid run is blocked"))
        return "\n".join(lines)


Round = tuple[dict[str, Rating], dict]  # (ratings by note id, key file contents)


def evaluate(cfg: GenConfig, rounds: list[Round], format_problems: list[str] | None = None) -> GateReport:
    needed = cfg.llm.pilot_per_setting
    problems = list(format_problems or [])
    # the latest round that contains a setting supplies that setting's notes
    chosen: dict[str, list[tuple[Rating, dict]]] = {}
    controls: list[Rating] = []
    for ratings, key in rounds:
        notes = key["notes"]
        in_round = {m["setting"] for m in notes.values() if m["kind"] == "note"}
        for s in in_round:
            chosen[s] = []
        for note_id, meta in notes.items():
            r = ratings.get(note_id, Rating())
            if meta["kind"] == "control":
                controls.append(r)
            else:
                chosen[meta["setting"]].append((r, meta))
    settings: dict[str, SettingResult] = {}
    for s in LLM_SETTINGS:
        entries = chosen.get(s, [])
        rated = [r for r, _ in entries if r.plausible is not None]
        settings[s] = SettingResult(len(rated), sum(r.plausible == "y" for r in rated), needed)
        if len(rated) < needed:
            problems.append(f"{s}: only {len(rated)} of {needed} notes have a plausible rating")
    agree = {k: 0 for k in SYMPTOM_KEYS}
    fid = {k: 0 for k in SYMPTOM_KEYS}
    n = 0
    for entries in chosen.values():
        for r, meta in entries:
            if not r.complete:
                continue
            n += 1
            for k in SYMPTOM_KEYS:
                agree[k] += _LABEL_TO_STATUS[r.symptoms[k]] == meta["extraction"].get(k, "not_mentioned")
                fid[k] += r.symptoms[k] == meta["plan_symptoms"].get(k, "none")
    if n < needed * len(LLM_SETTINGS):
        problems.append(f"only {n} notes have all five symptom labels filled; {needed * len(LLM_SETTINGS)} are needed")
    exclusion = {}
    for _, key in rounds:
        exclusion.update(key.get("meta", {}).get("exclusion_rates", {}))
    rated_controls = [c for c in controls if c.plausible is not None]
    return GateReport(
        settings=settings,
        extractor_accuracy={k: (agree[k] / n if n else 0.0) for k in SYMPTOM_KEYS},
        extractor_notes=n, extractor_needed=needed * len(LLM_SETTINGS),
        fidelity={k: (fid[k] / n if n else 0.0) for k in SYMPTOM_KEYS},
        controls_rated=len(rated_controls), controls_plausible=sum(c.plausible == "y" for c in rated_controls),
        exclusion_rates=exclusion, exclusion_threshold=cfg.llm.exclusion_threshold, problems=problems,
    )


def load_round(directory: Path) -> tuple[Round, list[str]]:
    key = json.loads((directory / "key.json").read_text())
    ratings_path = directory / "ratings.md"
    if not ratings_path.exists():
        return ({}, key), [f"{ratings_path} not found: fill in sheet.md and save it as ratings.md"]
    ratings, problems = parse_ratings(ratings_path.read_text())
    return (ratings, key), [f"{directory.name}: {p}" for p in problems]
