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
from .ratings import RatingFile, rating_files, read_rating_file

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
    # Set when several raters were merged: every rater's complete set of symptom labels, and whether the
    # raters disagreed about plausibility.
    symptom_sets: list[dict[str, str | None]] = field(default_factory=list)
    disagree: bool = False

    @property
    def complete(self) -> bool:
        return self.plausible is not None and bool(self.label_sets())

    def label_sets(self) -> list[dict[str, str | None]]:
        if self.symptom_sets:
            return self.symptom_sets
        return [self.symptoms] if all(self.symptoms.get(k) for k in SYMPTOM_KEYS) else []


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
    raters: list[str] = field(default_factory=list)  # rater kinds that were counted, e.g. ["human"]
    rater_names: list[str] = field(default_factory=list)
    disagreements: dict[str, int] = field(default_factory=dict)  # per setting, notes the raters split on
    discrimination: dict[str, dict] = field(default_factory=dict)  # llm reviewer -> controls gap numbers

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
        who = " and ".join(self.raters) if self.raters else "nobody"
        suffix = ""
        if "llm" in self.raters:
            suffix = " (includes an LLM review)" if "human" in self.raters else " (not a clinician)"
        lines.append(f"  rated by: {who}{suffix}" + (f" [{', '.join(self.rater_names)}]" if self.rater_names else ""))
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
        for name, g in self.discrimination.items():
            lines.append(f"  info  reviewer {name}: {g['notes_rate']:.0%} of LLM notes plausible vs {g['controls_rate']:.0%} of controls")
        if any(self.disagreements.values()):
            dis = ", ".join(f"{k} {v}" for k, v in self.disagreements.items() if v)
            lines.append(f"  info  raters disagreed on plausibility (counted as implausible): {dis}")
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
    kinds: set[str] = set()
    names: set[str] = set()
    disc: dict[str, dict] = {}
    for ratings, key in rounds:
        review = key.get("review", {})
        disc.update(review.get("discrimination", {}))
        kinds.update(review.get("kinds", ["human"]))
        names.update(review.get("raters", []))
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
    n = 0  # rater-notes with all five labels (pooled over raters)
    notes_labelled = 0
    disagreements = {s: 0 for s in LLM_SETTINGS}
    for setting, entries in chosen.items():
        for r, meta in entries:
            disagreements[setting] += r.disagree
            sets = r.label_sets() if r.plausible is not None else []
            notes_labelled += bool(sets)
            for labels in sets:
                n += 1
                for k in SYMPTOM_KEYS:
                    agree[k] += _LABEL_TO_STATUS[labels[k]] == meta["extraction"].get(k, "not_mentioned")
                    fid[k] += labels[k] == meta["plan_symptoms"].get(k, "none")
    if notes_labelled < needed * len(LLM_SETTINGS):
        problems.append(f"only {notes_labelled} notes have all five symptom labels filled; {needed * len(LLM_SETTINGS)} are needed")
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
        raters=sorted(kinds), rater_names=sorted(names), disagreements=disagreements, discrimination=disc,
    )


def _merge(files: list[tuple[str, RatingFile | None, dict[str, Rating]]]) -> dict[str, Rating]:
    """Combine several raters' ratings of the same notes. Plausibility is the most pessimistic one given
    (n if anyone said n), so adding a rater can only make the gate stricter."""
    ids = sorted({i for _, _, rs in files for i in rs})
    merged: dict[str, Rating] = {}
    for note_id in ids:
        given = [rs[note_id] for _, _, rs in files if note_id in rs]
        values = {r.plausible for r in given if r.plausible is not None}
        plausible = "n" if "n" in values else ("y" if values else None)
        sets = [dict(r.symptoms) for r in given if all(r.symptoms.get(k) for k in SYMPTOM_KEYS)]
        merged[note_id] = Rating(
            plausible=plausible, symptoms=dict(given[0].symptoms), symptom_sets=sets,
            comment=" | ".join(r.comment for r in given if r.comment), disagree=values == {"y", "n"})
    return merged


