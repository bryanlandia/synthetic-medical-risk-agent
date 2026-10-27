"""What the service needs from whatever orchestrates a request: an outcome, and an error type for a model that is down."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class OrchestratorError(RuntimeError):
    """The model could not be reached or failed; the request is answered 502 and is not a decline."""


@dataclass
class Outcome:
    tool: str | None  # "score", "decline" or None (the model called neither)
    report: dict[str, Any] | None = None
    decline_reason: str | None = None
    reply: str | None = None  # the model's prose; only ever used for a scored message
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    prompt_hash: str = ""


class Orchestrator(Protocol):
    model_id: str

    def run(self, message: str) -> Outcome: ...
