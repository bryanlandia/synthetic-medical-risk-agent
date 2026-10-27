import json

import pytest

from agent import logs

from conftest import API_KEY, HEADERS, SECRET

MESSAGE = "Zorbulan quextrium note: Velorin index 108 mg/dL. The patient reports tremor."


def lines(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "agent.request"]


def test_a_served_request_logs_one_line_with_the_listed_fields(make, caplog_requests):
    client, _, _ = make()
    client.post("/analyze", json={"message": MESSAGE}, headers=HEADERS)
    [line] = lines(caplog_requests)
    assert set(line) >= {"request_id", "status", "tool", "reply_source", "input_tokens", "output_tokens", "cost_usd", "latency_ms",
                         "message_chars"}
    assert line["status"] == 200 and line["message_chars"] == len(MESSAGE) and line["tool"] == "score"


@pytest.mark.parametrize("forbidden", ["Zorbulan", "quextrium", "tremor", "Velorin", SECRET, API_KEY])
def test_nothing_from_the_message_the_reply_the_secret_or_the_key_is_logged(make, caplog_requests, forbidden):
    client, _, _ = make()
    client.post("/analyze", json={"message": MESSAGE}, headers=HEADERS)
    client.post("/analyze", json={"message": MESSAGE}, headers={"x-shared-secret": SECRET + "x"})
    client.post("/analyze", json={"message": ""}, headers=HEADERS)
    text = "\n".join(r.getMessage() for r in caplog_requests.records) + caplog_requests.text
    assert forbidden not in text


def test_rejections_are_logged_with_their_status_and_reason_but_no_content(make, caplog_requests):
    client, _, _ = make()
    client.post("/analyze", json={"message": MESSAGE}, headers={})
    [line] = lines(caplog_requests)
    assert line["status"] == 401 and line["reason"] == "unauthorized" and "message" not in line


def test_a_field_that_is_not_on_the_list_cannot_be_logged():
    with pytest.raises(ValueError, match="not a loggable field"):
        logs.log_request(request_id="x", message="secret text")
