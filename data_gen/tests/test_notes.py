import json
import socket
import subprocess
import sys

import numpy as np
import pytest

from data_gen.builder import build_dataset, build_record
from data_gen.cohort import build_patient, sample_features
from data_gen.config import GenConfig
from data_gen.labs import LAB_BY_KEY, LABS, SYMPTOM_KEYS
from data_gen.plan import plan_note
from data_gen.render import parse_back_errors, render
from data_gen.rule import calibrated_intercept, true_probability
from data_gen.scan import scan_text
from data_gen.seeds import rng_for


def ordinary_plans(cfg, n):
    out = []
    for i in range(n):
        labs, flags = sample_features(rng_for(cfg.seed, "features", i))
        out.append((labs, flags, plan_note(cfg, labs, flags, rng_for(cfg.seed, "noise", i))))
    return out


# --- 3.1 (completes): ground truth is independent of the note --------------------

def test_true_probability_unchanged_when_note_text_changes():
    cfg = GenConfig(n_train=50, n_test=10)
    ic = calibrated_intercept(cfg.target_prevalence)
    patient = build_patient(cfg.seed, 5, ic)
    rec = build_record(cfg, patient, "train", None)
    edited = rec.model_copy(deep=True)
    edited.input.note = "completely different text, no values at all"
    assert edited.ground_truth == rec.ground_truth
    assert rec.ground_truth.true_probability == pytest.approx(
        true_probability(rec.ground_truth.labs, rec.ground_truth.flags, ic))
    other_style = build_record(
        GenConfig(n_train=50, n_test=10, style_rates={"terse": 1.0}), patient, "train", None)
    other_style2 = build_record(
        GenConfig(n_train=50, n_test=10, style_rates={"templated": 1.0}), patient, "train", None)
    assert other_style.ground_truth == other_style2.ground_truth == rec.ground_truth


# --- 5.1 note plan & realized rates -----------------------------------------------

@pytest.fixture(scope="module")
def plans():
    cfg = GenConfig(seed=7)
    return cfg, ordinary_plans(cfg, 4000)


def test_realized_noise_and_style_rates_match_config(plans):
    cfg, items = plans
    n = len(items)
    # style
    templated = sum(p.plan.style == "templated" for _, _, p in items)
    assert abs(templated / n - cfg.style_rates["templated"]) < 0.03
    # missing: per lab
    missing = sum(len(p.missing) for _, _, p in items)
    assert abs(missing / (n * len(LABS)) - cfg.missing_rate) < 0.03
    # hedging: per present symptom
    present = sum(sum(f.values()) for _, f, _ in items)
    hedged = sum(sum(x.type == "hedging" for x in p.noise) for _, _, p in items)
    assert abs(hedged / present - cfg.hedge_rate) < 0.03
    # unit mismatch: per stated lab that has an alternate unit
    stated_alt = sum(1 for _, _, p in items for l in p.plan.labs if LAB_BY_KEY[l.lab].alt_unit)
    mism = sum(sum(x.type == "unit_mismatch" for x in p.noise) for _, _, p in items)
    assert abs(mism / stated_alt - cfg.unit_mismatch_rate) < 0.03
    # stale contradictions: per stated lab (not unit-mismatched) in templated notes
    stated_t = sum(len(p.plan.labs) - sum(x.type == "unit_mismatch" for x in p.noise)
                   for _, _, p in items if p.plan.style == "templated")
    stale = sum(sum(x.type == "contradiction" for x in p.noise)
                for _, _, p in items if p.plan.style == "templated")
    assert abs(stale / stated_t - cfg.stale_rate) < 0.03


def test_stale_values_only_in_templated_style(plans):
    _, items = plans
    for _, _, p in items:
        if p.plan.style != "templated":
            assert not any(x.type == "contradiction" for x in p.noise)


def test_missing_labs_never_stated(plans):
    _, items = plans
    for _, _, p in items:
        assert not ({l.lab for l in p.plan.labs} & p.missing)


def test_noise_metadata_matches_plan(plans):
    _, items = plans
    for labs, flags, p in items:
        for x in p.noise:
            if x.type == "unit_mismatch":
                lab = LAB_BY_KEY[x.lab]
                stated = next(l for l in p.plan.labs if l.lab == x.lab)
                assert stated.unit == x.detail["unit_written"] == lab.alt_unit
                assert x.detail["unit_canonical"] == lab.unit
                assert lab.from_alt(stated.value) == pytest.approx(labs[x.lab], rel=0.01)
            if x.type == "contradiction":
                assert x.detail["true"] == labs[x.lab]
                assert x.detail["stated"] != x.detail["true"]


