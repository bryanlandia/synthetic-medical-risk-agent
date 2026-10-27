import json
import shutil
import types
import warnings
from pathlib import Path

import pytest
from evals.cli import build_parser
from evals.ledger import record_final_run

from training import eval_cli
from training.system import ClassifierSystem

MODEL = Path(__file__).resolve().parents[1] / "model"


def parse(*argv):
    return build_parser().parse_args(["run", "--system", "classifier", *argv])


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the model, a private results folder and ledger, and a stand-in for the harness run: the ledger is
    written as the real run would, and no protected record is read."""
    model = tmp_path / "model"
    shutil.copytree(MODEL, model)
    (model / eval_cli.FROZEN_NAME).unlink(missing_ok=True)
    monkeypatch.setattr(eval_cli, "RESULTS_DIR", tmp_path / "results")
    ledger = tmp_path / "ledger.json"
    calls = []

    def fake_run_suites(dataset, system, split, **kw):
        calls.append(split)
        record_final_run(system.version, split, final=kw["final"], path=kw["ledger_path"], stage=kw["ledger_stage"])
        return types.SimpleNamespace(rows=[], stopped=None)

    monkeypatch.setattr(eval_cli, "run_suites", fake_run_suites)
    monkeypatch.setattr(eval_cli, "summarize", lambda *a, **k: {"rows": []})
    monkeypatch.setattr(eval_cli, "write_summary", lambda *a, **k: None)
    monkeypatch.setattr(eval_cli, "write_transcripts", lambda *a, **k: None)
    monkeypatch.setattr(eval_cli, "render_markdown", lambda *a, **k: "")
    return types.SimpleNamespace(model=model, ledger=ledger, calls=calls, results=tmp_path / "results")


def write_dev_run(sandbox, version=None):
    d = sandbox.results / "dev"
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(json.dumps({"system_version": version or ClassifierSystem(sandbox.model).version}))


def test_freezing_needs_a_dev_run_of_this_exact_model(sandbox):
    with pytest.raises(eval_cli.NotFrozen, match="dev first"):
        eval_cli.freeze(sandbox.model)
    write_dev_run(sandbox, "classifier@000000000000+r1")
    with pytest.raises(eval_cli.NotFrozen, match="dev first"):
        eval_cli.freeze(sandbox.model)
    write_dev_run(sandbox)
    entry = eval_cli.freeze(sandbox.model)
    assert json.loads((sandbox.model / eval_cli.FROZEN_NAME).read_text()) == entry
    assert entry["model_hash"] == ClassifierSystem(sandbox.model).model_hash


def test_a_changed_model_is_not_the_frozen_one(sandbox, capsys):
    write_dev_run(sandbox)
    eval_cli.freeze(sandbox.model)
    reader = json.loads((sandbox.model / "reader.json").read_text())
    reader["conflict_rule"] = "last" if reader["conflict_rule"] == "confident" else "confident"
    (sandbox.model / "reader.json").write_text(json.dumps(reader, sort_keys=True, separators=(",", ":")) + "\n")
    code = eval_cli.cmd_run(parse("--split", "test", "--final"), None, sandbox.model, ledger_path=sandbox.ledger)
    assert code == 2 and "must use the frozen model" in capsys.readouterr().err and sandbox.calls == []


def test_the_second_final_run_is_refused_unless_forced_and_a_forced_run_is_recorded_and_warned(sandbox, capsys):
    write_dev_run(sandbox)
    eval_cli.freeze(sandbox.model)
    args = ("--split", "test", "--final", "--out", str(sandbox.results / "test"))
    assert eval_cli.cmd_run(parse(*args), None, sandbox.model, ledger_path=sandbox.ledger) == 0
    assert sandbox.calls == ["test"]
    assert eval_cli.cmd_run(parse(*args), None, sandbox.model, ledger_path=sandbox.ledger) == 2
    assert "second look" in capsys.readouterr().err and sandbox.calls == ["test"]
    with pytest.warns(UserWarning, match="2 times"):
        assert eval_cli.cmd_run(parse(*args, "--force"), None, sandbox.model, ledger_path=sandbox.ledger) == 0
    entries = json.loads(sandbox.ledger.read_text())["entries"]
    assert [e["run"] for e in entries] == [1, 2] and {e["split"] for e in entries} == {"test"}


def test_adversarial_and_the_repeated_trials_are_their_own_looks(sandbox):
    write_dev_run(sandbox)
    eval_cli.freeze(sandbox.model)
    for argv in (("--split", "test"), ("--split", "adversarial"), ("--split", "test", "--suites", "consistency", "--trials", "3")):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert eval_cli.cmd_run(parse(*argv, "--final", "--out", str(sandbox.results / "x")), None, sandbox.model,
                                    ledger_path=sandbox.ledger) == 0
    stages = sorted((e["split"], e.get("stage")) for e in json.loads(sandbox.ledger.read_text())["entries"])
    assert stages == [("adversarial", "adversarial"), ("test", "test"), ("test", "trials")]
