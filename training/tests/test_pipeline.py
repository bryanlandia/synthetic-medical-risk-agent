import json

import pytest

from risk_model.classifier import RiskClassifier
from training import pipeline, tracking


@pytest.fixture(scope="module")
def runs(dataset, tmp_path_factory):
    root = tmp_path_factory.mktemp("runs")
    out = {}
    for name in ("a", "b"):
        out[name] = (root / name, pipeline.train(root / name, root / "mlruns", n_boot=30, dataset=dataset))
    out["tracking"] = root / "mlruns"
    return out


def test_two_runs_with_the_same_seed_give_identical_model_files(runs):
    (a, _), (b, _) = runs["a"], runs["b"]
    for name in ("reader.json", "classifier.json", "metrics.json", "manifest.json", "reader_report.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    assert json.loads((a / "manifest.json").read_text())["model_hash"] == pipeline.model_hash(b)


def test_a_different_seed_changes_the_model_files_and_is_recorded(runs, dataset, tmp_path, monkeypatch):
    from training import classifier_fit as cf

    grid = cf.load_grid()
    monkeypatch.setattr(cf, "load_grid", lambda path=cf.GRID_PATH: {**grid, "seed": 7})
    pipeline.train(tmp_path / "s", None, n_boot=30, dataset=dataset)
    other = json.loads((tmp_path / "s" / "manifest.json").read_text())
    base_dir = runs["a"][0]
    assert other["seed"] == 7 and json.loads((base_dir / "manifest.json").read_text())["seed"] == 0
    assert other["model_hash"] != json.loads((base_dir / "manifest.json").read_text())["model_hash"]
    assert (tmp_path / "s" / "classifier.json").read_bytes() != (base_dir / "classifier.json").read_bytes()


def test_every_run_is_tracked_with_its_parameters_metrics_and_model_files(runs):
    out, result = runs["a"]
    run_id = json.loads((out / "run.json").read_text())["mlflow_run_id"]
    got = tracking.read_run(runs["tracking"], run_id)
    m = result["manifest"]
    assert got["status"] == "FINISHED"
    assert got["params"]["seed"] == "0" and got["params"]["model_hash"] == m["model_hash"]
    assert got["params"]["dataset_config_hash"] == m["dataset_config_hash"]
    assert got["params"]["train_ids_sha256"] == m["train_ids_sha256"]
    for key in ("dev_auc", "dev_brier", "dev_log_loss", "dev_ece", "dev_reader_accuracy"):
        assert key in got["metrics"]
    assert {"reader.json", "classifier.json", "metrics.json", "manifest.json"} <= set(got["artifacts"])


def test_the_dev_requirements_hold(runs):
    s = runs["a"][1]["summary"]
    p = s["probability_percentiles"]
    assert p["5"] <= s["spread_requirement"]["p5_at_most"] and p["95"] >= s["spread_requirement"]["p95_at_least"]
    assert s["dev"]["ece"]["value"] <= 0.0643
    assert set(s["against_targets"]) == {"auc", "brier", "log_loss", "ece"}
    assert all(row["label"] in ("clearly met", "clearly not met", "not distinguishable") for row in s["against_targets"].values())


def test_the_choice_and_all_candidate_scores_are_recorded_and_the_gbm_is_not_served(runs):
    out, result = runs["a"]
    s = result["summary"]
    assert len(s["candidates"]) == 9 and s["chosen"]["c"] == min(s["candidates"], key=lambda c: (c["dev_log_loss"], c["c"]))["c"]
    assert s["gbm_diagnostic"]["served"] is False
    assert not (out / "gbm.json").exists() and set(json.loads((out / "manifest.json").read_text())["files"]) == {
        "reader.json", "classifier.json", "reader_report.json", "metrics.json"}
    clf = RiskClassifier(json.loads((out / "classifier.json").read_text()))  # the served file loads in numpy alone
    assert clf.coef.shape == (len(clf.means) * 2 + 10,)
