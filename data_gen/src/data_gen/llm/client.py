"""Thin LLM client wrapper.

- The API key is read ONLY from the ``ANTHROPIC_API_KEY`` environment variable. There is no argument,
  config field or file that can carry a key, so a key can never be committed.
- Requests avoid parameters the current models reject (sampling parameters, thinking budgets, prefill).
- ``MockClient`` lets every test and the dry run work without the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

API_KEY_ENV = "ANTHROPIC_API_KEY"


class MissingApiKeyError(RuntimeError):
    pass


class LLMCallError(RuntimeError):
    """A call failed after the SDK's own retries. ``retryable`` is False for auth and request errors."""

    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class LLMRefusal(RuntimeError):
    """The model declined the request (stop_reason == 'refusal'); treated as a failed attempt."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


class LLMClient(Protocol):
    def complete(self, *, system: str, prompt: str, model: str, max_tokens: int) -> LLMResult: ...


class AnthropicClient:
    """Calls the Anthropic Messages API with the key from the environment."""

    def __init__(self, *, sdk: Any | None = None, max_retries: int = 2, timeout: float = 120.0):
        key = os.environ.get(API_KEY_ENV)
        if not key:
            raise MissingApiKeyError(
                f"{API_KEY_ENV} is not set. Export it in your shell (never put it in a file) before "
                "running anything that calls the API."
            )
        if sdk is None:
            import anthropic  # imported lazily so tests and the dry run never need the network

            sdk = anthropic
        self._sdk = sdk
        self._client = sdk.Anthropic(api_key=key, max_retries=max_retries, timeout=timeout)

    def complete(self, *, system: str, prompt: str, model: str, max_tokens: int) -> LLMResult:
        sdk = self._sdk
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "low"},  # keep thinking spend small for short notes
            )
        except sdk.RateLimitError as exc:
            raise LLMCallError(f"rate limited: {exc}", retryable=True) from exc
        except sdk.APIConnectionError as exc:
            raise LLMCallError(f"connection error: {exc}", retryable=True) from exc
        except sdk.APIStatusError as exc:
            retryable = getattr(exc, "status_code", 0) >= 500
            raise LLMCallError(f"API error {getattr(exc, 'status_code', '?')}: {exc}", retryable) from exc

        if response.stop_reason == "refusal":
            raise LLMRefusal("the model declined this request")
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
        return LLMResult(
            text=text,
            input_tokens=int(response.usage.input_tokens),
            output_tokens=int(response.usage.output_tokens),
            stop_reason=response.stop_reason,
        )


@dataclass
class MockClient:
    """Scripted client for tests: ``responder(system, prompt) -> text``. Records every call."""

    responder: Callable[[str, str], str]
    calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 800
    output_tokens: int = 350

    def complete(self, *, system: str, prompt: str, model: str, max_tokens: int) -> LLMResult:
        self.calls.append({"system": system, "prompt": prompt, "model": model, "max_tokens": max_tokens})
        return LLMResult(
            text=self.responder(system, prompt),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            stop_reason="end_turn",
        )