def _from_file(rf: RatingFile) -> dict[str, Rating]:
    return {i: Rating(plausible=nr.plausible, symptoms=dict(nr.symptoms), comment=nr.comment)
            for i, nr in rf.ratings.items()}


MIN_CONTROL_GAP = 0.20  # an LLM reviewer must rate the old template controls this far below the LLM notes


def load_round(directory: Path, accepted: tuple[str, ...] = ("human",),
               min_control_gap: float = MIN_CONTROL_GAP) -> tuple[Round, list[str]]:
    """Load a round's key and the ratings of every accepted rater kind. A hand-filled ratings.md counts as
    a human rater. Files from kinds that are not accepted are listed but not counted."""
    key = json.loads((directory / "key.json").read_text())
    problems: list[str] = []
    found: list[tuple[str, RatingFile | None, dict[str, Rating]]] = []  # (kind, file, ratings)
    skipped: list[str] = []
    ratings_md = directory / "ratings.md"
    if ratings_md.exists():
        md, probs = parse_ratings(ratings_md.read_text())
        problems += [f"{directory.name}: {p}" for p in probs]
        found.append(("human", None, md))
    for path in rating_files(directory):
        try:
            rf = read_rating_file(path)
        except ValueError as exc:
            problems.append(f"{directory.name}: {path.name} is not a valid rating file: {exc}")
            continue
        found.append((rf.kind, rf, _from_file(rf)))
    counted = [(k, rf, rs) for k, rf, rs in found if k in accepted]
    skipped = sorted({k for k, _, _ in found if k not in accepted})
    if not found:
        problems.append(f"{directory.name}: no ratings found: rate sheet.json in the rating app (or fill in sheet.md "
                        "and save it as ratings.md)")
    elif not counted:
        problems.append(f"{directory.name}: no ratings from an accepted rater kind ({', '.join(accepted)}); "
                        f"found only: {', '.join(skipped)}")
    names = [rf.rater if rf else "ratings.md" for _, rf, _ in counted]
    discrimination: dict[str, dict] = {}
    for kind, rf, _ in counted:
        if kind != "llm" or rf is None:
            continue
        from ..review.reviewer import controls_gap

        gap = controls_gap(rf.ratings, key)
        if gap is None:
            continue
        discrimination[rf.rater] = gap
        if gap["gap"] < min_control_gap:
            problems.append(
                f"{directory.name}: LLM reviewer {rf.rater} is non-discriminating: it rated {gap['notes_rate']:.0%} of the "
                f"LLM-written notes plausible but also {gap['controls_rate']:.0%} of the old template controls "
                f"(needs a gap of at least {min_control_gap:.0%})")
    key["review"] = {"kinds": sorted({k for k, _, _ in counted}), "raters": names, "not_counted": skipped,
                     "discrimination": discrimination}
    merged = _merge(counted) if counted else {}
    return (merged, key), problems


GATE_RESULT = "gate.json"


def review_description(raters: list[str]) -> str:
    """How the realism review is described wherever it is reported."""
    if not raters:
        return "no realism review"
    if "llm" in raters and "human" not in raters:
        return "an LLM review, not a clinician"
    if "llm" in raters:
        return "a human and an LLM review"
    return "a human review (not a clinical validation)"


def save_gate_result(directory: Path, report: GateReport) -> Path:
    """Remember who passed the notes, so the manifest of the full run can say so."""
    path = Path(directory) / GATE_RESULT
    path.write_text(json.dumps({
        "passed": report.passed,
        "rater_kinds": report.raters,
        "raters": report.rater_names,
        "description": review_description(report.raters),
        "disagreements": report.disagreements,
    }, indent=2, sort_keys=True) + "\n")
    return path


def load_gate_result(directory: Path) -> dict | None:
    path = Path(directory) / GATE_RESULT
    return json.loads(path.read_text()) if path.exists() else None
