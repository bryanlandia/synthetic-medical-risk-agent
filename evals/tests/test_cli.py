import json

import pytest

from evals.cli import main
from evals.systems import OracleSystem


def test_run_writes_transcripts_and_a_summary(dataset, tmp_path, capsys):
    out = tmp_path / "run"
    code = main(["run", "--system", "floor", "--split", "dev", "--suites", "happy_path", "borderline", "--limit", "25",
                 "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 0 and "| happy_path | auc |" in text and "ALL DATA IS SYNTHETIC" in text
    rows = [json.loads(line) for line in (out / "trials.jsonl").read_text().splitlines()]
    assert len(rows) > 25 and (out / "summary.json").exists() and (out / "summary.md").exists()


def test_run_on_a_protected_split_needs_the_final_flag(dataset, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("evals.ledger.LEDGER_PATH", tmp_path / "ledger.json")
    code = main(["run", "--system", "oracle", "--split", "test", "--suites", "happy_path", "--limit", "5", "--out", str(tmp_path / "o")])
    assert code == 2 and "--final" in capsys.readouterr().err
    assert not (tmp_path / "ledger.json").exists()


def test_the_failures_command_prints_a_seeded_sample(dataset, tmp_path, capsys):
    out = tmp_path / "run"
    main(["run", "--system", "floor", "--split", "dev", "--suites", "data_quality", "--out", str(out)])
    capsys.readouterr()
    assert main(["failures", str(out / "trials.jsonl"), "--grader", "data_quality", "-n", "4", "--seed", "2"]) == 0
    printed = capsys.readouterr().out
    assert "4 failing transcripts for data_quality" in printed and printed.count("--- data_quality") == 4


def test_the_regression_subset_passes_on_the_committed_baselines(dataset, capsys):
    assert main(["regression"]) == 0
    assert "passed" in capsys.readouterr().out


def test_the_regression_subset_fails_when_the_oracle_misses_its_ceiling(dataset, capsys, monkeypatch):
    original = OracleSystem.run

    def off(self, view):
        report = original(self, view)
        return {**report, "probability": min(1.0, max(0.0, report["probability"] * 0.8 + 0.1))}  # a shrunken oracle

    monkeypatch.setattr(OracleSystem, "run", off)
    assert main(["regression"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err and "ceiling" in err and "happy_path" in err
