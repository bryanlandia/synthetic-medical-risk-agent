import json

import httpx
import pytest

from evals.agent_system import FAILURE_PREFIX, AgentSystem
from evals.messages import render_message
from evals.records import input_view
from evals.report import parse_report

HEALTH = {"status": "ok", "model_hash": "a" * 64, "version": "0.1.0", "logic_version": "1", "model_id": "scripted", "prompt_hash": "abc123"}
REPORT = {"status": "scored", "probability": 0.31, "uncertain": False, "symptoms": {k: "not_mentioned" for k in
          ("tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness")}, "labs_used": [], "data_quality": [], "evidence": ["a", "b"],
          "disclaimer": "This is not medical advice."}


def system(handler):
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json=HEALTH)
        return handler(request)
    return AgentSystem("http://test", "s", http=httpx.Client(base_url="http://test", transport=httpx.MockTransport(route)))


def ok(request):
    return httpx.Response(200, json={"declined": False, "report": REPORT, "reply": "r", "reply_source": "model",
                                     "usage": {"input_tokens": 1000, "output_tokens": 100, "cost_usd": 0.0002, "tool_calls": 1, "model_calls": 2}})


def view(dataset):
    return input_view(dataset.by_split["train"][0])


def test_the_version_names_the_model_the_prompt_and_the_service(dataset):
    s = system(ok)
    assert s.version == "agent@aaaaaaaaaaaa+pabc123+scripted+v0.1.0.1" and s.name == "agent" and not s.reference


def test_a_scored_response_comes_back_as_the_report_and_the_call_is_kept(dataset):
    s = system(ok)
    out = s.run_call(view(dataset), 0)
    assert parse_report(out.text).ok and (out.input_tokens, out.output_tokens) == (1000, 100)
    [call] = s.calls
    assert call["tool_calls"] == 1 and call["reply_source"] == "model" and call["probability"] == 0.31 and call["record_id"] == view(dataset)["patient_id"]


def test_the_message_sent_is_the_rendered_record(dataset):
    seen = []

    def spy(request):
        seen.append(json.loads(request.content)["message"])
        return ok(request)

    v = view(dataset)
    system(spy).run_call(v, 0)
    assert seen == [render_message(v)]


@pytest.mark.parametrize("status", [401, 429, 503, 502])
def test_an_http_error_is_graded_as_an_invalid_report_not_dropped(dataset, status):
    s = system(lambda r: httpx.Response(status, json={"error": "x"}))
    out = s.run_call(view(dataset), 0)
    assert out.text == f"{FAILURE_PREFIX} http {status}]" and not parse_report(out.text).ok
    assert s.calls[0]["status"] == status


def test_a_decline_is_graded_as_an_invalid_report(dataset):
    s = system(lambda r: httpx.Response(200, json={"declined": True, "decline_reason": "out_of_scope", "report": None, "reply": "no",
                                                   "reply_source": "template", "usage": {"tool_calls": 1, "model_calls": 1}}))
    out = s.run_call(view(dataset), 0)
    assert "declined: out_of_scope" in out.text and not parse_report(out.text).ok and s.calls[0]["declined"]


def test_a_transport_error_and_an_unreadable_body_are_failures(dataset):
    def boom(request):
        raise httpx.ConnectError("down")

    assert system(boom).run_call(view(dataset), 0).text == f"{FAILURE_PREFIX} http 0]"
    assert not parse_report(system(lambda r: httpx.Response(200, content=b"<html>")).run_call(view(dataset), 0).text).ok


def test_the_same_message_and_trial_is_sent_once_and_a_new_trial_is_a_real_second_call(dataset):
    sent = []

    def count(request):
        sent.append(1)
        return ok(request)

    s = system(count)
    v = view(dataset)
    s.run_call(v, 0)
    s.run_call(v, 0)
    assert len(sent) == 1 and len(s.calls) == 2  # both are recorded, one was paid for
    s.run_call(v, 1)
    assert len(sent) == 2


def test_a_dropped_pooled_connection_is_retried_once_and_a_second_failure_is_recorded_with_its_class(dataset):
    attempts = []

    def flaky(request):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response")
        return ok(request)

    s = system(flaky)
    assert parse_report(s.run_call(view(dataset), 0).text).ok and len(attempts) == 2 and s.calls[0]["status"] == 200

    always = system(lambda r: (_ for _ in ()).throw(httpx.RemoteProtocolError("gone")))
    out = always.run_call(view(dataset), 0)
    assert out.text == f"{FAILURE_PREFIX} http 0]" and always.calls[0]["error"] == "RemoteProtocolError"


def test_a_timeout_is_not_retried(dataset):
    attempts = []

    def slow(request):
        attempts.append(1)
        raise httpx.ReadTimeout("slow")

    s = system(slow)
    s.run_call(view(dataset), 0)
    assert len(attempts) == 1 and s.calls[0]["error"] == "ReadTimeout"


def test_a_call_served_from_the_run_cache_is_recorded_again_but_costs_nothing(dataset):
    s = system(ok)
    v = view(dataset)
    s.run_call(v, 0)
    s.run_call(v, 0)
    first, second = s.calls
    assert (first["cached"], first["cost_usd"]) == (False, 0.0002) and (second["cached"], second["cost_usd"]) == (True, 0.0)
    assert sum(c["cost_usd"] for c in s.calls) == pytest.approx(0.0002)


def test_the_tool_names_and_the_failure_text_of_a_non_200_are_kept(dataset):
    s = system(lambda r: httpx.Response(502, json={"error": "model_unavailable"}))
    s.run_call(view(dataset), 0)
    assert s.calls[0]["error"] == "model_unavailable" and s.calls[0]["tools"] == []
