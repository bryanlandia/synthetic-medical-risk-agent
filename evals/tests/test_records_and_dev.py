import json
import warnings

import pytest

from evals.devsplit import DEV_SIZE, dev_ids, train_ids
from evals.ledger import FinalRunRequired, final_runs, record_final_run
from evals.records import SPLITS, assert_clean_view, categories, input_view, patient_key

FORBIDDEN = ("ground_truth", "flags", "true_probability", "label", "tags", "noise", "plan", "split", "style",
             "pair_group", "symptom", "injection")


# --- 2.1 the input view ----------------------------------------------------------------------------------------

def test_the_view_of_every_record_of_every_split_contains_no_answers(dataset):
    n = 0
    for split in SPLITS:
        for record in dataset.by_split[split]:
            view = input_view(record)
            assert set(view) == {"patient_id", "panel", "note"}
            blob = json.dumps({k: v for k, v in view.items() if k != "note"})  # keys and numbers, not prose
            for word in FORBIDDEN:
                assert word not in blob, (record.patient_id, word)
            n += 1
    assert n == sum(len(v) for v in dataset.by_split.values()) > 5000


def test_a_view_with_an_extra_field_is_rejected():
    with pytest.raises(ValueError, match="must not see"):
        assert_clean_view({"patient_id": "p", "panel": [], "note": "", "label": 1})
    with pytest.raises(ValueError, match="unexpected"):
        assert_clean_view({"patient_id": "p", "panel": [{"lab": "x", "value": 1.0, "unit": "u", "flag": True}], "note": ""})


def test_categories_follow_tags_noise_and_pairs(dataset):
    seen: set[str] = set()
    for split in SPLITS:
        for record in dataset.by_split[split]:
            cats = categories(record)
            seen |= cats
            if record.split == "test":
                assert "happy_path" in cats
            if record.pair_group:
                assert "consistency" in cats
            for tag in record.tags:
                assert {"missing_labs": "data_quality", "borderline": "borderline",
                        "prompt_injection": "adversarial"}.get(tag.type, "data_quality") in cats
    assert {"happy_path", "data_quality", "borderline", "adversarial", "consistency"} <= seen
    both = [r for r in dataset.by_split["adversarial"] if {"unit_mismatch", "borderline"} <= r.tag_types()]
    for r in both:  # a record can belong to more than one category
        assert {"data_quality", "borderline"} <= categories(r)


def test_matched_pair_members_share_a_patient_key(dataset):
    groups: dict[str, set[str]] = {}
    for r in dataset.by_split["test"]:
        groups.setdefault(patient_key(r), set()).add(r.patient_id)
    assert len(groups) == dataset.manifest["splits"]["test"]["n_unique_patients"]
    assert max(len(v) for v in groups.values()) == 4


# --- 2.2 the dev split ---------------------------------------------------------------------------------------------

def test_the_dev_split_is_deterministic_and_stratified(dataset):
    first, second = dev_ids(dataset), dev_ids(dataset)
    assert first == second and len(first) == len(set(first)) == DEV_SIZE
    others = {r.patient_id for s in ("test", "adversarial") for r in dataset.by_split[s]}
    assert not set(first) & others
    label = {r.patient_id: r.ground_truth.label for r in dataset.by_split["train"]}
    assert set(first) <= set(label)
    prevalence = sum(label.values()) / len(label)
    dev_prevalence = sum(label[i] for i in first) / len(first)
    assert abs(dev_prevalence - prevalence) <= 0.02


def test_the_dev_draw_depends_on_the_seed(dataset):
    import copy

    other = copy.copy(dataset)
    other.manifest = {**dataset.manifest, "seed": dataset.seed + 1}
    assert dev_ids(other) != dev_ids(dataset)


def test_training_ids_exclude_dev(dataset):
    dev, train = set(dev_ids(dataset)), set(train_ids(dataset))
    assert not dev & train and dev | train == {r.patient_id for r in dataset.by_split["train"]}
    assert len(train) == len(dataset.by_split["train"]) - DEV_SIZE


def test_dev_size_cannot_exceed_train(dataset):
    with pytest.raises(ValueError):
        dev_ids(dataset, n=10_000)


# --- 2.3 final runs --------------------------------------------------------------------------------------------------

def test_protected_splits_need_the_flag_and_are_counted(tmp_path):
    ledger = tmp_path / "ledger.json"
    for split in ("test", "adversarial"):
        with pytest.raises(FinalRunRequired, match="--final"):
            record_final_run("sys@v1", split, final=False, path=ledger)
    assert not ledger.exists()  # a refused run is not recorded
    assert record_final_run("sys@v1", "dev", final=False, path=ledger) == 0  # unprotected: nothing recorded
    assert record_final_run("sys@v1", "test", final=True, path=ledger) == 1
    assert final_runs("sys@v1", "test", ledger) == 1 and final_runs("sys@v1", "adversarial", ledger) == 0
    assert json.loads(ledger.read_text())["entries"][0]["system_version"] == "sys@v1"


def test_a_second_final_run_warns_and_other_versions_start_fresh(tmp_path):
    ledger = tmp_path / "ledger.json"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        record_final_run("sys@v1", "test", final=True, path=ledger)  # the first run is silent
        record_final_run("sys@v2", "test", final=True, path=ledger)  # a new version is its own first run
    with pytest.warns(UserWarning, match="2 times"):
        assert record_final_run("sys@v1", "test", final=True, path=ledger) == 2
