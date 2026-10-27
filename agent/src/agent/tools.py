"""The two tools the agent has. Neither takes values or text from the model.

``score_message`` reads the user's exact message from request state (``invocation_state``), which the model cannot set, runs
text intake and the classifier on it and returns the report unchanged. ``decline`` takes only a reason from a closed set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import risk_model
from risk_model import intake
from strands import ToolContext, tool

Reason = Literal["out_of_scope", "treatment_request", "real_disease", "phi", "other"]


@dataclass
class Tracker:
    """What happened in one request: which tool ended it, and how many tool calls the model made."""

    final_tool: str | None = None
    report: dict[str, Any] | None = None
    reason: str | None = None
    tool_calls: int = 0
    refused_extra: int = 0
    log: list[str] = field(default_factory=list)


def _result(payload: Any, error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return {"status": "error" if error else "success", "content": [{"text": text}]}


def make_tools(model: risk_model.RiskModel):
    """The tool functions, bound to a loaded model. The request's message and tracker arrive in ``invocation_state``."""

    @tool(context=True)
    def score_message(tool_context: ToolContext) -> dict[str, Any]:
        """Score the user's message for the fictional syndrome. Takes no arguments: the message is read from the request,
        never from you. Returns the risk report (probability, uncertain flag, symptom readings, labs read, data-quality
        warnings and evidence)."""
        state = tool_context.invocation_state
        tracker: Tracker = state["tracker"]
        tracker.tool_calls += 1
        tracker.log.append("score_message")
        if tracker.final_tool is not None:
            tracker.refused_extra += 1
            return _result("Only one tool call is allowed per request; this call was not run.", error=True)
        report = model.report(intake.view_from_text(state["message"]))
        tracker.final_tool, tracker.report = "score", report
        return _result(report)

    @tool(context=True)
    def decline(reason: Reason, tool_context: ToolContext) -> dict[str, Any]:
        """Decline the request. reason is one of out_of_scope, treatment_request, real_disease, phi, other. Nothing else is needed."""
        tracker: Tracker = tool_context.invocation_state["tracker"]
        tracker.tool_calls += 1
        tracker.log.append("decline")
        if tracker.final_tool is not None:
            tracker.refused_extra += 1
            return _result("Only one tool call is allowed per request; this call was not run.", error=True)
        tracker.final_tool, tracker.reason = "decline", reason
        tool_context.agent.cancel(after_current_tools=True)  # nothing more to write: end the loop without a second model call
        return _result("Declined.")

    return score_message, decline