def test_clean_notes_express_every_flag_faithfully(plans):
    _, items = plans
    for labs, flags, p in items:
        stated = {s.flag: s.stated for s in p.plan.symptoms}
        for key in SYMPTOM_KEYS:
            if flags[key]:
                assert stated[key] in ("present", "hedged")
            else:
                assert stated.get(key, "negated") == "negated"


# --- 5.2 deterministic offline rendering -------------------------------------------

def test_render_is_deterministic_and_offline(plans, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", no_network)
    _, items = plans
    for _, _, p in items[:300]:
        assert render(p.plan) == render(p.plan)


def test_template_path_imports_no_network_libraries():
    # A fresh interpreter, so other tests importing the SDK cannot affect the result.
    code = (
        "import sys, data_gen.builder, data_gen.render, data_gen.cli;"
        "banned = ('anthropic', 'requests', 'httpx', 'httpx2', 'urllib3', 'aiohttp');"
        "bad = [m for m in banned if m in sys.modules];"
        "sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_dataset_is_byte_identical_for_same_seed():
    cfg = GenConfig(seed=3, n_train=120, n_test=30, n_per_adversarial_type=10)

    def dump(ds):
        return json.dumps({k: [r.model_dump(mode="json") for r in v] for k, v in ds.items()}, sort_keys=True)

    assert dump(build_dataset(cfg)) == dump(build_dataset(cfg))
    assert dump(build_dataset(cfg)) != dump(build_dataset(cfg.model_copy(update={"seed": 4})))


# --- 5.3 parse-back & reserved styles --------------------------------------------------

def test_parse_back_recovers_plan_for_1000_notes(plans):
    _, items = plans
    sample = items[:1000]
    assert {p.plan.style for _, _, p in sample} == {"terse", "templated"}
    failures = [e for _, _, p in sample for e in parse_back_errors(p.plan, render(p.plan))]
    assert failures == []


def test_parse_back_detects_tampering(plans):
    _, items = plans
    _, _, p = next(x for x in items if x[2].plan.labs)
    text = render(p.plan)
    lab = p.plan.labs[0]
    bad = text.replace(f"{lab.value:.4g}", "999999", 1)
    assert parse_back_errors(p.plan, bad)


@pytest.mark.parametrize("style", ["shorthand", "ehr_template", "ai_scribe", "copy_forward"])
def test_llm_settings_are_rejected_by_template_rendering(style):
    with pytest.raises(ValueError, match="not supported by note_source 'template'"):
        GenConfig(n_train=10, n_test=5, style_rates={style: 1.0})
    labs, flags = sample_features(rng_for(1, "features", 0))
    plan = plan_note(GenConfig(), labs, flags, rng_for(1, "noise", 0)).plan
    with pytest.raises(ValueError, match="not supported by template rendering"):
        render(plan.model_copy(update={"style": style}))


@pytest.mark.parametrize("style", ["terse", "templated"])
def test_template_styles_are_rejected_by_the_llm_source(style):
    with pytest.raises(ValueError, match="not supported by note_source 'llm'"):
        GenConfig(note_source="llm", style_rates={style: 1.0})


def test_build_dataset_refuses_the_llm_source():
    with pytest.raises(ValueError, match="LLM note writer"):
        build_dataset(GenConfig(note_source="llm", n_train=10, n_test=5))


def test_style_rates_validation():
    with pytest.raises(ValueError):
        GenConfig(style_rates={"terse": 0.5, "templated": 0.4})
    with pytest.raises(ValueError):
        GenConfig(style_rates={"cuneiform": 1.0})


# --- 5.4 identifier scan -------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,finding",
    [
        ("SSN 123-45-6789 on file", "ssn"),
        ("MRN: 00482913", "mrn"),
        ("MRN 1234567", "mrn"),
        ("call 555-867-5309 today", "phone"),
        ("call (555) 867-5309 today", "phone"),
        ("seen at Mayo Clinic", "facility:mayo clinic"),
        ("email j.doe@example.com", "email"),
    ],
)
def test_scan_flags_identifier_shapes(text, finding):
    assert finding in scan_text(text)


def test_scan_passes_rendered_notes_and_catalog():
    ds = build_dataset(GenConfig(n_train=800, n_test=200, n_per_adversarial_type=20))
    for recs in ds.values():
        for r in recs:
            assert scan_text(r.input.note) == [], r.input.note
            assert r.synthetic is True
