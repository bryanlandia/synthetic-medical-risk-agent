import itertools
import math
from pathlib import Path

import numpy as np
import pytest

import risk_model
from risk_model import EstimateError, features, intake
from risk_model import estimate as est
from risk_model.labs import LAB_BY_KEY, LAB_KEYS, LABS, SYMPTOM_KEYS

MODEL = Path(__file__).resolve().parents[2] / "training" / "model"


@pytest.fixture(scope="module")
def model():
    return risk_model.load(MODEL)


def random_inputs(rng, n):
    for _ in range(n):
        labs = {}
        for lab in LABS:
            if rng.random() < 0.2:
                labs[lab.key] = None
            else:
                labs[lab.key] = float(rng.uniform(lab.plaus_lo, lab.plaus_hi))
        yield labs, {k: str(rng.choice(est.STATES)) for k in SYMPTOM_KEYS}


def test_the_probability_is_the_classifiers_for_the_same_inputs(model):
    rng = np.random.default_rng(0)
    for labs, symptoms in random_inputs(rng, 500):
        out = model.estimate(labs, symptoms)
        values, states = est.check(labs, symptoms)
        view = est._view(values, out["message"])
        assert abs(out["probability"] - model.classifier.probability(view, states)) < 1e-9
        assert out["band"] in est.BANDS


def test_the_bars_and_the_start_add_up_to_the_score(model):
    rng = np.random.default_rng(1)
    for labs, symptoms in random_inputs(rng, 500):
        out = model.estimate(labs, symptoms)
        total = out["start"] + sum(row["contribution"] for row in out["breakdown"])
        assert abs(total - out["score"]) < 1e-6
        assert abs(1 / (1 + math.exp(-total)) - out["probability"]) < 1e-6
        assert [r["key"] for r in out["breakdown"]] == [*LAB_KEYS, *SYMPTOM_KEYS]


def test_a_not_done_lab_carries_the_missing_indicator_and_a_possible_symptom_its_own_column(model):
    clf = model.classifier
    scale = clf.platt[0]
    labs = {k: LAB_BY_KEY[k].mean for k in LAB_KEYS}
    labs["plexa_count"] = None
    symptoms = {k: "absent" for k in SYMPTOM_KEYS}
    symptoms["tremor"] = "possible"
    out = model.estimate(labs, symptoms)
    rows = {r["key"]: r["contribution"] for r in out["breakdown"]}
    names = features.FEATURE_NAMES
    assert rows["plexa_count"] == pytest.approx(clf.coef[names.index("missing:plexa_count")] * scale + 0.0, abs=0.05)
    assert rows["tremor"] == pytest.approx(clf.coef[names.index("tremor:possible")] * scale)
    assert rows["fatigue"] == 0.0


def test_grouped_bars_equal_the_per_feature_contributions_summed_by_input(model):
    rng = np.random.default_rng(2)
    clf = model.classifier
    for labs, symptoms in random_inputs(rng, 50):
        out = model.estimate(labs, symptoms)
        values, states = est.check(labs, symptoms)
        parts = clf.contributions(clf.vector(est._view(values, out["message"]), states))
        assert sum(r["contribution"] for r in out["breakdown"]) == pytest.approx(float(parts.sum()), abs=1e-9)


def test_inputs_outside_the_limits_are_refused(model):
    labs = {k: LAB_BY_KEY[k].mean for k in LAB_KEYS}
    symptoms = {k: "absent" for k in SYMPTOM_KEYS}
    bad = [
        ({**labs, "velorin_index": 1040.0}, symptoms), ({**labs, "velorin_index": -1.0}, symptoms),
        ({**labs, "velorin_index": "100"}, symptoms), ({**labs, "velorin_index": True}, symptoms),
        ({**labs, "velorin_index": float("nan")}, symptoms),
        ({k: v for k, v in labs.items() if k != "serum_k17"}, symptoms), ({**labs, "extra": 1.0}, symptoms),
        (labs, {**symptoms, "tremor": "not_mentioned"}), (labs, {k: v for k, v in symptoms.items() if k != "tremor"}),
        (labs, {**symptoms, "extra": "present"}), ([], symptoms), (labs, None),
    ]
    for case in bad:
        with pytest.raises(EstimateError):
            model.estimate(*case)


def test_the_ends_of_the_plausible_range_are_allowed(model):
    for end in ("plaus_lo", "plaus_hi"):
        labs = {k: getattr(LAB_BY_KEY[k], end) for k in LAB_KEYS}
        model.estimate(labs, {k: "present" for k in SYMPTOM_KEYS})


def test_the_same_inputs_give_the_same_message_and_a_not_done_lab_is_left_out(model):
    rng = np.random.default_rng(3)
    for labs, symptoms in random_inputs(rng, 50):
        a, b = model.estimate(labs, symptoms)["message"], model.estimate(labs, symptoms)["message"]
        assert a == b
        for lab in LABS:
            assert (lab.name in a) == (labs[lab.key] is not None)


def test_the_message_has_nothing_but_the_inputs():
    labs = {k: None for k in LAB_KEYS}
    labs["serum_k17"] = 4.25
    symptoms = {k: "absent" for k in SYMPTOM_KEYS}
    symptoms["tremor"], symptoms["fatigue"] = "present", "possible"
    assert est.message(est.check(labs, symptoms)[0], symptoms) == (
        "Labs:\n- Serum K-17 (K17): 4.2 mmol/L\n\nNote:\nOn review, reports tremor.\nOn review, possible fatigue.\n"
        "On review, denies photophobia.\nOn review, denies joint stiffness.\nOn review, denies dizziness.")
    nothing = est.message({k: None for k in LAB_KEYS}, symptoms)
    assert nothing.startswith("Labs: none reported.\n\nNote:")


def read_back(model, labs, symptoms):
    out = model.estimate(labs, symptoms)
    view = intake.view_from_text(out["message"])
    reading = model.reader.read(view["note"])
    return out, view, reading


def check_round_trip(model, labs, symptoms):
    out, view, reading = read_back(model, labs, symptoms)
    values, _ = est.check(labs, symptoms)
    for entry in view["panel"]:
        want = values[entry["lab"]]
        assert (entry["value"] is None) if want is None else entry["value"] == pytest.approx(want, abs=1e-9), entry["lab"]
    assert {k: reading.readings[k] for k in SYMPTOM_KEYS} == symptoms
    assert abs(model.report(view)["probability"] - out["probability"]) < 0.001

def test_every_symptom_combination_reads_back_with_every_one_of_200_seeded_lab_settings(model):
    rng = np.random.default_rng(4)
    settings = [labs for labs, _ in random_inputs(rng, 200)]
    combos = [dict(zip(SYMPTOM_KEYS, c)) for c in itertools.product(est.STATES, repeat=len(SYMPTOM_KEYS))]
    assert len(combos) == 243 and sum(any(v is None for v in s.values()) for s in settings) > 100  # many settings have labs not done
    for symptoms in combos:
        for labs in settings:
            check_round_trip(model, labs, symptoms)



def test_the_extremes_read_back(model):
    symptoms = {k: "possible" for k in SYMPTOM_KEYS}
    for labs in ({k: LAB_BY_KEY[k].plaus_lo for k in LAB_KEYS}, {k: LAB_BY_KEY[k].plaus_hi for k in LAB_KEYS}, {k: None for k in LAB_KEYS}):
        check_round_trip(model, labs, symptoms)
