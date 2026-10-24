"""Note plan: decides what a note says, including all labeled noise and adversarial content.

Everything here is decided by the generator (never by a renderer or an LLM), so every defect is
labeled by construction. The order of random draws is part of the dataset's reproducibility: do not
reorder draws without regenerating (and re-reviewing) the committed dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import PLAN_VERSION, PLAN_VERSION_LLM
from .config import STALE_VALUE_STYLES, GenConfig
from .injections import entries as injection_entries
from .labs import LAB_BY_KEY, LABS, SYMPTOM_BY_KEY, SYMPTOM_KEYS
from .rule import round_sig
from .schema import (
    Annotation,
    NotePlan,
    NotePlanV2,
    PlanInjection,
    PlanLab,
    PlanLabV2,
    PlanSymptom,
    PlanSymptomV2,
)
from .settings import PROFILES, SettingProfile

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
    plan: NotePlan | NotePlanV2
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


def _stated_keys(
    rng: np.random.Generator, present: list[str], forced: list[str],
    lo: int = 2, hi: int = 5, state_all: bool = False,
) -> list[str]:
    """Labs the note states: ``lo`` to ``hi - 1`` of the present ones (version 1: 2 to 4), or all."""
    if state_all:
        return [lab.key for lab in LABS if lab.key in set(present)]
    n_stated = min(len(present), int(rng.integers(lo, hi)))
    pool = [k for k in present if k not in forced]
    extra = max(0, n_stated - len(forced))
    chosen = set(forced)
    if extra and pool:
        chosen |= set(_pick(rng, pool, min(extra, len(pool))))
    return [lab.key for lab in LABS if lab.key in chosen]


def _state_lab(
    cfg: GenConfig, rng: np.random.Generator, case: str | None, style: str,
    key: str, true_v: float, forced: list[str], stale_rate: float | None = None,
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
    elif ordinary and style in STALE_VALUE_STYLES and rng.random() < (
        cfg.stale_rate if stale_rate is None else stale_rate
    ):
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
    flags: dict[str, bool], disagree: dict[str, str], hedge_rate: float | None = None,
) -> tuple[list[PlanSymptom], list[Annotation]]:
    symptoms: list[PlanSymptom] = []
    noise: list[Annotation] = []
    hedge = cfg.hedge_rate if hedge_rate is None else hedge_rate
    for key in SYMPTOM_KEYS:
        truth = flags[key]
        if key in disagree:
            symptoms.append(PlanSymptom(flag=key, stated="negated" if truth else "present"))
        elif truth and ordinary and rng.random() < hedge:
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


# --- version 2 helpers (LLM-written notes) --------------------------------------------------------------

def lab_flag(lab_key: str, stated_value: float, unit: str) -> str | None:
    """High / low against the lab's reference range, judged on the value as written."""
    lab = LAB_BY_KEY[lab_key]
    canonical = stated_value if unit == lab.unit else lab.from_alt(stated_value)
    if canonical > lab.ref_hi:
        return "H"
    if canonical < lab.ref_lo:
        return "L"
    return None


def _display_range(lab_key: str, unit: str) -> tuple[float, float]:
    lab = LAB_BY_KEY[lab_key]
    if unit == lab.unit:
        return (lab.ref_lo, lab.ref_hi)
    return (round_sig(lab.to_alt(lab.ref_lo), 3), round_sig(lab.to_alt(lab.ref_hi), 3))


def _is_stale(noise: list[Annotation], lab_key: str) -> bool:
    return any(
        a.type == "contradiction" and a.lab == lab_key and a.detail.get("kind") == "stale_copied_forward"
        for a in noise
    )


def _v2_labs(profile: SettingProfile, plan_labs: list[PlanLab], noise: list[Annotation]) -> list[PlanLabV2]:
    return [
        PlanLabV2(
            lab=pl.lab, value=pl.value, unit=pl.unit,
            flag=lab_flag(pl.lab, pl.value, pl.unit) if profile.show_flags else None,
            ref_range=_display_range(pl.lab, pl.unit) if profile.show_ref_ranges else None,
            stale=_is_stale(noise, pl.lab),
        )
        for pl in plan_labs
    ]


