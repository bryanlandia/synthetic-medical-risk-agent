import logging
from pathlib import Path

import pytest
import risk_model
from fastapi.testclient import TestClient
from risk_model import intake

from agent.app import create_app
from agent.config import Settings
from agent.orchestrator import Outcome

SECRET = "test-secret-value-1234"
API_KEY = "sk-ant-test-key-9999"
HEADERS = {"x-shared-secret": SECRET}
MODEL = risk_model.load()


class Counting:
    """A stand-in orchestrator that scores the message with the real classifier and counts how often it is called."""

    model_id = "scripted"

    def __init__(self, reply: str | None = "Estimated probability stated by the report.", tool: str = "score"):
        self.calls, self.reply, self.tool = 0, reply, tool

    def run(self, message: str) -> Outcome:
        self.calls += 1
        if self.tool == "decline":
            return Outcome(tool="decline", decline_reason="treatment_request", tool_calls=1, model_calls=1, input_tokens=10, output_tokens=5)
        report = MODEL.report(intake.view_from_text(message))
        return Outcome(tool="score", report=report, reply=self.reply, tool_calls=1, model_calls=2, input_tokens=1000, output_tokens=200)


def env(tmp_path: Path, **over: str) -> dict[str, str]:
    base = {"AGENT_SHARED_SECRET": SECRET, "ANTHROPIC_API_KEY": API_KEY, "AGENT_SCRIPTED_MODEL": "1",
            "AGENT_SPEND_DB": str(tmp_path / "spend.db")}
    base.update(over)
    return base


@pytest.fixture
def make(tmp_path):
    def build(orchestrator=None, clock=None, **over):
        settings = Settings.from_env(env(tmp_path, **over))
        orch = orchestrator or Counting()
        kwargs = {"clock": clock} if clock else {}
        return TestClient(create_app(settings, orch, **kwargs)), orch, settings
    return build


@pytest.fixture
def caplog_requests(caplog):
    caplog.set_level(logging.INFO, logger="agent.request")
    return caplog


@pytest.fixture
def serve_scripted(make, tmp_path):
    from agent.runtime import StrandsOrchestrator
    from agent.scripted import ScriptedModel

    def build(mode="normal"):
        settings = Settings.from_env(env(tmp_path))
        client, _, _ = make(StrandsOrchestrator(settings, ScriptedModel(mode), MODEL, model_id="scripted"))
        return client
    return build
