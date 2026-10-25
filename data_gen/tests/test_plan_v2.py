import json
from collections import Counter

import pytest

from data_gen.cohort import sample_features
from data_gen.config import LLM_SETTINGS, GenConfig
from data_gen.labs import LAB_BY_KEY, LABS, SYMPTOM_BY_KEY, symptom_phrase_pool
from data_gen.plan import CASE_TYPES, lab_flag, plan_note
from data_gen.render import parse_back_errors, render
from data_gen.schema import NotePlan, NotePlanV2
from data_gen.seeds import rng_for
from data_gen.settings import PROFILES

LLM_CFG = GenConfig(note_source="llm", seed=11)


def make(cfg, i, case=None):
    labs, flags = sample_features(rng_for(cfg.seed, "features", i))
    return labs, flags, plan_note(cfg, labs, flags, rng_for(cfg.seed, "noise", i), case)


@pytest.fixture(scope="module")
def v2_plans():
    return [make(LLM_CFG, i) for i in range(4000)]


# --- template source keeps producing unchanged version 1 plans ------------------------------------

def test_template_source_still_yields_version_1_plans():
    for i in range(50):
        _, _, p = make(GenConfig(seed=3), i)
        assert type(p.plan) is NotePlan and p.plan.version == "1"
        assert "phrases" not in json.dumps(p.plan.model_dump())


# --- version 2 ---------------------------------------------------------------------------------

def test_v2_plans_are_deterministic_and_typed(v2_plans):
    again = make(LLM_CFG, 7)[2]
    assert again.plan == v2_plans[7][2].plan
    for _, _, p in v2_plans[:200]:
        assert isinstance(p.plan, NotePlanV2) and p.plan.version == "2"
        assert p.plan.style in LLM_SETTINGS


def test_setting_mix_follows_config(v2_plans):
    counts = Counter(p.plan.style for _, _, p in v2_plans)
    for setting in LLM_SETTINGS:
        assert abs(counts[setting] / len(v2_plans) - 0.25) < 0.03


def test_profiles_shape_what_each_setting_states(v2_plans):
    for _, flags, p in v2_plans:
        prof = PROFILES[p.plan.style]
        n_labs = len(p.plan.labs)
        present = len(LABS) - len(p.missing)
        if prof.max_labs is None:
            assert n_labs == present  # states every non-missing lab
        else:
            assert n_labs <= max(prof.max_labs, 0)
        if prof.max_negatives is not None:
            assert sum(s.stated == "negated" for s in p.plan.symptoms) <= prof.max_negatives
        for lab in p.plan.labs:
            assert (lab.flag is not None) <= prof.show_flags
            assert (lab.ref_range is not None) == prof.show_ref_ranges


def test_symptoms_carry_allowed_phrases_and_quotes_only_where_allowed(v2_plans):
    for _, flags, p in v2_plans[:1500]:
        prof = PROFILES[p.plan.style]
        for s in p.plan.symptoms:
            assert 2 <= len(s.phrases) <= 3
            assert set(s.phrases) <= set(symptom_phrase_pool(s.flag, s.stated))
            if s.quote:
                assert prof.quote_patient and s.stated in ("present", "hedged")


def test_phrase_diversity_across_a_cohort(v2_plans):
    for key, sym in SYMPTOM_BY_KEY.items():
        seen = Counter(ph for _, _, p in v2_plans for s in p.plan.symptoms if s.flag == key for ph in s.phrases)
        assert len(seen) >= 3
        assert max(seen.values()) / sum(seen.values()) < 0.6, key


# --- lab flags ---------------------------------------------------------------------------------

@pytest.mark.parametrize("lab", LABS, ids=lambda l: l.key)
def test_flag_boundaries_are_exclusive(lab):
    assert lab_flag(lab.key, lab.ref_hi, lab.unit) is None
    assert lab_flag(lab.key, lab.ref_lo, lab.unit) is None
    assert lab_flag(lab.key, lab.ref_hi * 1.001 + 1e-9, lab.unit) == "H"
    assert lab_flag(lab.key, lab.ref_lo * 0.999 - 1e-9, lab.unit) == "L"
    assert lab_flag(lab.key, lab.mean, lab.unit) is None
    if lab.alt_unit:  # judged on the value as written, in its own unit
        assert lab_flag(lab.key, lab.to_alt(lab.ref_hi * 1.05), lab.alt_unit) == "H"
        assert lab_flag(lab.key, lab.to_alt(lab.ref_lo * 0.95), lab.alt_unit) == "L"
        assert lab_flag(lab.key, lab.to_alt(lab.mean), lab.alt_unit) is None


def test_ehr_template_flags_match_stated_values(v2_plans):
    checked = 0
    for _, _, p in v2_plans:
        if p.plan.style != "ehr_template":
            continue
        for lab in p.plan.labs:
            assert lab.flag == lab_flag(lab.lab, float(f"{lab.value:.3g}"), lab.unit)  # judged on the printed value
            lo, hi = lab.ref_range
            assert lo < hi
            checked += 1
    assert checked > 1000


# --- copy_forward stale values -------------------------------------------------------------------

def test_copy_forward_stale_rate_is_scaled_and_tagged(v2_plans):
    cfg = LLM_CFG
    expected = cfg.stale_rate * PROFILES["copy_forward"].stale_rate_multiplier
    stated = stale = 0
    for _, _, p in v2_plans:
        if p.plan.style != "copy_forward":
            continue
        for lab in p.plan.labs:
            if lab.unit != LAB_BY_KEY[lab.lab].unit:
                continue  # unit-mismatched labs cannot also be stale
            stated += 1
            stale += lab.stale
            tagged = any(n.type == "contradiction" and n.lab == lab.lab for n in p.noise)
            assert lab.stale == tagged
    assert abs(stale / stated - expected) < 0.03


def test_other_settings_other_than_stale_styles_have_no_stale_values(v2_plans):
    for _, _, p in v2_plans:
        if p.plan.style in ("shorthand", "ehr_template", "ai_scribe"):
            assert not any(l.stale for l in p.plan.labs)


# --- ground truth and adversarial cases are unaffected -----------------------------------------------

@pytest.mark.parametrize("case", CASE_TYPES)
def test_every_case_type_builds_a_v2_plan(case):
    for i in range(30):
        labs, flags, p = make(LLM_CFG, 100 + i, case)
        assert isinstance(p.plan, NotePlanV2)
        if case != "borderline":  # that tag is added by the record builder, not the plan
            assert p.tags, case


def test_template_renderers_still_pass_parse_back_on_v2_plans(v2_plans):
    # The extra fields are ignored: restyle a v2 plan as a template style and the old checks still hold.
    failures = []
    for _, _, p in v2_plans[:500]:
        for style in ("terse", "templated"):
            plan = p.plan.model_copy(update={"style": style})
            failures += parse_back_errors(plan, render(plan))
    assert failures == []


def test_flags_are_judged_on_the_value_as_printed():
    from data_gen.plan import _v2_labs
    from data_gen.schema import PlanLab
    from data_gen.settings import PROFILES

    profile = PROFILES["ehr_template"]
    at_limit = _v2_labs(profile, [PlanLab(lab="dorrin_ratio", value=0.5996, unit="ratio")], [])[0]
    below = _v2_labs(profile, [PlanLab(lab="dorrin_ratio", value=0.5949, unit="ratio")], [])[0]
    assert at_limit.flag is None  # prints as 0.6, which is the lower limit, not below it
    assert below.flag == "L"
