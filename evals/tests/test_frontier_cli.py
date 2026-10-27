import json

import pytest
from data_gen.llm.client import MockClient

from evals import frontier_cli, protocol
from evals.cli import build_parser
from evals.prompt_system import prompt_hash
from evals.frontier import STAGES, load_prompt, stage_records
from evals.systems import scored_report

FAKE_KEY = "sk-" + "ant-test-secret-value-1234567890"  # built in pieces so a repository key scan stays clean


@pytest.fixture
def env(tmp_path, monkeypatch):
    client = MockClient(responder=lambda s, p: json.dumps(scored_report(json.loads(p), 0.3, uncertain=False)),
                        input_tokens=1800, output_tokens=600)
    monkeypatch.setattr(frontier_cli, "make_client", lambda: client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    paths = dict(protocol_path=tmp_path / "pv.json", out_root=tmp_path / "out", cache=tmp_path / "cache.jsonl")
    return client, paths


def parse(*argv):
    return build_parser().parse_args(list(argv))


def iterate(dataset, paths, *argv):
    return frontier_cli.cmd_iterate(parse("iterate", "--prompt", "v1", *argv), dataset, **paths)


def test_a_paid_step_without_yes_spends_nothing(dataset, env, capsys):
    client, paths = env
    assert iterate(dataset, paths, "--limit", "20") == 2
    assert client.calls == [] and "--yes" in capsys.readouterr().err
    assert not paths["protocol_path"].exists()


def test_iterate_scores_dev_records_the_version_and_writes_the_run(dataset, env):
    client, paths = env
    assert iterate(dataset, paths, "--yes", "--note", "first briefing") == 0
    assert len(client.calls) == 500
    [entry] = protocol.versions(paths["protocol_path"])
    assert entry["prompt_hash"] == prompt_hash(load_prompt("v1")) and entry["note"] == "first briefing"
    assert "happy_path.auc" in entry["metrics"] and {"value", "lo", "hi", "mdd"} <= set(entry["metrics"]["happy_path.auc"])
    assert entry["spend_usd"] == pytest.approx(500 * (1800 * 0.10 + 600 * 0.50) / 1_000_000, rel=1e-6)
    run_dir = paths["out_root"] / "dev" / "v1_claude-haiku-5-5"
    assert (run_dir / "trials.jsonl").exists() and json.loads((run_dir / "run.json").read_text())["calls_made"] == 500


def test_a_rerun_of_the_same_prompt_is_free(dataset, env):
    client, paths = env
    iterate(dataset, paths, "--yes", "--limit", "30")
    first = len(client.calls)
    assert iterate(dataset, paths, "--limit", "30") == 0  # all cached: no --yes needed, no call made
    assert len(client.calls) == first == len(stage_records(dataset, STAGES["dev"], 30)) > 30  # distinct records


def test_a_smoke_run_is_not_recorded(dataset, env):
    client, paths = env
    assert iterate(dataset, paths, "--yes", "--limit", "10") == 0
    assert protocol.versions(paths["protocol_path"]) == [] and len(client.calls) == len(
        stage_records(dataset, STAGES["dev"], 10))


def test_a_sixth_version_is_refused_before_any_call(dataset, env, capsys):
    client, paths = env
    for i in range(protocol.MAX_VERSIONS):
        protocol.record_dev_score(f"h{i}", "vx", "claude-haiku-5-5", {}, spend_usd=0.1, path=paths["protocol_path"])
    assert iterate(dataset, paths, "--yes", "--limit", "5") == 2
    assert client.calls == [] and "sixth is refused" in capsys.readouterr().err


def test_the_protected_splits_wait_for_a_freeze_and_then_run_once_with_final(dataset, env, tmp_path, capsys):
    client, paths = env
    ledger = tmp_path / "ledger.json"
    run = lambda *a: frontier_cli.cmd_run(parse("run", "--system", "frontier", "--prompt", "v1", *a), dataset,  # noqa: E731
                                          ledger_path=ledger, **paths)
    assert run("--split", "test", "--final", "--yes", "--limit", "5") == 2 and client.calls == []
    assert "frozen prompt" in capsys.readouterr().err
    iterate(dataset, paths, "--yes", "--limit", "5")  # a smoke run does not count...
    protocol.record_dev_score(prompt_hash(load_prompt("v1")), "v1", "claude-haiku-5-5", {}, spend_usd=0.1,
                              path=paths["protocol_path"])
    assert frontier_cli.cmd_freeze(parse("freeze", "--prompt", "v1"), paths["protocol_path"]) == 0
    before = len(client.calls)
    assert run("--split", "test", "--yes", "--limit", "5") == 2 and len(client.calls) == before  # --final missing
    assert run("--split", "test", "--final", "--yes", "--limit", "5", "--model", "sonnet",
               "--suites", "happy_path") == 0
    assert len(client.calls) == before + 5
    assert (paths["out_root"] / "claude-sonnet-5-5" / "test" / "trials.jsonl").exists()
    assert len(json.loads(ledger.read_text())["entries"]) == 1


def test_the_key_never_reaches_a_file(dataset, env, tmp_path):
    _, paths = env
    iterate(dataset, paths, "--yes", "--limit", "5")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert FAKE_KEY not in f.read_text(errors="ignore"), f


def test_a_missing_key_stops_a_paid_step_before_any_call(dataset, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    paths = dict(protocol_path=tmp_path / "pv.json", out_root=tmp_path / "out", cache=tmp_path / "cache.jsonl")
    assert iterate(dataset, paths, "--yes", "--limit", "5") == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err


def test_estimate_needs_no_key_and_writes_nothing(dataset, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert frontier_cli.cmd_estimate(parse("estimate", "--model", "sonnet"), dataset, cache=tmp_path / "c.jsonl") == 0
    out = capsys.readouterr().out
    assert "dev" in out and "adversarial" in out and "no key was needed" in out and not (tmp_path / "c.jsonl").exists()


def test_a_repeated_final_run_is_refused_unless_forced_and_the_trials_stage_is_its_own_look(dataset, env, tmp_path, capsys):
    client, paths = env
    ledger = tmp_path / "ledger.json"
    protocol.record_dev_score(prompt_hash(load_prompt("v1")), "v1", "claude-haiku-5-5", {}, spend_usd=0.1,
                              path=paths["protocol_path"])
    frontier_cli.cmd_freeze(parse("freeze", "--prompt", "v1"), paths["protocol_path"])
    run = lambda *a: frontier_cli.cmd_run(parse("run", "--system", "frontier", "--prompt", "v1", "--final", "--yes", *a),  # noqa: E731
                                          dataset, ledger_path=ledger, **paths)
    assert run("--split", "test", "--suites", "happy_path", "--limit", "5") == 0
    calls = len(client.calls)
    assert run("--split", "test", "--suites", "happy_path", "--limit", "5") == 2 and len(client.calls) == calls
    assert "second look" in capsys.readouterr().err
    assert run("--split", "test", "--suites", "consistency", "--trials", "3", "--limit", "5") == 0  # a different stage
    with pytest.warns(UserWarning, match="scored on test 2 times"):
        assert run("--split", "test", "--suites", "happy_path", "--limit", "5", "--force") == 0
    stages = [e.get("stage") for e in json.loads(ledger.read_text())["entries"]]
    assert stages == ["test", "trials", "test"]


def test_iterate_prints_progress_lines_and_quiet_hides_them(dataset, env, capsys):
    _, paths = env
    assert iterate(dataset, paths, "--yes", "--limit", "60") == 0
    lines = [l for l in capsys.readouterr().err.splitlines() if l.startswith("[dev v1]")]
    assert any("happy_path 25/60" in l for l in lines) and any("happy_path 60/60 (100%)" in l for l in lines)
    assert all("paid calls" in l and "invalid reports" in l and "$" in l for l in lines)
    assert iterate(dataset, paths, "--yes", "--limit", "60", "--quiet") == 0
    assert "[dev v1]" not in capsys.readouterr().err
