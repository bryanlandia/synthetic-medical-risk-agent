import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from data_gen.llm.client import (
    API_KEY_ENV,
    AnthropicClient,
    LLMCallError,
    LLMRefusal,
    MissingApiKeyError,
    MockClient,
)

REPO = Path(__file__).resolve().parents[2]
# Built from pieces so this file never matches its own scan.
KEY_PATTERN = re.compile("sk-" + "ant-" + r"[A-Za-z0-9_-]{16,}")


class FakeSDK:
    """Stands in for the anthropic module: records the client kwargs and the request."""

    class RateLimitError(Exception): ...

    class APIConnectionError(Exception): ...

    class APIStatusError(Exception):
        def __init__(self, msg, status_code=400):
            super().__init__(msg)
            self.status_code = status_code

    def __init__(self, response=None, raises=None):
        self.requests = []
        self.client_kwargs = None
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.requests.append(kwargs)
                if raises:
                    raise raises
                return response

        class _Client:
            def __init__(self, **kwargs):
                outer.client_kwargs = kwargs
                self.messages = _Messages()

        self.Anthropic = _Client


def response(text="hello", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=f" {text} ")],
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        stop_reason=stop_reason,
    )


def test_missing_key_fails_clearly(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(MissingApiKeyError, match=API_KEY_ENV):
        AnthropicClient(sdk=FakeSDK())


def test_key_comes_only_from_the_environment(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key-from-env")
    sdk = FakeSDK(response())
    AnthropicClient(sdk=sdk)
    assert sdk.client_kwargs["api_key"] == "test-key-from-env"
    with pytest.raises(TypeError):
        AnthropicClient(api_key="nope", sdk=sdk)  # type: ignore[call-arg]


def test_request_avoids_rejected_parameters(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "k")
    sdk = FakeSDK(response("note text"))
    result = AnthropicClient(sdk=sdk).complete(system="sys", prompt="p", model="claude-haiku-5-5", max_tokens=300)
    req = sdk.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["max_tokens"] == 300
    assert req["messages"] == [{"role": "user", "content": "p"}]  # no assistant prefill
    for banned in ("temperature", "top_p", "top_k", "thinking"):
        assert banned not in req
    assert req["output_config"] == {"effort": "low"}
    assert (result.text, result.input_tokens, result.output_tokens) == ("note text", 12, 7)


def test_refusal_and_errors_are_classified(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "k")
    with pytest.raises(LLMRefusal):
        AnthropicClient(sdk=FakeSDK(response(stop_reason="refusal"))).complete(
            system="s", prompt="p", model="m", max_tokens=10)
    for exc, retryable in (
        (FakeSDK.RateLimitError("429"), True),
        (FakeSDK.APIConnectionError("net"), True),
        (FakeSDK.APIStatusError("boom", 503), True),
        (FakeSDK.APIStatusError("bad request", 400), False),
        (FakeSDK.APIStatusError("auth", 401), False),
    ):
        with pytest.raises(LLMCallError) as info:
            AnthropicClient(sdk=FakeSDK(raises=exc)).complete(system="s", prompt="p", model="m", max_tokens=10)
        assert info.value.retryable is retryable


def test_mock_client_records_calls():
    mock = MockClient(responder=lambda s, p: f"echo:{p}")
    r = mock.complete(system="s", prompt="x", model="m", max_tokens=5)
    assert r.text == "echo:x" and mock.calls[0]["model"] == "m"


def test_no_api_key_string_in_tracked_files():
    out = subprocess.run(["git", "grep", "-l", "-E", KEY_PATTERN.pattern], cwd=REPO, capture_output=True, text=True)
    assert out.stdout.strip() == ""


def test_real_sdk_exposes_the_exceptions_the_wrapper_catches():
    import anthropic

    for name in ("RateLimitError", "APIConnectionError", "APIStatusError", "Anthropic"):
        assert hasattr(anthropic, name)
