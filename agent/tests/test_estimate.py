import json
import math

import httpx
import pytest
import risk_model
from fastapi.testclient import TestClient
from risk_model.labs import LAB_BY_KEY, LAB_KEYS, SYMPTOM_KEYS

from agent.app import create_app
from agent.config import Settings
from agent.limits import build_estimate_limiter, build_limits

from conftest import HEADERS, MODEL, SECRET, Counting, env
from test_logs import lines
from test_store import TOKEN, URL, FakeRedis

LABS = {k: LAB_BY_KEY[k].mean for k in LAB_KEYS}
SYMPTOMS = {k: "absent" for k in SYMPTOM_KEYS}
BODY = {"labs": LABS, "symptoms": SYMPTOMS}


def test_an_estimate_has_the_fixed_fields_and_calls_no_model(make):
    client, orch, _ = make()
    response = client.post("/estimate", json=BODY, headers=HEADERS)
    assert response.status_code == 200
    out = response.json()
    assert set(out) == {"request_id", "probability", "band", "score", "start", "breakdown", "message", "model_hash"}
    assert out["model_hash"] == risk_model.model_hash()
    assert out["probability"] == pytest.approx(MODEL.estimate(LABS, SYMPTOMS)["probability"], abs=1e-12)
    assert out["start"] + sum(r["contribution"] for r in out["breakdown"]) == pytest.approx(out["score"], abs=1e-6)
    assert 1 / (1 + math.exp(-out["score"])) == pytest.approx(out["probability"], abs=1e-9)
    assert out["message"].startswith("Labs:") and orch.calls == 0


def test_a_not_done_lab_is_accepted_and_a_value_is_rounded_to_its_resolution(make):
    client, _, _ = make()
    out = client.post("/estimate", json={"labs": {**LABS, "plexa_count": None, "velorin_index": 100.4}, "symptoms": SYMPTOMS}, headers=HEADERS).json()
    assert "Plexa" not in out["message"] and "Velorin index (VLI): 100 mg/dL" in out["message"]


@pytest.mark.parametrize("body", [
    {"labs": {**LABS, "velorin_index": 1040.0}, "symptoms": SYMPTOMS},
    {"labs": {**LABS, "velorin_index": "100"}, "symptoms": SYMPTOMS},
    {"labs": {k: v for k, v in LABS.items() if k != "serum_k17"}, "symptoms": SYMPTOMS},
    {"labs": LABS, "symptoms": {**SYMPTOMS, "tremor": "not_mentioned"}},
    {"labs": LABS, "symptoms": {k: v for k, v in SYMPTOMS.items() if k != "tremor"}},
    {"labs": LABS, "symptoms": SYMPTOMS, "message": "hello"},
    {"labs": LABS}, {"symptoms": SYMPTOMS}, [], "text", None,
])
def test_bad_inputs_get_422_and_nothing_is_computed(make, body):
    client, orch, _ = make()
    assert client.post("/estimate", json=body, headers=HEADERS).status_code == 422
    assert orch.calls == 0


def test_a_body_that_is_not_json_gets_422_and_an_oversized_one_413(make):
    client, _, _ = make()
    assert client.post("/estimate", content=b"not json", headers=HEADERS).status_code == 422
    assert client.post("/estimate", content=b" " * (64 * 1024 + 1), headers=HEADERS).status_code == 413


def test_the_secret_is_required_before_anything_else(make):
    client, _, _ = make()
    assert client.post("/estimate", json=BODY).status_code == 401
    assert client.post("/estimate", json=BODY, headers={"x-shared-secret": SECRET + "x"}).status_code == 401
    assert client.post("/estimate", json={"junk": 1}, headers={"x-shared-secret": SECRET + "x"}).status_code == 401


def test_the_121st_estimate_in_a_minute_gets_429_with_retry_after(make):
    client, _, _ = make(clock=lambda: 1_000_000.0)
    statuses = [client.post("/estimate", json=BODY, headers=HEADERS).status_code for _ in range(121)]
    assert statuses[:120] == [200] * 120 and statuses[120] == 429
    assert int(client.post("/estimate", json=BODY, headers=HEADERS).headers["retry-after"]) >= 1


