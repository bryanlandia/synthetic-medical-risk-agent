import json
import subprocess
import types
from contextlib import contextmanager

import httpx
import pytest

from evals import agent_cli, agent_service, regression
from evals.agent_system import AgentSystem
from evals.cli import build_parser
from evals.ledger import record_final_run

from test_agent_system import HEALTH, ok, system


def parse(*argv):
    return build_parser().parse_args(["run", "--system", "agent", *argv])


@pytest.fixture
def mocked(monkeypatch):
    """The CLI against a mocked service: no process is started and no protected record is read."""
    holder = {}

    @contextmanager
    def connect(args, cap):
        holder["cap"] = cap
        holder["system"] = holder.setdefault("system", system(holder.get("handler", ok)))
        yield holder["system"]

    monkeypatch.setattr(agent_cli, "connect", connect)
    return holder


def fake_run_suites(monkeypatch, ledger):
    def run(dataset, system, split, **kw):
        record_final_run(system.version, split, final=kw["final"], path=ledger, stage=kw["ledger_stage"])
        return types.SimpleNamespace(rows=[], stopped=None)

    monkeypatch.setattr(agent_cli, "run_suites", run)
    monkeypatch.setattr(agent_cli, "summarize", lambda *a, **k: {"rows": [], "notice": "", "harness_version": "", "system_version": "", "split": "x",
                                                                  "dataset_config_hash": "", "seed": 0, "n_boot": 1, "reference": False, "mdd_note": ""})
    monkeypatch.setattr(agent_cli, "write_transcripts", lambda *a, **k: None)
    monkeypatch.setattr(agent_cli, "write_summary", lambda *a, **k: None)
    monkeypatch.setattr(agent_cli, "render_markdown", lambda *a, **k: "")


def test_a_run_through_the_real_scripted_service_writes_transcripts_summary_calls_and_tool_use(dataset, tmp_path):
    code = agent_cli.cmd_run(parse("--split", "dev", "--limit", "10"), dataset, out_root=tmp_path)
    assert code == 0
    out = tmp_path / "dev"
    summary = json.loads((out / "summary.json").read_text())
    metrics = {(r["category"], r["metric"]) for r in summary["rows"]}
    assert ("happy_path", "auc") in metrics and ("tool_use", "scoring_tool_rate") in metrics and ("tool_use", "over_refusal_rate") in metrics
    calls = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
    assert calls and all(c["status"] == 200 and c["tool_calls"] == 1 for c in calls)
    info = json.loads((out / "run.json").read_text())
    assert info["system_version"].startswith("agent@") and "scripted" in info["system_version"] and info["spend_usd"] == 0


def test_a_protected_split_needs_a_dev_run_of_this_exact_system(dataset, tmp_path, mocked, capsys):
    code = agent_cli.cmd_run(parse("--split", "test", "--final"), dataset, out_root=tmp_path)
    assert code == 2 and "dev run" in capsys.readouterr().err
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "run.json").write_text(json.dumps({"system_version": "agent@someotherversion"}))
    assert agent_cli.cmd_run(parse("--split", "test", "--final"), dataset, out_root=tmp_path) == 2


def test_a_protected_split_needs_final_and_a_repeat_needs_force_and_is_recorded_and_warned(dataset, tmp_path, mocked, monkeypatch, capsys):
    ledger = tmp_path / "ledger.json"
    fake_run_suites(monkeypatch, ledger)
    sys_ = mocked.setdefault("system", system(ok))
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "run.json").write_text(json.dumps({"system_version": sys_.version}))
    run = lambda *a: agent_cli.cmd_run(parse("--split", "test", *a, "--out", str(tmp_path / "t")), dataset, out_root=tmp_path, ledger_path=ledger)  # noqa: E731
    assert run() == 2 and "--final" in capsys.readouterr().err
    assert run("--final") == 0
    assert run("--final") == 2 and "second look" in capsys.readouterr().err
    with pytest.warns(UserWarning, match="2 times"):
        assert run("--final", "--force") == 0
    assert [e["run"] for e in json.loads(ledger.read_text())["entries"]] == [1, 2]


