import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.app import create_app
from agent.config import ConfigError, Settings
from agent.limits import build_limits
from agent.store import RestStore, StoreError

from conftest import HEADERS, Counting, env


class Priced(Counting):
    model_id = "claude-haiku-5-5"  # a priced model: the scripted one costs nothing

URL, TOKEN = "https://store.example.test", "store-token-5555"
BODY = {"message": "Velorin index 128 mg/dL. Tremor present."}


class FakeRedis:
    """Enough of Redis behind the REST pipeline endpoint to count, add and expire."""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.expiry: dict[str, int] = {}
        self.requests = 0
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if self.down:
            return httpx.Response(500, json={"error": "down"})
        out = []
        for cmd, *args in json.loads(request.content):
            if cmd == "GET":
                out.append({"result": self.data.get(args[0])})
            elif cmd in ("INCR", "DECR"):
                self.data[args[0]] = str(int(self.data.get(args[0], "0")) + (1 if cmd == "INCR" else -1))
                out.append({"result": int(self.data[args[0]])})
            elif cmd == "INCRBYFLOAT":
                self.data[args[0]] = repr(float(self.data.get(args[0], "0")) + float(args[1]))
                out.append({"result": self.data[args[0]]})
            elif cmd == "EXPIRE":
                self.expiry[args[0]] = int(args[1])
                out.append({"result": 1})
            else:
                out.append({"error": f"unknown command {cmd}"})
        return httpx.Response(200, json=out)


def instance(tmp_path, fake, clock=None, orchestrator=None, **over):
    settings = Settings.from_env(env(tmp_path, AGENT_STORE_URL=URL, AGENT_STORE_TOKEN=TOKEN, **over))
    client = httpx.Client(transport=httpx.MockTransport(fake.handler))
    limits = build_limits(settings, clock or (lambda: 1_000_000.0), client)
    orch = orchestrator or Counting()
    return TestClient(create_app(settings, orch, clock or (lambda: 1_000_000.0), limits)), orch


def test_two_instances_share_one_daily_cap(tmp_path):
    fake = FakeRedis()
    a, orch_a = instance(tmp_path, fake, orchestrator=Priced(), AGENT_DAILY_BUDGET_USD="0.0001")
    b, orch_b = instance(tmp_path, fake, orchestrator=Priced(), AGENT_DAILY_BUDGET_USD="0.0001")
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 200  # 0.0002 a request, past a cap of 0.0001
    assert b.post("/analyze", json=BODY, headers=HEADERS).status_code == 503
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 503
    assert orch_a.calls == 1 and orch_b.calls == 0
    assert fake.expiry["spend:1970-01-12"] == 2 * 86_400


def test_two_instances_share_one_visitor_limit_and_retry_after_is_the_window_end(tmp_path):
    fake = FakeRedis()
    a, _ = instance(tmp_path, fake, AGENT_RATE_PER_MINUTE="10")
    b, _ = instance(tmp_path, fake, AGENT_RATE_PER_MINUTE="10")
    headers = {**HEADERS, "x-visitor-address": "203.0.113.9"}
    for i in range(10):
        assert (a if i % 2 else b).post("/analyze", json=BODY, headers=headers).status_code == 200
    r = b.post("/analyze", json=BODY, headers=headers)
    assert r.status_code == 429
    assert r.headers["retry-after"] == str(60 - 1_000_000 % 60)
    other = a.post("/analyze", json=BODY, headers={**HEADERS, "x-visitor-address": "203.0.113.10"})
    assert other.status_code == 200


def test_a_rejected_request_is_not_counted_and_a_new_minute_starts_clean(tmp_path):
    fake = FakeRedis()
    now = [1_000_000.0]
    a, _ = instance(tmp_path, fake, clock=lambda: now[0], AGENT_RATE_PER_MINUTE="2")
    for _ in range(2):
        assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 200
    for _ in range(3):
        assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 429
    assert fake.data[next(k for k in fake.data if k.startswith("rate:min:"))] == "2"
    now[0] += 60
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 200


def test_the_day_rolls_over_in_the_spend_key(tmp_path):
    fake = FakeRedis()
    now = [1_000_000.0]
    a, _ = instance(tmp_path, fake, clock=lambda: now[0], orchestrator=Priced(), AGENT_DAILY_BUDGET_USD="0.0001")
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 200
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 503
    now[0] += 86_400
    assert a.post("/analyze", json=BODY, headers=HEADERS).status_code == 200


def test_if_the_store_cannot_answer_the_request_is_refused_and_the_model_is_not_called(tmp_path):
    fake = FakeRedis()
    fake.down = True
    a, orch = instance(tmp_path, fake)
    r = a.post("/analyze", json=BODY, headers=HEADERS)
    assert r.status_code == 503 and r.json()["error"] == "limits_unavailable"
    assert orch.calls == 0
    assert TOKEN not in r.text


def test_a_store_error_never_carries_the_credential():
    fake = FakeRedis()
    fake.down = True
    store = RestStore(URL, TOKEN, client=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    with pytest.raises(StoreError) as caught:
        store.pipeline([["GET", "k"]])
    assert TOKEN not in str(caught.value)


def test_the_local_counters_are_used_without_a_store(tmp_path):
    from agent.ratelimit import RateLimiter
    from agent.spend import SpendCounter

    limiter, spend = build_limits(Settings.from_env(env(tmp_path)))
    assert isinstance(limiter, RateLimiter) and isinstance(spend, SpendCounter)


def test_production_refuses_to_start_without_the_store_and_names_the_variable_not_a_value(tmp_path):
    base = {"AGENT_ENV": "production", "AGENT_SCRIPTED_MODEL": "0"}
    with pytest.raises(ConfigError, match="AGENT_STORE_URL") as caught:
        Settings.from_env(env(tmp_path, **base))
    assert "sk-ant" not in str(caught.value)
    assert Settings.from_env(env(tmp_path, AGENT_STORE_URL=URL, AGENT_STORE_TOKEN=TOKEN, **base)).store_url == URL


def test_the_url_and_the_token_come_together(tmp_path):
    with pytest.raises(ConfigError, match="together"):
        Settings.from_env(env(tmp_path, AGENT_STORE_URL=URL))


def test_a_preview_environment_is_treated_like_development(tmp_path):
    s = Settings.from_env(env(tmp_path, AGENT_ENV="preview"))
    assert s.environment == "preview" and s.scripted_model
