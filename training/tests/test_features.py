import numpy as np
import pytest
from data_gen import labs as gen

from risk_model import features
from risk_model.labs import LABS, SYMPTOM_KEYS

MEANS = np.array([lab.mean for lab in LABS], dtype=float)
SDS = np.array([lab.sd for lab in LABS], dtype=float)


def view(**overrides):
    panel = [{"lab": lab.key, "value": lab.mean, "unit": lab.unit} for lab in LABS]
    for entry in panel:
        if entry["lab"] in overrides:
            entry.update(overrides[entry["lab"]])
    return {"patient_id": "P1", "panel": panel, "note": "n"}


def test_the_lab_copy_matches_the_generators():
    assert [(l.key, l.name, l.abbr, l.unit, l.mean, l.sd, l.ref_lo, l.ref_hi, l.plaus_lo, l.plaus_hi, l.alt_unit, l.factor)
            for l in LABS] == [(l.key, l.name, l.abbr, l.unit, l.mean, l.sd, l.ref_lo, l.ref_hi, l.plaus_lo, l.plaus_hi,
                                l.alt_unit, l.factor) for l in gen.LABS]
    assert SYMPTOM_KEYS == gen.SYMPTOM_KEYS


@pytest.mark.parametrize("key", ["ground_truth", "label", "split", "plan", "true_probability"])
def test_a_ground_truth_key_is_rejected_by_name(key):
    bad = {**view(), key: 1}
    with pytest.raises(ValueError, match=key):
        features.build(bad, {}, MEANS, SDS)


def test_a_panel_entry_with_extra_fields_is_rejected():
    bad = view()
    bad["panel"][0]["flag"] = "H"
    with pytest.raises(ValueError, match="flag"):
        features.panel_values(bad)


def test_typical_values_are_zero_and_nothing_is_missing():
    x = features.build(view(), {}, MEANS, SDS)
    assert len(x) == len(features.FEATURE_NAMES) == 26
    assert np.allclose(x, 0.0)


def test_a_null_value_sits_at_the_mean_with_its_indicator_on():
    x = features.build(view(serum_k17={"value": None}), {}, MEANS, SDS)
    names = features.FEATURE_NAMES
    assert x[names.index("z:serum_k17")] == 0.0 and x[names.index("missing:serum_k17")] == 1.0
    assert x[names.index("missing:velorin_index")] == 0.0


@pytest.mark.parametrize("bad", [-100.0, 1000.0, 0.0])
def test_an_impossible_value_is_treated_as_missing(bad):
    x = features.build(view(velorin_index={"value": bad}), {}, MEANS, SDS)
    assert x[features.FEATURE_NAMES.index("missing:velorin_index")] == 1.0
    assert x[features.FEATURE_NAMES.index("z:velorin_index")] == 0.0
    assert features.panel_values(view(velorin_index={"value": bad}))["velorin_index"] is None


def test_an_alternate_panel_unit_is_converted_before_use():
    lab = gen.LAB_BY_KEY["serum_k17"]
    usual = features.build(view(serum_k17={"value": 5.0}), {}, MEANS, SDS)
    alt = features.build(view(serum_k17={"value": lab.to_alt(5.0), "unit": "mg/dL"}), {}, MEANS, SDS)
    assert np.allclose(usual, alt)


def test_symptom_levels_become_indicator_columns():
    x = features.build(view(), {"tremor": "present", "fatigue": "possible", "dizziness": "absent",
                                "photophobia": "not_mentioned"}, MEANS, SDS)
    names = features.FEATURE_NAMES
    assert x[names.index("tremor:present")] == 1 and x[names.index("fatigue:possible")] == 1
    assert x[names.index("dizziness:present")] == 0 and x[names.index("photophobia:possible")] == 0
