"""The Strands agent: one per request, the system prompt, two tools, at most two model turns."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import risk_model
from strands import Agent

from .config import Settings
from .orchestrator import Outcome, OrchestratorError
from .tools import Tracker, make_tools

PROMPT_PATH = Path(__file__).with_name("prompts") / "system.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text()
PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]
MAX_TURNS = 2  # one model call to pick the tool, one to write the reply
_LOG = logging.getLogger("agent.model")


class StrandsOrchestrator:
    def __init__(self, settings: Settings, model: Any, risk: risk_model.RiskModel, model_id: str | None = None):
        self.settings = settings
        self._model = model
        self.model_id = model_id or settings.model_id
        self.prompt_hash = PROMPT_HASH
        self._tools = make_tools(risk)

    def run(self, message: str) -> Outcome:
        tracker = Tracker()
        agent = Agent(model=self._model, tools=list(self._tools), system_prompt=SYSTEM_PROMPT, callback_handler=None)
        try:
            result = agent(message, invocation_state={"message": message, "tracker": tracker}, limits={"turns": MAX_TURNS})
        except Exception as exc:  # the provider, network or SDK failed: never echo details to the caller
            raise OrchestratorError(type(exc).__name__) from None
        usage = result.metrics.accumulated_usage
        reply = str(result).strip() if tracker.final_tool == "score" else None
        return Outcome(tool=tracker.final_tool, report=tracker.report, decline_reason=tracker.reason, reply=reply or None,
                       input_tokens=int(usage.get("inputTokens", 0)), output_tokens=int(usage.get("outputTokens", 0)),
                       tool_calls=tracker.tool_calls, model_calls=int(result.metrics.cycle_count), prompt_hash=PROMPT_HASH,
                       tool_names=list(tracker.log))


def build_orchestrator(settings: Settings) -> StrandsOrchestrator:
    risk = risk_model.load(settings.model_dir)
    if settings.scripted_model:
        from .scripted import ScriptedModel

        return StrandsOrchestrator(settings, ScriptedModel(), risk, model_id="scripted")
    from strands.models.anthropic import AnthropicModel

    # Haiku 5.5 thinks by default and thinking shares max_tokens, so the ceiling is generous and the effort low: this task is
    # routing and a short summary, not reasoning.
    model = AnthropicModel(client_args=_client_args(settings), model_id=settings.model_id, max_tokens=settings.max_tokens,
                           params={"output_config": {"effort": settings.effort}})
    return StrandsOrchestrator(settings, model, risk)


def _client_args(settings: Settings) -> dict[str, Any]:
    """The API client: a short timeout so a stalled call fails in seconds, not minutes, and every error response from the API
    logged by status and request id only (the SDK retries quietly otherwise, and the cause of a slow request is lost)."""
    import httpx

    async def log_error(response: httpx.Response) -> None:
        if response.status_code >= 400:
            _LOG.warning("model api status=%s request_id=%s", response.status_code, response.headers.get("request-id"))

    return {"api_key": settings.api_key, "timeout": settings.model_timeout_s, "max_retries": 2,
            "http_client": httpx.AsyncClient(timeout=settings.model_timeout_s, event_hooks={"response": [log_error]})}