def test_estimates_do_not_use_the_assistants_allowance_and_the_assistant_does_not_use_theirs(make):
    client, orch, _ = make(clock=lambda: 1_000_000.0)
    assert all(client.post("/estimate", json=BODY, headers=HEADERS).status_code == 200 for _ in range(100))
    assert client.post("/analyze", json={"message": "Velorin index 128 mg/dL. Tremor present."}, headers=HEADERS).status_code == 200
    for _ in range(9):  # the assistant's ten a minute are still all there: this is the 10th
        assert client.post("/analyze", json={"message": "Velorin index 128 mg/dL."}, headers=HEADERS).status_code == 200
    assert client.post("/analyze", json={"message": "x tremor"}, headers=HEADERS).status_code == 429
    assert client.post("/estimate", json=BODY, headers=HEADERS).status_code == 200  # and the assistant's 429 did not touch it
    assert orch.calls == 10


def test_estimates_add_nothing_to_the_daily_spend(make, tmp_path):
    client, _, _ = make()
    for _ in range(5):
        client.post("/estimate", json=BODY, headers=HEADERS)
    settings = Settings.from_env(env(tmp_path))
    _, spend = build_limits(settings)
    assert spend.total_today() == 0.0


def test_each_visitor_has_their_own_estimate_allowance(make):
    client, _, _ = make(clock=lambda: 1_000_000.0, AGENT_ESTIMATE_PER_MINUTE="2")
    visit = lambda who: client.post("/estimate", json=BODY, headers={**HEADERS, "x-visitor-address": who}).status_code
    assert [visit("a"), visit("a"), visit("a"), visit("b")] == [200, 200, 429, 200]


def test_the_shared_store_keeps_estimate_counts_under_their_own_key_prefix(tmp_path):
    fake = FakeRedis()
    settings = Settings.from_env(env(tmp_path, AGENT_STORE_URL=URL, AGENT_STORE_TOKEN=TOKEN, AGENT_ESTIMATE_PER_MINUTE="3"))
    http = httpx.Client(transport=httpx.MockTransport(fake.handler))
    clock = lambda: 1_000_000.0
    client = TestClient(create_app(settings, Counting(), clock, build_limits(settings, clock, http), estimate_limiter=build_estimate_limiter(settings, clock, http)))
    statuses = [client.post("/estimate", json=BODY, headers=HEADERS).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    assert any(k.startswith("estimate:min:") for k in fake.data) and not any(k.startswith("rate:") for k in fake.data)
    assert client.post("/analyze", json={"message": "Velorin index 128 mg/dL."}, headers=HEADERS).status_code == 200
    assert any(k.startswith("rate:min:") for k in fake.data)


def test_an_unreachable_store_refuses_the_estimate(tmp_path):
    fake = FakeRedis()
    fake.down = True
    settings = Settings.from_env(env(tmp_path, AGENT_STORE_URL=URL, AGENT_STORE_TOKEN=TOKEN))
    http = httpx.Client(transport=httpx.MockTransport(fake.handler))
    client = TestClient(create_app(settings, Counting(), estimate_limiter=build_estimate_limiter(settings, client=http)))
    assert client.post("/estimate", json=BODY, headers=HEADERS).status_code == 503


@pytest.mark.parametrize("forbidden", ["Velorin", "tremor", "Plexa", "mmol", "labs", "symptoms", SECRET])
def test_nothing_from_the_inputs_or_the_message_is_logged(make, caplog_requests, forbidden):
    client, _, _ = make()
    client.post("/estimate", json={"labs": {**LABS, "velorin_index": 128.0}, "symptoms": {**SYMPTOMS, "tremor": "present"}}, headers=HEADERS)
    client.post("/estimate", json=BODY, headers={})
    client.post("/estimate", json={"labs": LABS}, headers=HEADERS)
    text = "\n".join(r.getMessage() for r in caplog_requests.records) + caplog_requests.text
    assert forbidden not in text
    ok, unauthorized, invalid = lines(caplog_requests)
    assert ok["route"] == "estimate" and ok["status"] == 200 and set(ok) == {"request_id", "status", "route", "latency_ms"}
    assert unauthorized["status"] == 401 and invalid["status"] == 422
