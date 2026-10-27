import pytest

from evals.regression import reference_systems
from evals.runner import run_suites
from evals.summary import render_markdown, summarize
from evals.targets import CLEARLY_MET, CLEARLY_NOT_MET, NOT_DISTINGUISHABLE, attach_targets, judge, load_targets

HIGHER = {"category": "c", "metric": "m", "direction": "higher", "target": 0.70}
LOWER = {"category": "c", "metric": "brier", "direction": "lower", "target": 0.18}


@pytest.mark.parametrize("value,lo,hi,reached,label", [
    (0.80, 0.76, 0.84, True, CLEARLY_MET),
    (0.72, 0.66, 0.78, True, NOT_DISTINGUISHABLE),
    (0.60, 0.55, 0.65, False, CLEARLY_NOT_MET),
    (0.68, 0.62, 0.74, False, NOT_DISTINGUISHABLE),  # short of the target, but the target is inside the interval
    (0.70, 0.70, 0.75, True, CLEARLY_MET),  # an interval that just reaches the target
])
def test_the_three_labels_for_a_higher_is_better_metric(value, lo, hi, reached, label):
    got = judge(HIGHER, value, lo, hi)
    assert got["reached"] is reached and got["label"] == label and got["target"] == 0.70


@pytest.mark.parametrize("value,lo,hi,reached,label", [
    (0.15, 0.13, 0.17, True, CLEARLY_MET),
    (0.19, 0.17, 0.21, False, NOT_DISTINGUISHABLE),
    (0.25, 0.22, 0.28, False, CLEARLY_NOT_MET),
])
def test_direction_is_respected_for_a_lower_is_better_metric(value, lo, hi, reached, label):
    got = judge(LOWER, value, lo, hi)
    assert got["reached"] is reached and got["label"] == label


def test_rows_without_a_target_are_left_alone():
    rows = [{"category": "c", "metric": "m", "value": 0.8, "lo": 0.7, "hi": 0.9}, {"category": "x", "metric": "y",
            "value": 1.0, "lo": 1.0, "hi": 1.0}]
    attach_targets(rows, {"targets": [HIGHER]})
    assert rows[0]["label"] == CLEARLY_MET and "label" not in rows[1]


def test_a_system_under_test_is_compared_with_the_targets_file_and_a_reference_is_not(dataset, tmp_path):
    system = reference_systems(dataset)["lab_only"]
    run = run_suites(dataset, system, "dev", suites=["happy_path"], limit=200, log_dir=tmp_path)
    plain = summarize(dataset, run, n_boot=100)
    assert all("label" not in r for r in plain["rows"])
    under_test = summarize(dataset, run, n_boot=100, reference=False)
    auc = next(r for r in under_test["rows"] if r["metric"] == "auc")
    target = next(t for t in load_targets()["targets"] if t["metric"] == "auc")
    assert auc["target"] == target["target"] and auc["label"] in (CLEARLY_MET, NOT_DISTINGUISHABLE, CLEARLY_NOT_MET)
    text = render_markdown(under_test)
    assert "Against target" in text and (">= 0.7" in text) and ("not reached" in text or "reached" in text)
