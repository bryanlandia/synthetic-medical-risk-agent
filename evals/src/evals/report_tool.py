"""A client that gets the risk report back through a tool call instead of free text.

The tool's input schema is the committed report schema, so the model fills in the contract directly. The tool is
offered but not forced (newer models reject a forced tool choice), and no sampling parameters are sent. The tool
input is returned as JSON text, so ``PromptSystem``, the cache and the graders work unchanged. Anything that is not
one complete tool call (no call, a refusal, a cut-off reply) comes back as text that does not parse, so it is a
counted failure of the parse grader rather than a silent retry.
"""

from __future__ import annotations

import json
from typing import Any

from data_gen.llm.client import AnthropicClient, LLMCallError, LLMResult

from .report import SCHEMA_PATH

TOOL_NAME = "submit_report"
TOOL_DESCRIPTION = "Submit the risk report for this record. Call it exactly once."
NO_CALL_PREFIX = "[no tool call]"
REFUSAL_PREFIX = "[refusal]"
TRUNCATED_PREFIX = "[truncated]"


def report_tool() -> dict[str, Any]:
    return {"name": TOOL_NAME, "description": TOOL_DESCRIPTION,
            "input_schema": json.loads(SCHEMA_PATH.read_text())}


class ReportToolClient(AnthropicClient):
    def __init__(self, *, effort: str = "medium", **kwargs: Any):
        super().__init__(effort=effort, **kwargs)

    def complete(self, *, system: str, prompt: str, model: str, max_tokens: int, nonce: int = 0) -> LLMResult:
        sdk = self._sdk
        try:
            response = self._client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[report_tool()], output_config={"effort": self.effort})
        except sdk.RateLimitError as exc:
            raise LLMCallError(f"rate limited: {exc}", retryable=True, rate_limited=True) from exc
        except sdk.APIConnectionError as exc:
            raise LLMCallError(f"connection error: {exc}", retryable=True) from exc
        except sdk.APIStatusError as exc:
            status = getattr(exc, "status_code", 0)
            raise LLMCallError(f"API error {status or '?'}: {exc}", status >= 500,
                               rate_limited=status in (429, 529)) from exc
        stop = response.stop_reason
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
        calls = [b for b in response.content
                 if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == TOOL_NAME]
        if stop == "refusal":
            out = f"{REFUSAL_PREFIX} {text}".strip()
        elif stop == "max_tokens":
            out = f"{TRUNCATED_PREFIX} {text}".strip()
        elif not calls:
            out = f"{NO_CALL_PREFIX} {text}".strip()
        else:
            out = json.dumps(calls[0].input, sort_keys=True)
        return LLMResult(text=out, input_tokens=int(response.usage.input_tokens),
                         output_tokens=int(response.usage.output_tokens), stop_reason=stop)
