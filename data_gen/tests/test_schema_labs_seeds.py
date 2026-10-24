import json

import pytest
from pydantic import ValidationError

from data_gen import DISEASE_NAME
from data_gen.labs import LABS, REAL_TEST_DENYLIST, SYMPTOMS
from data_gen.schema import GroundTruth, LabEntry, ModelInput, Record
from data_gen.seeds import adversarial_patient_id, cohort_patient_id, rng_for


def make_record(**overrides):
    base = dict(
        seed=1,
        patient_id="P1-000000",
        split="train",
        style="terse",
        input=ModelInput(
            patient_id="P1-000000",
            panel=[LabEntry(lab="velorin_index", value=101.0, unit="mg/dL")],
            note="Pt c/o fatigue.",
        ),
        ground_truth=GroundTruth(
            labs={"velorin_index": 101.0},
            flags={"fatigue": True},
            true_probability=0.4,
            label=1,
        ),
    )
    base.update(overrides)
    return Record(**base)


# --- 2.1 schema -----------------------------------------------------------

def test_valid_record_accepted_and_marked_synthetic():
    rec = make_record()
    assert rec.synthetic is True
    assert rec.disease == DISEASE_NAME
    assert "FICTIONAL" in rec.disease.upper()
    assert "synthetic" in rec.notice.lower()


@pytest.mark.parametrize(
    "overrides",
    [
        {"split": "validation"},
        {"synthetic": False},
        {"ground_truth": dict(labs={}, flags={}, true_probability=1.2, label=1)},
        {"ground_truth": dict(labs={}, flags={}, true_probability=-0.1, label=0)},
        {"ground_truth": dict(labs={}, flags={}, true_probability=0.5, label=2)},
        {"unknown_field": 1},
    ],
)
def test_invalid_records_rejected(overrides):
    with pytest.raises(ValidationError):
        make_record(**overrides)


def test_input_view_has_no_ground_truth():
    view = make_record().input_view()
    text = json.dumps(view).lower()
    for forbidden in ("flags", "true_probability", "label", "ground_truth"):
        assert forbidden not in text
    assert set(view) == {"patient_id", "panel", "note"}


def test_input_model_rejects_extra_ground_truth_fields():
    with pytest.raises(ValidationError):
        ModelInput(patient_id="x", panel=[], note="n", label=1)


# --- 2.2 labs -------------------------------------------------------------

def test_lab_count_in_bounds():
    assert 6 <= len(LABS) <= 10


def test_lab_names_are_fictional():
    for lab in LABS:
        for real in REAL_TEST_DENYLIST:
            assert real not in lab.name.lower(), (lab.name, real)
            assert real != lab.abbr.lower()


def test_lab_definitions_are_consistent():
    keys = [lab.key for lab in LABS]
    assert len(set(keys)) == len(keys)
    for lab in LABS:
        assert lab.plaus_lo < lab.ref_lo < lab.mean < lab.ref_hi < lab.plaus_hi
        assert (lab.alt_unit is None) == (lab.factor is None)
        if lab.factor is not None:
            assert lab.from_alt(lab.to_alt(lab.mean)) == pytest.approx(lab.mean)
    assert sum(lab.alt_unit is not None for lab in LABS) >= 3


def test_symptoms_defined():
    assert len(SYMPTOMS) >= 3
    assert all(0 < s.base_rate < 1 for s in SYMPTOMS)


# --- 2.3 seeds ------------------------------------------------------------

def test_rng_deterministic_and_independent_per_key():
    a = rng_for(7, "features", 3).random(5)
    assert (a == rng_for(7, "features", 3).random(5)).all()
    assert not (a == rng_for(8, "features", 3).random(5)).all()
    assert not (a == rng_for(7, "features", 4).random(5)).all()
    assert not (a == rng_for(7, "labels", 3).random(5)).all()


def test_rng_rejects_negative_inputs():
    with pytest.raises(ValueError):
        rng_for(-1, "features", 0)


def test_ids_do_not_collide_across_seeds_or_kinds():
    ids = {cohort_patient_id(s, i) for s in range(5) for i in range(200)}
    ids |= {adversarial_patient_id(s, i) for s in range(5) for i in range(200)}
    assert len(ids) == 5 * 200 * 2
    assert "-A" not in cohort_patient_id(1, 1)
