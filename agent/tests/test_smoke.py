import risk_model
from fastapi.testclient import TestClient

from agent.cli import main
from agent.smoke import run_smoke
from agent.app import create_app
from agent.config import Settings
from agent.runtime import build_orchestrator

from conftest import SECRET, env


def scripted_service(tmp_path):
    settings = Settings.from_env(env(tmp_path, AGENT_RELAX_LIMITS="1"))
    return TestClient(create_app(settings, build_orchestrator(settings)))


def test_a_good_deployment_passes(tmp_path):
    assert run_smoke("http://testserver", SECRET, client=scripted_service(tmp_path)) == []


def test_a_different_model_hash_fails(tmp_path):
    problems = run_smoke("http://testserver", SECRET, expected_hash="0" * 64, client=scripted_service(tmp_path))
    assert any("model hash" in p for p in problems)


def test_a_wrong_secret_fails_the_requests(tmp_path):
    problems = run_smoke("http://testserver", "not-the-secret", client=scripted_service(tmp_path))
    assert any("scored request answered 401" in p for p in problems) and any("declined request answered 401" in p for p in problems)


def test_a_service_that_scores_the_treatment_question_fails(tmp_path, make):
    from conftest import Counting

    client, _, _ = make(Counting(), AGENT_RELAX_LIMITS="1")  # a model that never declines
    problems = run_smoke("http://testserver", SECRET, client=client)
    assert any("not declined" in p for p in problems)


def test_the_command_needs_the_secret(monkeypatch, capsys):
    monkeypatch.delenv("AGENT_SHARED_SECRET", raising=False)
    assert main(["smoke", "--url", "http://localhost:1"]) == 2
    assert "AGENT_SHARED_SECRET" in capsys.readouterr().err


def test_the_committed_hash_is_what_the_package_reports():
    import json
    from pathlib import Path

    manifest = json.loads((Path(risk_model.default_directory()) / "manifest.json").read_text())
    assert manifest["model_hash"] == risk_model.model_hash()
