"""Phrasebank, style traits, exemplars and the variety metrics: more natural, varied notes, code-graded."""

import re
from collections import Counter

import pytest

from data_gen.config import LLM_SETTINGS, GenConfig, LLMConfig
from data_gen.labs import PHRASEBANK, SYMPTOM_KEYS, all_symptom_phrases, symptom_phrase_pool
from data_gen.llm.checks import claims_scan, exemplar_errors, offline_errors, style_errors
from data_gen.llm.prompts import EXEMPLAR_INTRO, build_prompt, exemplars, prompt_text_hash, system_prompt
from data_gen.llm.variety import MAX_TOP_OPENER_SHARE, opener, variety_report
from data_gen.plan import plan_note
from data_gen.cohort import sample_features
from data_gen.scan import scan_text
from data_gen.seeds import rng_for
from data_gen.traits import EXEMPLAR_COUNT, TRAITS, choose_traits, exemplar_picks, stock_lines, trait_lines

CFG = GenConfig(note_source="llm", seed=7, llm=LLMConfig())


def plan_of(i, style):
    labs, flags = sample_features(rng_for(CFG.seed, "features", i))
    return plan_note(CFG, labs, flags, rng_for(CFG.seed, "noise", i), None, style=style).plan


@pytest.fixture(scope="module")
def plans():
    return {s: [plan_of(i, s) for i in range(120)] for s in LLM_SETTINGS}


# --- the phrasebank -----------------------------------------------------------------------------------------------

def test_phrasebank_covers_every_symptom_and_polarity_with_enough_options():
    assert set(PHRASEBANK) == set(SYMPTOM_KEYS)
    for key, pools in PHRASEBANK.items():
        assert set(pools) == {"present", "hedged", "negated"}
        for stated, pool in pools.items():
            assert len(pool) >= 6 and len(set(pool)) == len(pool), (key, stated)


def test_no_phrase_of_one_symptom_equals_or_contains_a_phrase_of_another():
    for a in SYMPTOM_KEYS:
        for b in SYMPTOM_KEYS:
            if a == b:
                continue
            for pa in all_symptom_phrases(a):
                for pb in all_symptom_phrases(b):
                    assert pa.lower() not in pb.lower(), (a, pa, b, pb)


def test_negated_wording_is_natural_not_a_negated_positive_phrase():
    for key in SYMPTOM_KEYS:
        for p in symptom_phrase_pool(key, "negated"):
            assert not re.search(r"\b(feels|is|are) not\b", p), p  # no "feels not exhausted"
        assert any(re.match(r"(no|denies|not)\b", p) or "steady" in p or "normal" in p
                   for p in symptom_phrase_pool(key, "negated"))


def test_a_plans_wording_options_match_how_the_symptom_is_stated(plans):
    for setting_plans in plans.values():
        for plan in setting_plans:
            for s in plan.symptoms:
                assert set(s.phrases) <= set(symptom_phrase_pool(s.flag, s.stated))


# --- style traits -------------------------------------------------------------------------------------------------

def test_traits_are_drawn_per_note_from_the_render_seed_and_are_reproducible(plans):
    for setting, setting_plans in plans.items():
        again = [plan_of(i, setting) for i in range(0, 120, 20)]
        for p in again:
            assert p.traits == choose_traits(setting, p.render_seed)
            assert p.exemplars == exemplar_picks(setting, p.render_seed, EXEMPLAR_COUNT)
        assert choose_traits(setting, 123) == choose_traits(setting, 123)
        assert set(setting_plans[0].traits) == {t.key for t in TRAITS[setting]}


def test_quick_notes_vary_less_than_documented_ones():
    count = {s: len(TRAITS[s]) for s in LLM_SETTINGS}
    assert count["shorthand"] < min(count["ehr_template"], count["ai_scribe"], count["copy_forward"])


def test_every_trait_value_is_used_across_a_cohort_and_none_dominates(plans):
    for setting, setting_plans in plans.items():
        for trait in TRAITS[setting]:
            used = Counter(p.traits[trait.key] for p in setting_plans)
            assert set(used) == set(trait.choices), (setting, trait.key)
            assert max(used.values()) / len(setting_plans) <= 0.6, (setting, trait.key, used)


def test_distinct_trait_combinations_meet_the_pilot_minimum(plans):
    for setting, setting_plans in plans.items():
        sample = setting_plans[:20]
        report = variety_report(setting, ["x"] * 20, [p.traits for p in sample])
        assert report["distinct_trait_combos"] >= report["min_distinct_trait_combos"], setting


def test_traits_do_not_change_the_plans_facts():
    # the traits stream is independent of the plan's own draws: same labs, symptoms and noise either way
    labs, flags = sample_features(rng_for(CFG.seed, "features", 5))
    a = plan_note(CFG, labs, flags, rng_for(CFG.seed, "noise", 5), None, style="ehr_template")
    b = plan_note(CFG, labs, flags, rng_for(CFG.seed, "noise", 5), None, style="ehr_template")
    assert a.plan.model_dump() == b.plan.model_dump() and a.noise == b.noise


def test_the_prompt_carries_the_style_lines_and_two_exemplars(plans):
    for setting, setting_plans in plans.items():
        plan = setting_plans[3]
        user = build_prompt(plan).user
        assert "Style for this note" in user
        for line in trait_lines(setting, plan.traits):
            assert line in user
        assert user.count("Example ") == 2 and EXEMPLAR_INTRO in user
        for i in plan.exemplars:
            assert exemplars(setting)[i] in user
        assert user.index("Style for this note") < user.index(EXEMPLAR_INTRO)


def test_the_setting_prompts_defer_to_the_style_lines():
    for setting in LLM_SETTINGS:
        low = system_prompt(setting).lower()
        assert "style lines" in low
    assert "Patient seen in follow-up. Medications and history reviewed" not in system_prompt("copy_forward")


