import json

import pytest

from data_gen.builder import build_dataset, build_record
from data_gen.cohort import build_patient
from data_gen.config import GenConfig
from data_gen.injections import all_texts, categories, catalog_version, entries
from data_gen.labs import LAB_BY_KEY
from data_gen.plan import CASE_TYPES
from data_gen.rule import calibrated_intercept, true_probability
from data_gen.validate import dataset_errors


@pytest.fixture(scope="module")
def ds():
    return build_dataset(GenConfig(n_train=600, n_test=150, n_per_adversarial_type=60))


def by_type(adv):
    return {c: [r for r in adv if c in r.tag_types()] for c in CASE_TYPES}


# --- 4.1 case-type generators -------------------------------------------------

def test_at_least_50_records_per_case_type(ds):
    for case, recs in by_type(ds["adversarial"]).items():
        assert len(recs) >= 50, case


def test_adversarial_ids_are_opaque(ds):
    for r in ds["adversarial"]:
        assert not any(c in r.patient_id for c in CASE_TYPES)
        assert not any(c in json.dumps(r.input_view()) for c in CASE_TYPES)


def test_borderline_cases(ds):
    for r in by_type(ds["adversarial"])["borderline"]:
        assert 0.4 <= r.ground_truth.true_probability <= 0.6


def test_impossible_values_only_in_adversarial_and_tagged(ds):
    for r in by_type(ds["adversarial"])["impossible_value"]:
        tag = next(t for t in r.tags if t.type == "impossible_value")
        lab = LAB_BY_KEY[tag.lab]
        entry = next(e for e in r.input.panel if e.lab == tag.lab)
        assert entry.value == tag.detail["recorded"]
        assert not lab.plaus_lo <= entry.value <= lab.plaus_hi
        assert lab.plaus_lo <= r.ground_truth.labs[tag.lab] <= lab.plaus_hi  # ground truth stays valid
    for split in ("train", "test"):
        for r in ds[split]:
            for e in r.input.panel:
                if e.value is not None:
                    lab = LAB_BY_KEY[e.lab]
                    assert lab.plaus_lo <= e.value <= lab.plaus_hi
            assert not r.tags


def test_missing_labs_cases(ds):
    for r in by_type(ds["adversarial"])["missing_labs"]:
        n_missing = sum(e.value is None for e in r.input.panel)
        assert 2 <= n_missing <= 4


def test_unit_mismatch_cases(ds):
    for r in by_type(ds["adversarial"])["unit_mismatch"]:
        tagged = [t for t in r.tags if t.type == "unit_mismatch"]
        assert tagged
        for t in tagged:
            lab = LAB_BY_KEY[t.lab]
            written = next(l for l in r.plan.labs if l.lab == t.lab)
            assert written.unit == lab.alt_unit == t.detail["unit_written"]
            assert lab.from_alt(written.value) == pytest.approx(r.ground_truth.labs[t.lab], rel=0.01)


def test_contradiction_cases(ds):
    for r in by_type(ds["adversarial"])["contradiction"]:
        t = next(t for t in r.tags if t.type == "contradiction")
        assert abs(t.detail["stated"] - t.detail["true"]) > 0.3 * t.detail["true"]
        assert r.ground_truth.labs[t.lab] == t.detail["true"]  # structured value unchanged


def test_flag_disagreement_cases(ds):
    for r in by_type(ds["adversarial"])["note_flag_disagreement"]:
        for t in (t for t in r.tags if t.type == "note_flag_disagreement"):
            stated = next(s.stated for s in r.plan.symptoms if s.flag == t.flag)
            truth = r.ground_truth.flags[t.flag]
            assert (stated == "negated") if truth else (stated == "present")
            assert t.detail["direction"] == ("says_absent_when_present" if truth else "says_present_when_absent")


def test_flag_disagreement_and_injection_only_in_adversarial(ds):
    for split in ("train", "test"):
        for r in ds[split]:
            assert "note_flag_disagreement" not in r.tag_types() | r.noise_types()
            assert "prompt_injection" not in r.tag_types() | r.noise_types()


def test_full_dataset_validation_passes(ds):
    assert dataset_errors(ds) == []


# --- 4.2 injection catalog -----------------------------------------------------

def test_catalog_is_versioned_and_diverse():
    assert catalog_version()
    cats = categories()
    assert len(cats) >= 3
    assert {"override_risk_output", "request_treatment_advice"} <= cats
    assert len({e.id for e in entries()}) == len(entries())


def test_injection_text_is_verbatim_from_catalog(ds):
    inj = by_type(ds["adversarial"])["prompt_injection"]
    assert len(inj) >= 50
    seen_cats = set()
    for r in inj:
        tag = next(t for t in r.tags if t.type == "prompt_injection")
        assert r.plan.injection.text in r.input.note
        assert r.plan.injection.text in all_texts()
        assert tag.detail["category"] == r.plan.injection.category
        assert tag.detail["goal"]
        seen_cats.add(tag.detail["category"])
    assert len(seen_cats) >= 3
    assert {"override_risk_output", "request_treatment_advice"} <= seen_cats


def test_no_catalog_text_outside_injection_notes(ds):
    for r in ds["train"] + ds["test"]:
        assert not any(t in r.input.note for t in all_texts())


def test_injection_does_not_change_labels():
    cfg = GenConfig(n_train=20, n_test=5)
    ic = calibrated_intercept(cfg.target_prevalence)
    patient = build_patient(cfg.seed, 3, ic)
    clean = build_record(cfg, patient, "train", None)
    injected = build_record(cfg, patient, "adversarial", "prompt_injection")
    assert clean.ground_truth == injected.ground_truth
    assert injected.ground_truth.true_probability == pytest.approx(
        true_probability(patient.labs, patient.flags, ic))
