import itertools
from pathlib import Path

import numpy as np
import pytest

import risk_model
from risk_model import features, sensitivity
from risk_model.labs import LAB_BY_KEY, LAB_KEYS, SYMPTOM_KEYS

MODEL = Path(__file__).resolve().parents[2] / "training" / "model"
ALL_STATED = "Tremor present. Fatigue present. Denies photophobia. Denies joint stiffness. Denies dizziness."


@pytest.fixture(scope="module")
def model():
    return risk_model.load(MODEL)


def view(labs=LAB_KEYS, note=ALL_STATED, **overrides):
    panel = [{"lab": k, "value": overrides.get(k, LAB_BY_KEY[k].mean), "unit": LAB_BY_KEY[k].unit} for k in labs]
    return {"patient_id": "P", "panel": panel, "note": note}


def solve(model, v):
    reading = model.reader.read(v["note"]).readings
    x = model.classifier.vector(v, reading)
    p = float(1 / (1 + np.exp(-model.classifier.logit(x))))
    return reading, x, p


def brute_force(model, v):
    """Lowest and highest probability over {as recorded, each plausible end} for every unmeasured item, built feature by feature."""
    clf = model.classifier
    reading, x, _ = solve(model, v)
    options = []
    for kind, key in sensitivity.unmeasured(v, reading):
        if kind == "lab":
            lab, i = LAB_BY_KEY[key], LAB_KEYS.index(key)
            ends = [max(lab.mean - 2 * lab.sd, lab.plaus_lo), min(lab.mean + 2 * lab.sd, lab.plaus_hi)]
            states = [{}] + [{f"z:{key}": (e - clf.means[i]) / clf.sds[i], f"missing:{key}": 0.0} for e in ends]
        else:
            states = [{}, {f"{key}:present": 1.0}, {f"{key}:possible": 1.0}]
        options.append(states)
    ps = []
    for combo in itertools.product(*options):
        y = x.copy()
        for state in combo:
            for name, value in state.items():
                y[features.FEATURE_NAMES.index(name)] = value
        ps.append(1 / (1 + np.exp(-clf.logit(y))))
    return min(ps), max(ps)


def test_the_platt_slope_keeps_the_order_of_the_logit(model):
    assert model.classifier.platt is None or model.classifier.platt[0] > 0


def test_a_complete_record_has_a_point_range_and_no_gaps(model):
    v = view()
    reading, x, p = solve(model, v)
    assert all(r != "not_mentioned" for r in reading.values())
    interval, gaps = sensitivity.analyse(model.classifier, v, reading, x)
    assert interval == [p, p] and gaps == []


def test_a_missing_lab_widens_the_range_and_brackets_the_probability(model):
    v = view(labs=[k for k in LAB_KEYS if k != "tarnic_acid"])
    reading, x, p = solve(model, v)
    (lo, hi), gaps = sensitivity.analyse(model.classifier, v, reading, x)
    assert lo <= p <= hi and hi - lo > 0.01
    assert [(g["kind"], g["key"]) for g in gaps] == [("lab", "tarnic_acid")]
    assert (gaps[0]["low"], gaps[0]["high"]) == (lo, hi)


@pytest.mark.parametrize("labs,note", [
    (LAB_KEYS[:7], ALL_STATED),
    (LAB_KEYS[:5], ALL_STATED),
    (LAB_KEYS[:4], "Tremor present. Fatigue present. Denies photophobia."),
    (LAB_KEYS[:2], "Tremor possible. Denies dizziness."),
    (LAB_KEYS[:6], ""),
    (LAB_KEYS[3:5], "Fatigue present."),
])
def test_the_bounds_match_a_brute_force_search(model, labs, note):
    v = view(labs=labs, note=note, velorin_index=140.0)
    reading, x, p = solve(model, v)
    assert len(sensitivity.unmeasured(v, reading)) <= 10
    (lo, hi), _ = sensitivity.analyse(model.classifier, v, reading, x)
    want_lo, want_hi = brute_force(model, v)
    assert lo == pytest.approx(want_lo, abs=1e-9) and hi == pytest.approx(want_hi, abs=1e-9)
    assert lo <= p <= hi


