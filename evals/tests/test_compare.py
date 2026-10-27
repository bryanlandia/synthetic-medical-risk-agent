import json
import types

import numpy as np
import pytest

from evals import compare


def fake_dataset(n=300, seed=0, pairs=False):
    rng = np.random.default_rng(seed)
    recs = {}
    for i in range(n):
        group = f"G{i // 4}" if pairs else None
        recs[f"R{i:04d}"] = types.SimpleNamespace(
            patient_id=f"R{i:04d}", pair_group=group, ground_truth=types.SimpleNamespace(label=int(rng.random() < 0.4)))
    return types.SimpleNamespace(record=lambda rid: recs[rid]), recs


def rows_for(recs, prob, suite="happy_path", trial=0):
    return [{"suite": suite, "trial_index": trial, "record_id": rid,
             "report": None if prob(r) is None else {"status": "scored", "probability": prob(r)}}
            for rid, r in recs.items()]


def informative(r):
    return 0.8 if r.ground_truth.label else 0.2


def flat(r):
    return 0.4


def test_a_known_difference_is_found_with_its_direction_and_an_interval_that_excludes_zero():
    ds, recs = fake_dataset()
    out = compare.paired(rows_for(recs, informative), rows_for(recs, flat), ds, "good", "flat")
    by = {r["metric"]: r for r in out["rows"]}
    assert out["patients"] == 300
    assert by["auc"]["diff"] > 0.4 and by["auc"]["lo"] > 0 and by["auc"]["verdict"] == "good is better"
    assert by["brier"]["diff"] < 0 and by["brier"]["hi"] < 0 and by["brier"]["verdict"] == "good is better"
    assert by["log_loss"]["verdict"] == "good is better"


def test_the_order_decides_who_is_better():
    ds, recs = fake_dataset()
    out = compare.paired(rows_for(recs, flat), rows_for(recs, informative), ds, "flat", "good")
    assert {r["verdict"] for r in out["rows"]} == {"good is better"}


def test_identical_systems_differ_by_zero_and_are_not_distinguishable():
    ds, recs = fake_dataset()
    rows = rows_for(recs, informative)
    out = compare.paired(rows, rows, ds, "a", "b")
    for r in out["rows"]:
        assert r["diff"] == 0 and r["lo"] == 0 and r["hi"] == 0 and r["verdict"] == "not distinguishable"


def test_an_invalid_report_counts_as_the_neutral_probability_and_unshared_patients_are_left_out():
    ds, recs = fake_dataset(n=40)
    a = rows_for(recs, informative)
    b = rows_for(recs, lambda r: None)
    b = [row for row in b if row["record_id"] != "R0000"]
    out = compare.paired(a, b, ds, "a", "b")
    assert out["patients"] == 39 and out["only_a"] == 1 and out["only_b"] == 0
    brier_b = {r["metric"]: r for r in out["rows"]}["brier"]["b"]
    assert brier_b == pytest.approx(0.25)  # every probability is 0.5


def test_matched_pair_members_count_once_and_only_the_first_trial_and_the_happy_path_suite_are_read():
    ds, recs = fake_dataset(n=40, pairs=True)
    rows = rows_for(recs, informative) + rows_for(recs, flat, suite="borderline") + rows_for(recs, flat, trial=1)
    probs = compare.probabilities(rows, ds)
    assert len(probs) == 10 and all(p in (0.2, 0.8) for _, p, _ in probs.values())


def test_no_shared_patients_is_an_error():
    ds, recs = fake_dataset(n=10)
    a = rows_for({k: v for k, v in list(recs.items())[:5]}, informative)
    b = rows_for({k: v for k, v in list(recs.items())[5:]}, informative)
    with pytest.raises(ValueError, match="share no"):
        compare.paired(a, b, ds)


def test_stage_dir_resolves_both_systems(tmp_path):
    (tmp_path / "dev" / "v3_claude-haiku-5-5").mkdir(parents=True)
    (tmp_path / "dev" / "v5_claude-haiku-5-5").mkdir(parents=True)
    assert compare.stage_dir("classifier", "test", root=tmp_path) == tmp_path / "test"
    assert compare.stage_dir("frontier", "test", "haiku", root=tmp_path) == tmp_path / "claude-haiku-5-5" / "test"
    assert compare.stage_dir("frontier", "dev", "haiku", root=tmp_path).name == "v5_claude-haiku-5-5"
    with pytest.raises(ValueError):
        compare.stage_dir("nobody", "test")


def test_the_report_text_has_a_row_per_metric_and_the_notice():
    ds, recs = fake_dataset()
    out = compare.paired(rows_for(recs, informative), rows_for(recs, flat), ds, "a", "b")
    text = compare.render(out, "a", "b", "test", None, ("a@1", "b@1"))
    assert "ALL DATA IS SYNTHETIC" in text and all(m in text for m in ("auc", "brier", "log_loss")) and "a@1" in text
