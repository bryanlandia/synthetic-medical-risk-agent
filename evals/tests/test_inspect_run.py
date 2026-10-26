import json

import pytest

from evals.ledger import FinalRunRequired
from evals.runner import run_suites
from evals.systems import FloorSystem, LabOnlySystem, OracleSystem
from evals.transcripts import GRADER_NAMES, failure_sample, format_failure, read_transcripts, write_transcripts

REQUIRED = {"record_id", "system_version", "trial_index", "raw_output", "report", "errors", "input_tokens",
            "output_tokens", "latency_s", "graders", "suite", "split", "harness_version", "dataset_config_hash"}


@pytest.fixture(scope="module")
def oracle_run(dataset, tmp_path_factory):
    return run_suites(dataset, OracleSystem(dataset), "dev", log_dir=tmp_path_factory.mktemp("logs"))


def test_the_oracle_and_floor_run_end_to_end_on_dev_through_inspect_with_no_model(dataset, oracle_run, tmp_path):
    assert oracle_run.suites["happy_path"] == 500 and {"data_quality", "borderline"} <= set(oracle_run.suites)
    assert all(log.status == "success" for log in oracle_run.logs)
    for log in oracle_run.logs:
        assert log.eval.model.startswith("mockllm") and log.results.total_samples == oracle_run.suites[log.eval.task]
    floor = run_suites(dataset, FloorSystem(dataset), "dev", log_dir=tmp_path)
    assert all(log.status == "success" for log in floor.logs) and floor.suites == oracle_run.suites


def test_inspect_scores_agree_with_the_graders(dataset, oracle_run):
    by_task = {log.eval.task: log for log in oracle_run.logs}
    happy = by_task["happy_path"].results.scores[0].metrics["mean"].value  # the mean squared error is the Brier score
    from evals.metrics import brier
    import numpy as np

    trials = oracle_run.sink.trials["happy_path"]
    y = np.array([dataset.record(i).ground_truth.label for i in trials])
    p = np.array([ts[0].report.probability for ts in trials.values()])
    assert happy == pytest.approx(brier(y, p), abs=1e-6)
    for name in ("data_quality", "borderline"):
        assert by_task[name].results.scores[0].metrics["mean"].value == 1.0  # the oracle passes every record


def test_a_system_built_to_fail_scores_lower_than_the_oracle(dataset, tmp_path):
    run = run_suites(dataset, FloorSystem(dataset), "dev", suites=["data_quality", "borderline"], log_dir=tmp_path)
    scores = {log.eval.task: log.results.scores[0].metrics["mean"].value for log in run.logs}
    assert scores["data_quality"] < 0.2 and scores["borderline"] < 1.0


def test_protected_splits_need_the_final_flag_through_the_runner(dataset, tmp_path):
    with pytest.raises(FinalRunRequired):
        run_suites(dataset, OracleSystem(dataset), "test", log_dir=tmp_path, ledger_path=tmp_path / "ledger.json")
    run = run_suites(dataset, OracleSystem(dataset), "adversarial", suites=["adversarial"], limit=10, final=True,
                     log_dir=tmp_path, ledger_path=tmp_path / "ledger.json")
    assert json.loads((tmp_path / "ledger.json").read_text())["entries"][0]["split"] == "adversarial"
    assert run.logs[0].results.scores[0].metrics["mean"].value == 1.0  # the oracle resists every injection


def test_consistency_runs_one_sample_per_matched_pair_group(dataset, tmp_path):
    run = run_suites(dataset, OracleSystem(dataset), "test", suites=["consistency"], limit=20, final=True,
                     log_dir=tmp_path, ledger_path=tmp_path / "ledger.json")
    assert run.logs[0].results.total_samples > 0
    assert run.logs[0].results.scores[0].metrics["mean"].value == 0.0  # the oracle's spread is zero
    assert all(len(ts) % 4 == 0 for ts in run.sink.trials["consistency"].values())


# --- 5.2 transcripts ------------------------------------------------------------------------------------------------

def test_every_trial_has_a_complete_transcript(oracle_run, tmp_path):
    n_trials = len(oracle_run.sink.all_trials())
    path = write_transcripts(oracle_run.rows, tmp_path / "trials.jsonl")
    rows = read_transcripts(path)
    assert len(rows) == n_trials  # the number of trials equals the number of transcripts
    for row in rows:
        assert REQUIRED <= set(row), REQUIRED - set(row)
        assert row["system_version"] == "oracle@1" and row["raw_output"]
    scored = [r for r in rows if r.get("variant") != "addendum_removed"]
    assert all(set(r["graders"]) >= {"parse", "safety", "fabrication", "symptom_reading"} for r in scored)
    assert all(r["graders"]["parse"]["passed"] for r in scored)


def test_trials_are_recorded_per_epoch(dataset, tmp_path):
    run = run_suites(dataset, FloorSystem(dataset), "dev", suites=["happy_path"], limit=5, trials=3, log_dir=tmp_path)
    rows = run.rows
    assert len(rows) == 15 and sorted({r["trial_index"] for r in rows}) == [0, 1, 2]


# --- 5.3 failure sampling -------------------------------------------------------------------------------------------

def test_failure_sampling_is_seeded_and_names_the_reason(dataset, tmp_path):
    run = run_suites(dataset, FloorSystem(dataset), "dev", suites=["data_quality"], log_dir=tmp_path)
    rows = run.rows
    failing = [r for r in rows if not r["graders"]["data_quality"]["passed"]]
    assert len(failing) >= 10  # the floor never warns, so every record with a warning fails
    first = failure_sample(rows, "data_quality", n=10, seed=1)
    assert len(first) == 10 and first == failure_sample(rows, "data_quality", n=10, seed=1)
    assert first != failure_sample(rows, "data_quality", n=10, seed=2)
    assert all(not r["graders"]["data_quality"]["passed"] for r in first)
    text = format_failure(first[0], "data_quality")
    assert "truth=" in text and first[0]["sample_id"] in text
    with pytest.raises(ValueError):
        failure_sample(rows, "nonsense")
    assert failure_sample(rows, "symptom_reading", n=3, seed=1)  # the floor reads no symptoms either