# --- exemplars ------------------------------------------------------------------------------------------------------

def test_there_are_six_exemplars_per_setting_each_distinct():
    for setting in LLM_SETTINGS:
        notes = exemplars(setting)
        assert len(notes) == EXEMPLAR_COUNT and len(set(notes)) == EXEMPLAR_COUNT


def test_exemplars_are_clean_original_fictional_text():
    from data_gen.llm.checks import _CO_DENIES, _META

    for setting in LLM_SETTINGS:
        for note in exemplars(setting):
            assert claims_scan(note) == [], note
            assert scan_text(note) == [], note  # no identifier-shaped strings or denylisted facility names
            assert not _META.search(note) and not _CO_DENIES.search(note), note
            assert 10 <= len(note.split()) <= 160


def test_exemplar_flags_are_consistent_with_the_reference_ranges():
    from data_gen.labs import LAB_BY_KEY

    checked = 0
    for note in exemplars("ehr_template"):
        for line in note.splitlines():
            for m in re.finditer(r"([A-Za-z-]+(?: [A-Za-z-]+)? \((\w{3})\)):? ([\d.]+) [^()]*\((?:(H|L), )?ref ([\d.]+)-([\d.]+)\)", line):
                value, flag, lo, hi = float(m.group(3)), m.group(4), float(m.group(5)), float(m.group(6))
                expect = "H" if value > hi else "L" if value < lo else None
                assert flag == expect, (line, value, flag, expect)
                checked += 1
    assert checked >= 8  # the pattern really found the exemplars' lab lines


def test_a_note_that_copies_an_exemplar_is_rejected(plans):
    plan = plans["ehr_template"][0]
    sample = exemplars("ehr_template")[0]
    assert exemplar_errors(sample, plan) == ["exemplar_copied"]
    assert "exemplar_copied" in offline_errors(sample, plan)
    assert exemplar_errors("A completely different note about nothing in common with those.", plan) == []


def test_stock_lines_the_traits_ask_for_are_not_counted_as_copying(plans):
    for setting in ("ehr_template", "copy_forward"):
        for plan in plans[setting]:
            lines = stock_lines(setting, plan.traits)
            for line in lines:
                assert exemplar_errors(f"{line} Something else entirely follows here today.", plan) == []


def test_changing_an_exemplar_changes_the_prompt_hash(monkeypatch):
    import data_gen.llm.prompts as pr

    before = prompt_text_hash("shorthand")
    monkeypatch.setitem(pr._exemplar_cache, "shorthand", exemplars("shorthand")[:-1] + ["changed"])
    assert prompt_text_hash("shorthand") != before


# --- the variety metric ------------------------------------------------------------------------------------------------

def test_opener_and_report():
    assert opener("Patient seen in follow-up. More.") == "patient seen in"
    notes = ["Patient seen in follow-up."] * 5 + [f"Visit {i} note." for i in range(5)]
    report = variety_report("copy_forward", notes, [{"a": str(i)} for i in range(10)])
    assert report["top_opener"] == "patient seen in" and report["top_opener_share"] == 0.5
    assert not report["passed"]  # 50% is above the 35% limit
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet".split()
    varied = variety_report("copy_forward", [f"{w} text here." for w in words], [{"a": str(i)} for i in range(10)])
    assert varied["passed"] and varied["distinct_trait_combos"] == 10


def test_the_limits_are_below_the_round_zero_baseline():
    baseline = {"copy_forward": 1.0, "ehr_template": 0.70}
    for setting, share in baseline.items():
        assert MAX_TOP_OPENER_SHARE[setting] < share
    # AI scribe notes follow a template and share a first heading by design, so their limit is looser
    assert MAX_TOP_OPENER_SHARE["ai_scribe"] > MAX_TOP_OPENER_SHARE["ehr_template"]


# --- the ambient AI scribe setting matches what such tools produce ----------------------------------------------------

def test_ai_scribe_is_a_structured_third_person_note_not_a_transcript_or_a_quoted_conversation():
    low = system_prompt("ai_scribe").lower()
    for needle in ("not a transcript", "third person", "under headings", "paraphrases the patient instead of quoting",
                   "only what was discussed", "full words, not abbreviations", "never as a table"):
        assert needle in low, needle
    for plan in [plan_of(i, "ai_scribe") for i in range(60)]:
        assert not any(s.quote for s in plan.symptoms)  # no patient quotes
        assert "layout" in plan.traits and plan.traits["layout"] in {"soap", "hpi", "summary", "plain"}
    exemplar_text = " ".join(exemplars("ai_scribe"))
    assert '"' not in exemplar_text and "c/o" not in exemplar_text and "pt " not in exemplar_text.lower()
    assert sum("The patient" in e or "the patient" in e or "They" in e for e in exemplars("ai_scribe")) == EXEMPLAR_COUNT


def test_the_ai_scribe_layouts_cover_headed_and_plain_notes(plans):
    layouts = Counter(p.traits["layout"] for p in plans["ai_scribe"])
    assert set(layouts) == {"soap", "hpi", "summary", "plain"}
    assert max(layouts.values()) / len(plans["ai_scribe"]) <= 0.5


def test_copy_forward_openers_are_literal_stock_lines_that_the_copy_check_allows(plans):
    seen = set()
    for plan in plans["copy_forward"]:
        line = stock_lines("copy_forward", plan.traits)
        assert any(l in {"Seen in clinic for follow-up.", "Return visit.", "Follow-up note.", "Interval visit."} for l in line)
        seen.update(l for l in line)
    assert {"Seen in clinic for follow-up.", "Return visit.", "Follow-up note.", "Interval visit."} <= seen