def _v2_symptoms(
    rng: np.random.Generator, profile: SettingProfile,
    symptoms: list[PlanSymptom], disagree: dict[str, str],
) -> list[PlanSymptomV2]:
    """Cap the negatives a setting states, and attach wording options and quote requests."""
    negated = [i for i, s in enumerate(symptoms) if s.stated == "negated" and s.flag not in disagree]
    dropped: set[int] = set()
    if profile.max_negatives is not None and len(negated) > profile.max_negatives:
        keep = {int(i) for i in rng.choice(negated, size=profile.max_negatives, replace=False)}
        dropped = set(negated) - keep
    out: list[PlanSymptomV2] = []
    for i, s in enumerate(symptoms):
        if i in dropped:
            continue
        pool = SYMPTOM_BY_KEY[s.flag].phrases
        picked = rng.choice(len(pool), size=min(int(rng.integers(2, 4)), len(pool)), replace=False)
        quote = bool(
            profile.quote_patient and s.stated in ("present", "hedged") and rng.random() < 0.5
        )
        out.append(PlanSymptomV2(
            flag=s.flag, stated=s.stated, phrases=[pool[int(j)] for j in picked], quote=quote))
    return out


def _scaled(rate: float, multiplier: float) -> float:
    return min(1.0, rate * multiplier)


def plan_note(
    cfg: GenConfig,
    labs: dict[str, float],
    flags: dict[str, bool],
    rng: np.random.Generator,
    case: str | None = None,
) -> PlannedNote:
    """Build the plan for one patient. ``case`` None = ordinary train/test patient.

    Template notes get a version 1 plan. With the LLM source the style is a documentation setting and
    the plan is version 2, following that setting's profile. Version 1 draws are unchanged.
    """
    style = choose_style(cfg, rng)
    profile = PROFILES[style] if cfg.note_source == "llm" else None
    render_seed = int(rng.integers(0, 2**31 - 1))

    missing = _choose_missing(cfg, rng, case)
    noise = [Annotation(type="missing_value", lab=key) for key in sorted(missing)]
    tags: list[Annotation] = []
    if case == "missing_labs":
        tags.append(Annotation(type="missing_labs", detail={"count": len(missing)}))
    present = [lab.key for lab in LABS if lab.key not in missing]

    forced = _forced_labs(rng, case, present)
    if profile is None:
        stated, stale_rate = _stated_keys(rng, present, forced), None
    else:
        stated = _stated_keys(
            rng, present, forced, profile.min_labs, (profile.max_labs or 0) + 1,
            state_all=profile.max_labs is None)
        stale_rate = _scaled(cfg.stale_rate, profile.stale_rate_multiplier)
    plan_labs: list[PlanLab] = []
    for key in stated:
        plan_lab, lab_noise, lab_tags = _state_lab(
            cfg, rng, case, style, key, labs[key], forced, stale_rate)
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
    hedge_rate = None if profile is None else _scaled(cfg.hedge_rate, profile.hedge_rate_multiplier)
    symptoms, hedge_noise = _plan_symptoms(cfg, rng, case is None, flags, disagree, hedge_rate)
    noise += hedge_noise

    injection, injection_tags = _choose_injection(rng, case)
    tags += injection_tags

    plan: NotePlan | NotePlanV2
    if profile is None:
        plan = NotePlan(
            version=PLAN_VERSION, style=style, labs=plan_labs, symptoms=symptoms,
            injection=injection, render_seed=render_seed,
        )
    else:
        plan = NotePlanV2(
            version=PLAN_VERSION_LLM, style=style, labs=_v2_labs(profile, plan_labs, noise),
            symptoms=_v2_symptoms(rng, profile, symptoms, disagree),
            injection=injection, render_seed=render_seed,
        )
    return PlannedNote(plan=plan, noise=noise, tags=tags, missing=missing, panel_overrides=overrides)
