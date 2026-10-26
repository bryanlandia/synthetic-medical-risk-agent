import json
from types import SimpleNamespace as NS

import pytest
from data_gen.llm.client import API_KEY_ENV, LLMCallError

from evals.report import SCHEMA_PATH, parse_report
from evals.report_tool import NO_CALL_PREFIX, REFUSAL_PREFIX, TOOL_NAME, TRUNCATED_PREFIX, ReportToolClient
from evals.systems import scored_report

VIEW = {"patient_id": "x", "panel": [{"lab": "velorin_index", "value": 104.0, "unit": "mg/dL"}], "note": "Seen."}


class FakeSDK:
    class RateLimitError(Exception): ...

    class APIConnectionError(Exception): ...

    class APIStatusError(Exception):
        def __init__(self, msg, status_code=400):
            super().__init__(msg)
            self.status_code = status_code

    def __init__(self, response=None, raises=None):
        self.requests, outer = [], self

        class _Messages:
            def create(self, **kwargs):
                outer.requests.append(kwargs)
                if raises:
                    raise raises
                return response

        class _Client:
            def __init__(self, **kwargs):
                self.messages = _Messages()

        self.Anthropic = _Client


def reply(*blocks, stop="tool_use"):
    return NS(content=list(blocks), stop_reason=stop, usage=NS(input_tokens=700, output_tokens=210))


def tool_call(payload):
    return NS(type="tool_use", name=TOOL_NAME, input=payload)


def client(monkeypatch, sdk):
    monkeypatch.setenv(API_KEY_ENV, "k")
    return ReportToolClient(sdk=sdk)


def call(c):
    return c.complete(system="s", prompt=json.dumps(VIEW), model="claude-sonnet-5-5", max_tokens=4000)


def test_a_tool_call_comes_back_as_a_report_that_parses(monkeypatch):
    payload = scored_report(VIEW, 0.31, uncertain=False)
    out = call(client(monkeypatch, FakeSDK(reply(NS(type="thinking", thinking=""), tool_call(payload)))))
    assert out.input_tokens == 700 and out.output_tokens == 210
    assert parse_report(out.text).ok and json.loads(out.text)["probability"] == 0.31


def test_the_request_offers_the_committed_schema_and_forces_nothing(monkeypatch):
    sdk = FakeSDK(reply(tool_call(scored_report(VIEW, 0.3, uncertain=False))))
    call(client(monkeypatch, sdk))
    req = sdk.requests[0]
    assert [t["name"] for t in req["tools"]] == [TOOL_NAME]
    assert req["tools"][0]["input_schema"] == json.loads(SCHEMA_PATH.read_text())
    for banned in ("tool_choice", "temperature", "top_p", "top_k", "thinking"):
        assert banned not in req
    assert req["output_config"] == {"effort": "medium"}


@pytest.mark.parametrize("response,prefix", [
    (reply(NS(type="text", text="I think it is low."), stop="end_turn"), NO_CALL_PREFIX),
    (reply(NS(type="text", text="I cannot help."), stop="refusal"), REFUSAL_PREFIX),
    (reply(tool_call({"status": "scor"}), stop="max_tokens"), TRUNCATED_PREFIX),
])
def test_no_call_a_refusal_and_a_cut_off_reply_are_reports_that_fail_to_parse(monkeypatch, response, prefix):
    out = call(client(monkeypatch, FakeSDK(response)))
    assert out.text.startswith(prefix) and not parse_report(out.text).ok


def test_rate_limits_are_signalled_for_the_caller_to_back_off(monkeypatch):
    for exc, limited in ((FakeSDK.RateLimitError("429"), True), (FakeSDK.APIStatusError("x", 529), True),
                         (FakeSDK.APIStatusError("x", 400), False)):
        with pytest.raises(LLMCallError) as info:
            call(client(monkeypatch, FakeSDK(raises=exc)))
        assert info.value.rate_limited is limited
