import inspect

import pytest

from data_gen import DISEASE_NAME
from data_gen.cohort import sample_features
from data_gen.config import LLM_SETTINGS, GenConfig
from data_gen.injections import all_texts
from data_gen.labs import LAB_BY_KEY, SYMPTOM_BY_KEY
from data_gen.llm.prompts import (ADDENDUM_MARKER, EXEMPLAR_INTRO, MarkerError, build_prompt, display_value, finalize_note,
                                  prompt_text_hash)
from data_gen.plan import CASE_TYPES, plan_note
from data_gen.render import ADDENDUM
from data_gen.rule import LAB_WEIGHTS
from data_gen.schema import NotePlanV2
from data_gen.seeds import rng_for

CFG = GenConfig(note_source="llm", seed=9)
# Words that must appear nowhere in a prompt (rule and ground-truth material).
FORBIDDEN = ("true_probability", "probability", "ground", "scoring", "intercept", "coefficient",
             "weight", "prevalence", "Velorin-Kessler", "syndrome")
# Words that must not appear in the plan-facts message (the rules text may say "do not state a risk").
FORBIDDEN_IN_FACTS = ("label", "risk", "diagnos", "probab")


def plan_for_case(i, case=None):
    labs, flags = sample_features(rng_for(CFG.seed, "features", i))
    return plan_note(CFG, labs, flags, rng_for(CFG.seed, "noise", i), case).plan


@pytest.fixture(scope="module")
def plans():
    out = [plan_for_case(i) for i in range(300)]
    out += [plan_for_case(1000 + i, c) for i, c in enumerate(CASE_TYPES * 20)]
    return out


def test_builder_takes_only_a_plan():
    assert list(inspect.signature(build_prompt).parameters) == ["plan"]


def test_each_setting_has_its_own_system_prompt_and_hash():
    hashes = {s: prompt_text_hash(s) for s in LLM_SETTINGS}
    assert len(set(hashes.values())) == 4
    systems = {build_prompt(next(p for p in [plan_for_case(i) for i in range(60)] if p.style == s)).system
               for s in LLM_SETTINGS}
    assert len(systems) == 4


def test_prompts_contain_no_ground_truth_or_rule_material(plans):
    for plan in plans:
        pr = build_prompt(plan)
        text = (pr.system + "\n" + pr.user).lower()
        for word in FORBIDDEN:
            assert word.lower() not in text, (word, plan.style)
        for word in FORBIDDEN_IN_FACTS:
            assert word not in pr.user.lower(), (word, plan.style)
        for key in LAB_WEIGHTS:
            assert key not in text
        assert DISEASE_NAME.lower() not in text
        # injection text is never shown to the model
        assert not any(t.lower() in text for t in all_texts())


def facts_of(user: str) -> str:
    """The part of the user message that states the plan; the exemplar notes after it are about other patients."""
    return user.split(EXEMPLAR_INTRO)[0]


def test_user_prompt_states_exactly_the_plan_facts(plans):
    for plan in plans[:150]:
        user = facts_of(build_prompt(plan).user)
        for lab in plan.labs:
            assert LAB_BY_KEY[lab.lab].name in user and f"{display_value(lab.value)} {lab.unit}" in user
        stated_names = {LAB_BY_KEY[l.lab].name for l in plan.labs}
        for key, lab in LAB_BY_KEY.items():
            if lab.name not in stated_names:
                assert lab.name not in user
        for s in plan.symptoms:
            assert all(f'"{p}"' in user for p in s.phrases)
        stated_flags = {s.flag for s in plan.symptoms}
        for key, sym in SYMPTOM_BY_KEY.items():
            if key not in stated_flags:
                assert not any(f'"{p}"' in user for p in sym.phrases)


def test_flags_and_ranges_appear_only_when_the_plan_has_them(plans):
    for plan in plans:
        user = facts_of(build_prompt(plan).user)
        assert ("reference" in user) == any(l.ref_range for l in plan.labs)
        assert ("flag H" in user or "flag L" in user) == any(l.flag for l in plan.labs)


