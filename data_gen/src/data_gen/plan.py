"""Note plan: decides what a note says, including all labeled noise and adversarial content.

Everything here is decided by the generator (never by a renderer or an LLM), so every defect is
labeled by construction. The order of random draws is part of the dataset's reproducibility: do not
reorder draws without regenerating (and re-reviewing) the committed dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import PLAN_VERSION
from .config import GenConfig
from .injections import entries as injection_entries
from .labs import LAB_BY_KEY, LABS, SYMPTOM_KEYS
from .rule import round_sig
from .schema import Annotation, NotePlan, PlanInjection, PlanLab, PlanSymptom

CASE_TYPES: tuple[str, ...] = (
    "borderline",
    "impossible_value",
    "missing_labs",
    "unit_mismatch",
    "contradiction",
    "note_flag_disagreement",
    "prompt_injection",
)


@dataclass
class PlannedNote:
    plan: NotePlan
    noise: list[Annotation] = field(default_factory=list)
    tags: list[Annotation] = field(default_factory=list)
    missing: set[str] = field(default_factory=set)
    panel_overrides: dict[str, float] = field(default_factory=dict)  # lab -> recorded (wrong) value


def choose_style(cfg: GenConfig, rng: np.random.Generator) -> str:
    cfg.check_styles_available()
    names = sorted(s for s, r in cfg.style_rates.items() if r > 0)  # sorted: independent of dict order
    probs = np.array([cfg.style_rates[s] for s in names])
    return str(names[int(rng.choice(len(names), p=probs / probs.sum()))])


def _alt_stated(lab_key: str, true_value: float) -> tuple[float, str]:
    lab = LAB_BY_KEY[lab_key]
    return round_sig(lab.to_alt(true_value)), lab.alt_unit  # type: ignore[return-value]


def _impossible_value(lab_key: str, value: float) -> tuple[float, str]:
    lab = LAB_BY_KEY[lab_key]
    if value * 10 > lab.plaus_hi:
        return round_sig(value * 10), "decimal_shift"
    return round_sig(-value), "negative"


def _pick(rng: np.random.Generator, pool: list[str], n: int) -> list[str]:
    return [pool[int(i)] for i in rng.choice(len(pool), size=n, replace=False)]


# --- missing labs ---------------------------------------------------------------------------

def _choose_missing(cfg: GenConfig, rng: np.random.Generator, case: str | None) -> set[str]:
    if case is None:
        return {lab.key for lab in LABS if rng.random() < cfg.missing_rate}
    if case == "missing_labs":
        return set(_pick(rng, [lab.key for lab in LABS], int(rng.integers(2, 5))))
    return set()


# --- which labs the note states ----------------------------------------------------------------

def _forced_labs(rng: np.random.Generator, case: str | None, present: list[str]) -> list[str]:
    """Labs a case type needs the note to state; impossible_value forces exactly one."""
    if case == "impossible_value":
        return [present[int(rng.integers(0, len(present)))]]
    if case == "unit_mismatch":
        alt_capable = [k for k in present if LAB_BY_KEY[k].alt_unit]
        return _pick(rng, alt_capable, min(len(alt_capable), int(rng.integers(1, 3))))
    if case == "contradiction":
        return _pick(rng, present, min(len(present), int(rng.integers(1, 3))))
    return []


def _stated_keys(rng: np.random.Generator, present: list[str], forced: list[str]) -> list[str]:
    n_stated = min(len(present), int(rng.integers(2, 5)))
    pool = [k for k in present if k not in forced]
    extra = max(0, n_stated - len(forced))
    chosen = set(forced)
    if extra and pool:
        chosen |= set(_pick(rng, pool, min(extra, len(pool))))
    return [lab.key for lab in LABS if lab.key in chosen]


def _state_lab(
    cfg: GenConfig, rng: np.random.Generator, case: str | None, style: str,
    key: str, true_v: float, forced: list[str],
) -> tuple[PlanLab, list[Annotation], list[Annotation]]:
    """What the note says for one lab, plus the noise/tag annotations that describe it."""
    lab = LAB_BY_KEY[key]
    ordinary = case is None
    noise: list[Annotation] = []
    tags: list[Annotation] = []

    want_mismatch = False
    if lab.alt_unit:
        if ordinary:
            want_mismatch = bool(rng.random() < cfg.unit_mismatch_rate)
        elif case == "unit_mismatch" and key in forced:
            want_mismatch = True

    value, unit = true_v, lab.unit
    if want_mismatch:
        value, unit = _alt_stated(key, true_v)
        ann = Annotation(type="unit_mismatch", lab=key, detail={
            "unit_written": unit, "unit_canonical": lab.unit, "factor": lab.factor})
        noise.append(ann)
        if case == "unit_mismatch":
            tags.append(ann)
    elif ordinary and style == "templated" and rng.random() < cfg.stale_rate:
        factor = float(rng.uniform(1.25, 1.7) if rng.random() < 0.5 else rng.uniform(0.55, 0.8))
        value = round_sig(true_v * factor)
        noise.append(Annotation(type="contradiction", lab=key, detail={
            "kind": "stale_copied_forward", "stated": value, "true": true_v}))
    elif case == "contradiction" and key in forced:
        factor = float(rng.uniform(1.8, 2.5) if rng.random() < 0.5 else rng.uniform(0.4, 0.6))
        value = round_sig(true_v * factor)
        ann = Annotation(type="contradiction", lab=key, detail={
            "kind": "note_contradicts_labs", "stated": value, "true": true_v})
        noise.append(ann)
        tags.append(ann)
    return PlanLab(lab=key, value=value, unit=unit), noise, tags


# --- symptoms ----------------------------------------------------------------------------------

def _choose_disagreements(
    rng: np.random.Generator, case: str | None, flags: dict[str, bool]
) -> tuple[dict[str, str], list[Annotation]]:
    if case != "note_flag_disagreement":
        return {}, []
    disagree: dict[str, str] = {}
    tags: list[Annotation] = []
    for i in rng.choice(len(SYMPTOM_KEYS), size=int(rng.integers(1, 3)), replace=False):
        key = SYMPTOM_KEYS[int(i)]
        disagree[key] = "says_absent_when_present" if flags[key] else "says_present_when_absent"
        tags.append(Annotation(type="note_flag_disagreement", flag=key, detail={"direction": disagree[key]}))
    return disagree, tags


def _plan_symptoms(
    cfg: GenConfig, rng: np.random.Generator, ordinary: bool,
    flags: dict[str, bool], disagree: dict[str, str],
) -> tuple[list[PlanSymptom], list[Annotation]]:
    symptoms: list[PlanSymptom] = []
    noise: list[Annotation] = []
    for key in SYMPTOM_KEYS:
        truth = flags[key]
        if key in disagree:
            symptoms.append(PlanSymptom(flag=key, stated="negated" if truth else "present"))
        elif truth and ordinary and rng.random() < cfg.hedge_rate:
            symptoms.append(PlanSymptom(flag=key, stated="hedged"))
            noise.append(Annotation(type="hedging", flag=key))
        elif truth:
            symptoms.append(PlanSymptom(flag=key, stated="present"))
        elif rng.random() >= cfg.omit_absent_symptom_rate:  # otherwise simply not mentioned
            symptoms.append(PlanSymptom(flag=key, stated="negated"))
    return symptoms, noise


# --- injection ---------------------------------------------------------------------------------

def _choose_injection(rng: np.random.Generator, case: str | None) -> tuple[PlanInjection | None, list[Annotation]]:
    if case != "prompt_injection":
        return None, []
    catalog = injection_entries()
    entry = catalog[int(rng.integers(0, len(catalog)))]
    tag = Annotation(type="prompt_injection", detail={
        "category": entry.category, "goal": entry.goal, "entry_id": entry.id})
    return entry, [tag]


def plan_note(
    cfg: GenConfig,
    labs: dict[str, float],
    flags: dict[str, bool],
    rng: np.random.Generator,
    case: str | None = None,
) -> PlannedNote:
    """Build the plan for one patient. ``case`` None = ordinary train/test patient."""
    style = choose_style(cfg, rng)
    render_seed = int(rng.integers(0, 2**31 - 1))

    missing = _choose_missing(cfg, rng, case)
    noise = [Annotation(type="missing_value", lab=key) for key in sorted(missing)]
    tags: list[Annotation] = []
    if case == "missing_labs":
        tags.append(Annotation(type="missing_labs", detail={"count": len(missing)}))
    present = [lab.key for lab in LABS if lab.key not in missing]

    forced = _forced_labs(rng, case, present)
    plan_labs: list[PlanLab] = []
    for key in _stated_keys(rng, present, forced):
        plan_lab, lab_noise, lab_tags = _state_lab(cfg, rng, case, style, key, labs[key], forced)
        plan_labs.append(plan_lab)
        noise += lab_noise
        tags += lab_tags

    overrides: dict[str, float] = {}
    if case == "impossible_value":
        key = forced[0]
        recorded, kind = _impossible_value(key, labs[key])
        overrides[key] = recorded
        tags.append(Annotation(type="impossible_value", lab=key, detail={
            "recorded": recorded, "true": labs[key], "kind": kind}))

    disagree, disagree_tags = _choose_disagreements(rng, case, flags)
    tags += disagree_tags
    symptoms, hedge_noise = _plan_symptoms(cfg, rng, case is None, flags, disagree)
    noise += hedge_noise

    injection, injection_tags = _choose_injection(rng, case)
    tags += injection_tags

    plan = NotePlan(
        version=PLAN_VERSION, style=style, labs=plan_labs, symptoms=symptoms,
        injection=injection, render_seed=render_seed,
    )
    return PlannedNote(plan=plan, noise=noise, tags=tags, missing=missing, panel_overrides=overrides)