def test_a_live_run_prints_its_estimate_and_needs_yes(dataset, tmp_path, mocked, capsys):
    code = agent_cli.cmd_run(parse("--split", "dev", "--live"), dataset, out_root=tmp_path)
    err = capsys.readouterr()
    assert code == 2 and "spends money" in err.err and "stage cap" in err.out and "about $" in err.out
    assert mocked == {}  # the service was never started


def test_the_scope_run_grades_every_prompt_and_writes_results(dataset, tmp_path, mocked, capsys):
    mocked["handler"] = lambda r: httpx.Response(200, json={"declined": True, "decline_reason": "out_of_scope", "report": None, "reply": "no",
                                                            "reply_source": "template", "usage": {"tool_calls": 1, "model_calls": 1, "cost_usd": 0.0}})
    args = build_parser().parse_args(["agent-scope"])
    assert agent_cli.cmd_scope(args, dataset, out_root=tmp_path) == 0
    results = [json.loads(line) for line in (tmp_path / "scope" / "results.jsonl").read_text().splitlines()]
    assert len(results) == 66 and all(r["declined"] for r in results)
    rows = {r["metric"]: r for r in json.loads((tmp_path / "scope" / "summary.json").read_text())["rows"]}
    assert rows["decline_rate"]["value"] == 1.0 and rows["right_reason_rate"]["value"] < 1.0 and rows["over_refusal_rate"]["value"] == 1.0


def test_the_estimate_needs_no_key_and_names_every_stage(dataset, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert agent_cli.cmd_estimate(types.SimpleNamespace(stage="all"), dataset) == 0
    out = capsys.readouterr().out
    for name in ("dev", "test", "adversarial", "trials", "scope", "total", "no key was needed"):
        assert name in out


def test_stage_caps_scale_with_the_calls_and_never_fall_below_the_floor():
    assert agent_cli.stage_cap(10, 0.001) == agent_cli.MIN_CAP
    assert agent_cli.stage_cap(10_000, 0.001) == 15.0


def test_the_service_environment_passes_the_api_key_only_for_a_live_run(tmp_path):
    base = {"PATH": "/bin", "HOME": "/h", "ANTHROPIC_API_KEY": "sk-secret", "OTHER": "x"}
    scripted = agent_service.service_env(live=False, budget_usd=None, secret="s", spend_db=tmp_path / "d", base=base)
    assert "ANTHROPIC_API_KEY" not in scripted and scripted["AGENT_SCRIPTED_MODEL"] == "1" and "OTHER" not in scripted
    assert scripted["AGENT_ENV"] == "test" and scripted["AGENT_RELAX_LIMITS"] == "1" and "AGENT_DAILY_BUDGET_USD" not in scripted
    live = agent_service.service_env(live=True, budget_usd=3.5, secret="s", spend_db=tmp_path / "d", base=base)
    assert live["ANTHROPIC_API_KEY"] == "sk-secret" and "AGENT_SCRIPTED_MODEL" not in live and live["AGENT_DAILY_BUDGET_USD"] == "3.5"
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        agent_service.service_env(live=True, budget_usd=None, secret="s", spend_db=tmp_path / "d", base={"PATH": "/bin"})


def test_the_agent_guard_tests_pass_in_the_regression_subset():
    assert regression.agent_guard_failures() == []


def test_a_failing_guard_test_fails_the_regression_subset(monkeypatch):
    monkeypatch.setattr(regression.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "FAILED tests/test_guards.py::x", ""))
    [msg] = regression.agent_guard_failures()
    assert "agent guard tests failed" in msg and "test_guards" in msg


def test_the_measured_cost_per_call_ignores_calls_served_from_the_cache(tmp_path):
    (tmp_path / "dev").mkdir()
    rows = [{"status": 200, "model_calls": 2, "cost_usd": 0.001, "cached": False}, {"status": 200, "model_calls": 2, "cost_usd": 0.0, "cached": True},
            {"status": 502, "model_calls": 0, "cost_usd": 0.0, "cached": False}]
    (tmp_path / "dev" / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    unit, basis = agent_cli.per_call_cost(tmp_path)
    assert unit == pytest.approx(0.001) and "measured on 1 calls" in basis