def test_polarity_words_follow_the_plan(plans):
    for plan in plans[:150]:
        user = facts_of(build_prompt(plan).user)
        for stated, word in (("present", "- present:"), ("hedged", "- possible (uncertain):"), ("negated", "- denied:")):
            assert (word in user) == any(s.stated == stated for s in plan.symptoms)


# --- 3.2 injection insertion --------------------------------------------------------------------

def test_marker_is_requested_only_for_injection_plans(plans):
    for plan in plans:
        assert (ADDENDUM_MARKER in build_prompt(plan).user) == (plan.injection is not None)


def test_catalog_text_is_inserted_verbatim():
    plan = next(p for p in (plan_for_case(2000 + i, "prompt_injection") for i in range(30)))
    out = finalize_note(f"Pt seen.\n{ADDENDUM_MARKER}\n", plan)
    assert plan.injection.text in out
    assert out.endswith(plan.injection.text) and f"\n{ADDENDUM} " in out
    assert ADDENDUM_MARKER not in out


def test_plans_without_injection_yield_none():
    plan = next(p for p in (plan_for_case(i) for i in range(30)) if p.injection is None)
    assert finalize_note("A clean note.", plan) == "A clean note."
    assert not any(t in finalize_note("A clean note.", plan) for t in all_texts())


@pytest.mark.parametrize("bad", ["no marker here", f"{ADDENDUM_MARKER} early then more text",
                                 f"x {ADDENDUM_MARKER}\n{ADDENDUM_MARKER}"])
def test_missing_or_misplaced_marker_is_an_error(bad):
    plan = next(p for p in (plan_for_case(2100 + i, "prompt_injection") for i in range(30)))
    with pytest.raises(MarkerError):
        finalize_note(bad, plan)


def test_stray_marker_on_a_clean_plan_is_an_error():
    plan = next(p for p in (plan_for_case(i) for i in range(30)) if p.injection is None)
    with pytest.raises(MarkerError):
        finalize_note(f"note {ADDENDUM_MARKER}", plan)


# --- found by the first real pilot: the model invented flags and review-of-systems negatives ----------------------------

def test_prompts_forbid_inventing_flags_and_unlisted_review_of_systems_entries():
    from data_gen.llm.prompts import system_prompt

    ehr = system_prompt("ehr_template").lower()
    assert "never add a flag" in ehr and "do not add a system" in ehr
    for setting in LLM_SETTINGS:
        assert "do not interpret any lab result" in system_prompt(setting).lower()


# --- the tells a clinician reviewer rejected (round 0): precision, padding, c/o denies, fiction -------------------------------

@pytest.mark.parametrize("value,shown", [(4.199, "4.2"), (30.93, "30.9"), (0.6902, "0.69"), (315.0, "315"),
                                         (55.04, "55"), (106.9, "107"), (1234.5, "1230"), (3.031, "3.03"), (0.05, "0.05")])
def test_lab_values_are_shown_the_way_a_lab_report_prints_them(value, shown):
    assert display_value(value) == shown
    assert abs(float(shown) - value) <= 0.005 * abs(value) + 1e-9  # inside the 1% the checks allow, so notes still pass


def test_no_prompt_value_has_more_than_three_significant_figures(plans):
    import re
    for plan in plans[:200]:
        for line in build_prompt(plan).user.splitlines():
            if "(abbreviation " in line:
                number = re.search(r": (-?[\d.]+) ", line).group(1)
                assert len(number.replace("-", "").replace(".", "").lstrip("0")) <= 3, line


def test_prompts_ask_for_one_wording_per_symptom_and_never_mention_fiction():
    from data_gen.config import LLM_SETTINGS
    from data_gen.llm.prompts import system_prompt

    for setting in LLM_SETTINGS:
        low = system_prompt(setting).lower()
        assert "exactly one" in low and "mention that symptom once" in low
        assert "never restate the same finding" in low
        assert "in a study" not in low  # the old opening line the model echoed as "fictional study condition"
    assert 'never write "c/o denies"' in system_prompt("shorthand").lower()
    assert "never \"c/o denies\"" in system_prompt("copy_forward").lower()
