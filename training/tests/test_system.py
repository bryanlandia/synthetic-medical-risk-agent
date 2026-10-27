import json
import shutil
from pathlib import Path

import pytest
from evals.cli import build_parser
from evals.runner import run_suites

from training import eval_cli
from training.system import ClassifierSystem

MODEL = Path(__file__).resolve().parents[1] / "model"


def parse(*argv):
    return build_parser().parse_args(["run", "--system", "classifier", *argv])


def test_the_system_is_not_a_reference_and_names_the_model_and_the_logic(tmp_path):
    system = ClassifierSystem(MODEL)
    assert system.name == "classifier" and system.reference is False
    assert system.version.startswith("classifier@") and "+r" in system.version
    assert system.model_hash == json.loads((MODEL / "manifest.json").read_text())["model_hash"]


def test_a_dev_run_through_the_harness_writes_valid_reports(dataset, tmp_path, capsys):
    code = eval_cli.cmd_run(parse("--split", "dev", "--limit", "30", "--out", str(tmp_path / "out")), dataset, MODEL)
    assert code == 0
    rows = [json.loads(line) for line in (tmp_path / "out" / "trials.jsonl").read_text().splitlines()]
    assert rows and all(r["graders"]["parse"]["passed"] and r["graders"]["fabrication"]["passed"]
                        and r["graders"]["safety"]["passed"] for r in rows)
    info = json.loads((tmp_path / "out" / "run.json").read_text())
    assert info["stage"] == "dev" and info["system_version"] == ClassifierSystem(MODEL).version


def test_three_trials_are_identical(dataset, tmp_path):
    run = run_suites(dataset, ClassifierSystem(MODEL), "dev", suites=["happy_path"], limit=25, trials=3,
                     log_dir=tmp_path / "logs", workers=1)
    by_record = {}
    for row in run.rows:
        by_record.setdefault(row["sample_id"], []).append((row["trial_index"], row["raw_output"]))
    assert len(by_record) == 25
    for outputs in by_record.values():
        assert sorted(t for t, _ in outputs) == [0, 1, 2]
        assert len({raw for _, raw in outputs}) == 1


@pytest.mark.parametrize("split", ["test", "adversarial"])
def test_a_protected_split_is_refused_without_a_frozen_model(dataset, tmp_path, split, capsys):
    model = tmp_path / "model"
    shutil.copytree(MODEL, model)
    (model / eval_cli.FROZEN_NAME).unlink(missing_ok=True)
    code = eval_cli.cmd_run(parse("--split", split, "--final", "--out", str(tmp_path / "out")), dataset, model)
    assert code == 2 and "frozen" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_protected_split_needs_the_final_flag_even_when_frozen(dataset, tmp_path, capsys):
    model = tmp_path / "model"
    shutil.copytree(MODEL, model)
    system = ClassifierSystem(model)
    (model / eval_cli.FROZEN_NAME).write_text(json.dumps({"model_hash": system.model_hash, "system_version": system.version}))
    code = eval_cli.cmd_run(parse("--split", "test", "--out", str(tmp_path / "out")), dataset, model)
    assert code == 2 and "--final" in capsys.readouterr().err and not (tmp_path / "out").exists()
