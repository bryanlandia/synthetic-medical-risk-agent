"""Validation of records and datasets against the synthetic-cohort and clinical-notes specs."""

from __future__ import annotations

import json
from collections import Counter

from .config import AVAILABLE_STYLES, LLM_SETTINGS
from .injections import all_texts
from .labs import LAB_BY_KEY, LABS
from .plan import CASE_TYPES
from .render import ParsedNote, parse_back_errors, parse_note
from .scan import scan_text
from .schema import Record

FORBIDDEN_IN_INPUT = ("true_probability", "ground_truth", '"label"', '"flags"', '"plan"')
STRICT_MIN_TEST = 500  # at or above this test size the spec's fixed 0.1 SD tolerance is meaningful


# --- record level ------------------------------------------------------------------------------

def _lab_errors(r: Record, parsed: ParsedNote) -> list[str]:
    pid, gt = r.patient_id, r.ground_truth
    contradiction = {n.lab for n in r.noise if n.type == "contradiction"}
    missing = {n.lab for n in r.noise if n.type == "missing_value"}
    mismatch = {n.lab for n in r.noise if n.type == "unit_mismatch"}
    errs: list[str] = []
    for key, (value, unit) in parsed.labs.items():
        lab = LAB_BY_KEY[key]
        canon = value if unit == lab.unit else lab.from_alt(value)
        truth = gt.labs[key]
        if key in contradiction:
            if abs(canon - truth) <= 0.1 * abs(truth):
                errs.append(f"{pid}: {key} tagged contradiction but note value matches")
        elif abs(canon - truth) > 0.01 * abs(truth):
            errs.append(f"{pid}: {key} note value {canon} != true {truth}")
        if key in missing:
            errs.append(f"{pid}: missing lab {key} stated in note")
        if (unit != lab.unit) != (key in mismatch):
            errs.append(f"{pid}: {key} unit/noise-tag mismatch")
    return errs


def _symptom_ok(stated: str, truth: bool, disagrees: bool) -> bool:
    if disagrees:
        return stated == "negated" if truth else stated == "present"
    return stated in ("present", "hedged") if truth else stated == "negated"


def _symptom_errors(r: Record, parsed: ParsedNote) -> list[str]:
    pid, gt = r.patient_id, r.ground_truth
    disagree = {t.flag for t in r.tags if t.type == "note_flag_disagreement"}
    hedged_noise = {n.flag for n in r.noise if n.type == "hedging"}
    errs: list[str] = []
    for flag, stated in parsed.symptoms.items():
        if not _symptom_ok(stated, gt.flags[flag], flag in disagree):
            errs.append(f"{pid}: symptom {flag} stated {stated} vs truth {gt.flags[flag]}")
        if (stated == "hedged") != (flag in hedged_noise):
            errs.append(f"{pid}: symptom {flag} hedging/noise-tag mismatch")
    errs += [
        f"{pid}: true symptom {flag} not stated"
        for flag, truth in gt.flags.items()
        if truth and flag not in parsed.symptoms and flag not in disagree
    ]
    return errs


def _panel_errors(r: Record) -> list[str]:
    missing = {n.lab for n in r.noise if n.type == "missing_value"}
    errs: list[str] = []
    for entry in r.input.panel:
        if (entry.value is None) != (entry.lab in missing):
            errs.append(f"{r.patient_id}: panel missing-ness of {entry.lab} disagrees with noise")
        if entry.unit != LAB_BY_KEY[entry.lab].unit:
            errs.append(f"{r.patient_id}: panel unit for {entry.lab} is not canonical")
    return errs


def _llm_record_errors(r: Record) -> list[str]:
    """Structural checks for LLM-written records (plan version 2). Text fidelity was checked, with the
    LLM extractor, when each note was accepted; the offline text checks live in data_gen.llm.checks."""
    pid = r.patient_id
    errs: list[str] = []
    view = json.dumps(r.input_view()).lower()
    errs += [f"{pid}: input view contains {w!r}" for w in FORBIDDEN_IN_INPUT if w in view]
    if r.style not in LLM_SETTINGS or r.style != r.plan.style:
        errs.append(f"{pid}: style {r.style!r} is not an LLM documentation setting matching the plan")
    errs += [f"{pid}: identifier scan: {f}" for f in scan_text(r.input.note)]
    if r.pair_group is not None and any(setting in r.patient_id for setting in LLM_SETTINGS):
        errs.append(f"{pid}: record id reveals its setting")
    return errs + _panel_errors(r)


def record_errors(r: Record) -> list[str]:
    pid = r.patient_id
    if r.plan is None:
        return [f"{pid}: record has no plan"]
    if r.plan.version == "2":
        return _llm_record_errors(r)
    errs: list[str] = []
    view = json.dumps(r.input_view()).lower()
    errs += [f"{pid}: input view contains {w!r}" for w in FORBIDDEN_IN_INPUT if w in view]
    if r.style not in AVAILABLE_STYLES:
        errs.append(f"{pid}: style {r.style!r} has no renderer")
    errs += [f"{pid}: {e}" for e in parse_back_errors(r.plan, r.input.note)]
    errs += [f"{pid}: identifier scan: {f}" for f in scan_text(r.input.note)]
    parsed = parse_note(r.input.note, r.style)
    return errs + _lab_errors(r, parsed) + _symptom_errors(r, parsed) + _panel_errors(r)


# --- dataset level -----------------------------------------------------------------------------

