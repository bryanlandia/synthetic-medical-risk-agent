import json

import pytest

from evals.runner import run_suites
from evals.summary import render_markdown, summarize, write_summary
from evals.systems import FloorSystem, LabOnlySystem, OracleSystem


@pytest.fixture(scope="module")
def runs(dataset, tmp_path_factory):
    logs = tmp_path_factory.mktemp("logs")
    ledger = tmp_path_factory.mktemp("ledger") / "ledger.json"
    out = {}
    for system in (OracleSystem(dataset), FloorSystem(dataset), LabOnlySystem(dataset)):
        out[system.name] = run_suites(dataset, system, "dev", log_dir=logs, ledger_path=ledger)
    return out


def metrics(summary):
    return {(r["category"], r["metric"]): r for r in summary["rows"]}


def test_the_summary_has_a_row_per_metric_with_interval_n_and_mdd(dataset, runs):
    summary = summarize(dataset, runs["oracle"], n_boot=200)
    got = metrics(summary)
    for key in [("happy_path", "auc"), ("happy_path", "brier"), ("happy_path", "ece"), ("symptom_reading", "accuracy"),
                ("data_quality", "exact_match"), ("borderline", "uncertain_rate"), ("fabrication", "rate"),
                ("safety", "pass_rate"), ("parse", "failure_rate")]:
        assert key in got, key
    for row in summary["rows"]:
        assert row["lo"] <= row["value"] <= row["hi"] or row["lo"] == row["hi"]
        assert row["n"] >= row["patients"] > 0 and row["mdd"] >= 0
    assert summary["harness_version"] and summary["dataset_config_hash"] == dataset.config_hash
    assert "synthetic" in summary["notice"].lower() and "fictional" in summary["notice"].lower()
    assert got[("symptom_reading", "accuracy")]["value"] == 1.0 and got[("safety", "pass_rate")]["value"] == 1.0


def test_the_baselines_are_ordered_as_the_design_expects(dataset, runs):
    oracle, floor, lab = (metrics(summarize(dataset, runs[n], n_boot=200)) for n in ("oracle", "floor", "lab_only"))
    assert floor[("happy_path", "auc")]["value"] == 0.5
    assert 0.55 < lab[("happy_path", "auc")]["value"] < oracle[("happy_path", "auc")]["value"]
    assert oracle[("happy_path", "brier")]["value"] < lab[("happy_path", "brier")]["value"] < floor[("happy_path", "brier")]["value"] + 0.01
    assert oracle[("data_quality", "exact_match")]["value"] == 1.0 and floor[("data_quality", "exact_match")]["value"] < 0.5
    assert lab[("symptom_reading", "accuracy")]["value"] < oracle[("symptom_reading", "accuracy")]["value"]


def test_the_markdown_is_readable_and_the_files_are_written(dataset, runs, tmp_path):
    summary = summarize(dataset, runs["lab_only"], n_boot=100)
    text = render_markdown(summary)
    assert text.startswith("# Results: lab_only@1 on dev") and "ALL DATA IS SYNTHETIC" in text
    assert "| happy_path | auc |" in text and "MDD" in text and "A reference system" in text
    js, md = write_summary(summary, tmp_path / "out")
    assert json.loads(js.read_text())["system_version"] == "lab_only@1" and md.read_text() == text


def test_summaries_are_reproducible(dataset, runs):
    a = summarize(dataset, runs["lab_only"], n_boot=150, seed=3)
    b = summarize(dataset, runs["lab_only"], n_boot=150, seed=3)
    assert a == b


def test_a_test_split_summary_includes_consistency_and_adversarial(dataset, tmp_path):
    run = run_suites(dataset, OracleSystem(dataset), "test", suites=["happy_path", "consistency", "borderline"],
                     limit=80, final=True, log_dir=tmp_path, ledger_path=tmp_path / "ledger.json")
    adv = run_suites(dataset, OracleSystem(dataset), "adversarial", suites=["adversarial"], limit=20, final=True,
                     log_dir=tmp_path, ledger_path=tmp_path / "ledger2.json")
    got = metrics(summarize(dataset, run, n_boot=100))
    assert got[("consistency", "mean_sd")]["value"] == 0.0 and got[("consistency", "pass_rate")]["value"] == 1.0
    assert metrics(summarize(dataset, adv, n_boot=100))[("adversarial", "resistance_rate")]["value"] == 1.0
