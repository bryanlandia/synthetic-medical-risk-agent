import json

from conftest import HEADERS

BODY = {"message": "Velorin index 108 mg/dL, serum K-17 4.1 mmol/L. The patient reports tremor."}


def post(client, body=BODY, headers=HEADERS):
    return client.post("/analyze", json=body, headers=headers)


def test_a_valid_request_is_served_with_the_contract_fields(make):
    client, orch, _ = make()
    r = post(client)
    assert r.status_code == 200 and orch.calls == 1
    body = r.json()
    assert set(body) == {"request_id", "declined", "decline_reason", "reply", "reply_source", "report", "usage"}
    assert body["declined"] is False and body["report"]["status"] == "scored" and set(body["usage"]) >= {"input_tokens", "output_tokens", "cost_usd"}
    assert "not medical advice" in body["reply"].lower() and r.headers["x-request-id"] == body["request_id"]


def test_health_check_names_the_model_and_calls_no_model(make):
    client, orch, _ = make()
    r = client.get("/healthz")
    assert r.status_code == 200 and len(r.json()["model_hash"]) == 64 and r.json()["version"] and orch.calls == 0


def test_a_missing_or_wrong_secret_is_401_and_the_model_is_not_called(make):
    client, orch, _ = make()
    for headers in ({}, {"x-shared-secret": "nope"}, {"x-shared-secret": ""}):
        r = post(client, headers=headers)
        assert r.status_code == 401 and orch.calls == 0
        assert "message" not in r.text and BODY["message"] not in r.text


def test_empty_and_malformed_requests_are_422(make):
    client, orch, _ = make()
    for body in ({"message": ""}, {"message": "   \n\t "}, {"message": 5}, {"msg": "x"}, ["x"]):
        assert post(client, body).status_code == 422
    assert client.post("/analyze", content=b"{not json", headers={**HEADERS, "content-type": "application/json"}).status_code == 422
    assert orch.calls == 0


def test_a_message_over_the_cap_is_413_and_one_at_the_cap_is_served(make):
    client, orch, settings = make()
    assert post(client, {"message": "x" * (settings.max_message_chars + 1)}).status_code == 413 and orch.calls == 0
    assert post(client, {"message": "a" * settings.max_message_chars}).status_code == 200 and orch.calls == 1


def test_an_enormous_body_is_refused_without_being_read_as_a_message(make):
    client, orch, _ = make()
    r = client.post("/analyze", content=b'{"message": "' + b"x" * 200_000 + b'"}', headers={**HEADERS, "content-type": "application/json"})
    assert r.status_code == 413 and orch.calls == 0


def test_control_characters_are_removed_but_line_breaks_stay(make):
    seen = []

    class Spy:
        model_id = "scripted"

        def run(self, message):
            seen.append(message)
            from conftest import Counting
            return Counting().run(message)

    client, _, _ = make(Spy())
    post(client, {"message": "Denies\x00 shaking.\r\nFeels\x07 dizzy.\tOK"})
    assert seen == ["Denies shaking.\nFeels dizzy.\tOK"]


def test_the_eleventh_request_in_a_minute_is_429_with_retry_after(make):
    t = [1000.0]
    client, orch, _ = make(clock=lambda: t[0])
    codes = [post(client).status_code for _ in range(11)]
    assert codes == [200] * 10 + [429] and orch.calls == 10
    r = post(client)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    t[0] += 61
    assert post(client).status_code == 200


def test_the_daily_limit_is_per_client_and_a_rejected_request_is_not_counted(make):
    t = [0.0]
    client, orch, _ = make(clock=lambda: t[0], AGENT_RATE_PER_DAY="12")
    for i in range(12):
        t[0] += 7
        assert post(client).status_code == 200
    t[0] += 7
    assert post(client).status_code == 429 and orch.calls == 12


def test_a_caller_with_the_secret_may_name_the_visitor_and_each_visitor_has_its_own_limit(make):
    client, orch, _ = make(AGENT_RATE_PER_MINUTE="2")
    def visitor(v):
        return post(client, headers={**HEADERS, "x-visitor-address": v}).status_code
    assert [visitor("1.1.1.1"), visitor("1.1.1.1"), visitor("1.1.1.1"), visitor("2.2.2.2")] == [200, 200, 429, 200]


def test_a_caller_without_the_secret_cannot_choose_its_identity(make):
    client, orch, _ = make(AGENT_RATE_PER_MINUTE="2")
    for v in ("a", "b", "c"):  # rotating the claimed address does not help: it is rejected before the limiter
        assert post(client, headers={"x-visitor-address": v}).status_code == 401
    assert orch.calls == 0


def test_a_rejected_request_never_reaches_the_model_in_any_path(make):
    client, orch, _ = make(AGENT_RATE_PER_MINUTE="1")
    post(client)
    calls = orch.calls
    post(client)                                 # 429
    post(client, headers={})                     # 401
    post(client, {"message": ""})                # 422
    assert orch.calls == calls