def test_the_range_includes_leaving_a_lab_unmeasured_even_when_every_value_would_raise_the_estimate(model):
    v = view(labs=[k for k in LAB_KEYS if k != "osmet_level"])  # the Osmet value term is near zero: any value adds to the logit
    reading, x, p = solve(model, v)
    (lo, hi), gaps = sensitivity.analyse(model.classifier, v, reading, x)
    assert lo == p and hi > p
    assert gaps[0]["low"] == p


def test_a_missing_plexa_count_reads_lower_than_a_typical_one(model):
    without = view(labs=[k for k in LAB_KEYS if k != "plexa_count"])
    _, _, p_missing = solve(model, without)
    _, _, p_typical = solve(model, view())
    assert p_typical > p_missing
    reading, x, _ = solve(model, without)
    (_, hi), _ = sensitivity.analyse(model.classifier, without, reading, x)
    assert hi >= p_typical - 1e-12


def test_an_impossible_value_counts_as_unmeasured(model):
    v = view(velorin_index=1280.0)  # shifted by a power of ten
    reading, x, p = solve(model, v)
    (lo, hi), gaps = sensitivity.analyse(model.classifier, v, reading, x)
    assert [(g["kind"], g["key"]) for g in gaps] == [("lab", "velorin_index")]
    assert lo <= p <= hi


def test_gaps_name_only_unmeasured_items_largest_swing_first_and_flag_routing(model):
    v = view(labs=LAB_KEYS[:3], note="Tremor possible.")
    reading, x, p = solve(model, v)
    _, gaps = sensitivity.analyse(model.classifier, v, reading, x)
    measured = set(LAB_KEYS[:3]) | {s for s in SYMPTOM_KEYS if reading[s] != "not_mentioned"}
    assert gaps and not {g["key"] for g in gaps} & measured
    swings = [g["high"] - g["low"] for g in gaps]
    assert swings == sorted(swings, reverse=True)
    for g in gaps:
        assert 0 <= g["low"] <= p <= g["high"] <= 1
        crosses = sensitivity.routing(g["low"]) != sensitivity.routing(p) or sensitivity.routing(g["high"]) != sensitivity.routing(p)
        assert g["changes_routing"] == crosses


def report_for(model, **kw):
    return model.report(view(**kw))


def test_a_complete_record_reports_a_point_range_and_says_nothing_is_missing(model):
    r = report_for(model)
    assert r["interval"] == [r["probability"], r["probability"]] and r["gaps"] == []
    assert any("does not depend on unmeasured findings" in e for e in r["evidence"])


def test_a_wide_range_names_its_width_and_the_largest_swing(model):
    r = report_for(model, labs=LAB_KEYS[:2], note="")
    lo, hi = r["interval"]
    assert hi - lo > 0.3
    top = r["gaps"][0]
    statements = [e for e in r["evidence"] if "anywhere from" in e]
    assert len(statements) == 1
    assert f"{lo:.0%} to {hi:.0%}" in statements[0] and f"{top['low']:.0%} to {top['high']:.0%}" in statements[0]


def test_a_narrow_range_says_the_missing_findings_would_not_change_much(model):
    r = report_for(model, labs=[k for k in LAB_KEYS if k != "osmet_level"], velorin_index=60.0, tarnic_acid=150.0, dorrin_ratio=0.4)
    lo, hi = r["interval"]
    assert hi - lo < 0.05 and r["gaps"]
    assert any("would not change the result much" in e for e in r["evidence"])


def test_recorded_values_are_untouched_and_evidence_stays_within_the_contract(model):
    v = view(labs=LAB_KEYS[:5], note="Tremor possible.", velorin_index=125.5)
    r = model.report(v)
    given = {e["lab"]: e["value"] for e in v["panel"]}
    assert {e["lab"]: e["value"] for e in r["labs_used"]} == given
    assert not {g["key"] for g in r["gaps"]} & set(given)
    assert 1 <= len(r["evidence"]) <= 8 and all(len(e) <= 300 for e in r["evidence"])
    confidence = [e for e in r["evidence"] if "findings not on the record" in e or "different band" in e or "missing" in e]
    assert 1 <= len(confidence) <= 2


def test_the_logic_version_names_the_new_report_fields():
    assert risk_model.LOGIC_VERSION == "2"