def _clean_split_errors(r: Record, split: str) -> list[str]:
    """train / random test must contain no adversarial content or implausible values."""
    pid = r.patient_id
    errs: list[str] = []
    if r.tags:
        errs.append(f"{pid}: {split} record carries tags {sorted(r.tag_types())}")
    if r.noise_types() & {"note_flag_disagreement", "prompt_injection"}:
        errs.append(f"{pid}: adversarial noise in {split}")
    if r.plan and r.plan.injection:
        errs.append(f"{pid}: injection in {split}")
    errs += [f"{pid}: injection text in {split} note" for text in all_texts() if text in r.input.note]
    for entry in r.input.panel:
        lab = LAB_BY_KEY[entry.lab]
        if entry.value is not None and not lab.plaus_lo <= entry.value <= lab.plaus_hi:
            errs.append(f"{pid}: implausible {entry.lab}={entry.value} in {split}")
    return errs


def _adversarial_record_errors(r: Record) -> list[str]:
    pid = r.patient_id
    if not r.tags:
        return [f"{pid}: adversarial record without tags"]
    errs: list[str] = []
    if "borderline" in r.tag_types() and not 0.4 <= r.ground_truth.true_probability <= 0.6:
        errs.append(f"{pid}: borderline p={r.ground_truth.true_probability}")
    for t in r.tags:
        if t.type != "impossible_value":
            continue
        lab = LAB_BY_KEY[t.lab]  # type: ignore[index]
        entry = next(e for e in r.input.panel if e.lab == t.lab)
        if entry.value is None or lab.plaus_lo <= entry.value <= lab.plaus_hi:
            errs.append(f"{pid}: impossible_value tag but panel value plausible")
    return errs


def pair_group_errors(by_split: dict[str, list[Record]]) -> list[str]:
    """Matched-pair groups: one patient written in every LLM setting, identical apart from the note."""
    groups: dict[str, list[Record]] = {}
    for recs in by_split.values():
        for r in recs:
            if r.pair_group is not None:
                groups.setdefault(r.pair_group, []).append(r)
    errs: list[str] = []
    for group, members in groups.items():
        if any(m.split != "test" for m in members):
            errs.append(f"pair group {group}: members must be in the test split")
        if sorted(m.style for m in members) != sorted(LLM_SETTINGS):
            errs.append(f"pair group {group}: expected one record per setting, got {sorted(m.style for m in members)}")
        if len({m.ground_truth.model_dump_json() for m in members}) != 1:
            errs.append(f"pair group {group}: ground truth differs between members")
        if len({tuple((e.lab, e.value) for e in m.input.panel) for m in members}) != 1:
            errs.append(f"pair group {group}: lab panel differs between members")
        if len({m.input.note for m in members}) != len(members):
            errs.append(f"pair group {group}: two members have identical text")
    return errs


def dataset_errors(by_split: dict[str, list[Record]], min_per_type: int = 50) -> list[str]:
    errs: list[str] = []
    all_ids = [r.patient_id for recs in by_split.values() for r in recs]
    if len(set(all_ids)) != len(all_ids):
        errs.append("patient ids are not unique across splits")

    for split, recs in by_split.items():
        for r in recs:
            if r.split != split:
                errs.append(f"{r.patient_id}: split field {r.split} != file split {split}")
            errs += record_errors(r)
            if split in ("train", "test"):
                errs += _clean_split_errors(r, split)

    adv = by_split.get("adversarial", [])
    counts = Counter(t for r in adv for t in r.tag_types())
    errs += [
        f"adversarial case type {case}: {counts[case]} < {min_per_type}"
        for case in CASE_TYPES if counts[case] < min_per_type
    ]
    for r in adv:
        errs += _adversarial_record_errors(r)
    return errs + pair_group_errors(by_split)


def distribution_errors(by_split: dict[str, list[Record]]) -> list[str]:
    """Random test must match train on prevalence (0.02) and lab means (0.1 SD).

    For tiny smoke datasets (test split under 500) the sampling noise of a mean difference alone
    exceeds 0.1 SD, so the lab-mean tolerance is widened to 5 standard errors there.
    """
    train, test = by_split.get("train", []), by_split.get("test", [])
    if not train or not test:
        return ["train or test split is empty"]
    tol_sd = 0.1 if len(test) >= STRICT_MIN_TEST else 5 * (1 / len(train) + 1 / len(test)) ** 0.5
    errs = []
    prev = abs(sum(r.ground_truth.label for r in train) / len(train)
               - sum(r.ground_truth.label for r in test) / len(test))
    if prev > 0.02:
        errs.append(f"train/test prevalence differs by {prev:.4f} > 0.02")
    for lab in LABS:
        a = sum(r.ground_truth.labs[lab.key] for r in train) / len(train)
        b = sum(r.ground_truth.labs[lab.key] for r in test) / len(test)
        if abs(a - b) >= tol_sd * lab.sd:
            errs.append(f"train/test mean of {lab.key} differs by {abs(a - b) / lab.sd:.3f} SD >= {tol_sd:.3f}")
    return errs


def manifest_errors(by_split: dict[str, list[Record]], manifest: dict) -> list[str]:
    errs = []
    if manifest.get("synthetic") is not True or "synthetic" not in manifest.get("notice", "").lower():
        errs.append("manifest lacks the synthetic notice")
    for name, recs in by_split.items():
        info = manifest.get("splits", {}).get(name)
        if info is None or info.get("n") != len(recs):
            errs.append(f"manifest count for {name} does not match the file")
    errs += [f"manifest missing {key}" for key in ("seed", "generator_version", "config_hash", "note_source")
             if key not in manifest]
    return errs


__all__ = ["record_errors", "dataset_errors", "distribution_errors", "manifest_errors"]
