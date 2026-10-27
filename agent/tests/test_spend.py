import pytest

from agent import pricing
from agent.spend import SpendCounter

from conftest import Counting, HEADERS

DAY = 86_400.0


def test_prices_are_pinned_and_an_unknown_model_is_refused_not_priced_at_zero():
    assert pricing.cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert pricing.cost_usd("claude-haiku-5-5", 1000, 200) == pytest.approx(0.0002)
    assert pricing.cost_usd("scripted", 10**6, 10**6) == 0
    with pytest.raises(KeyError):
        pricing.cost_usd("claude-unknown", 1, 1)


def test_the_total_adds_up_and_survives_a_restart(tmp_path):
    path = tmp_path / "spend.db"
    a = SpendCounter(path, 1.0, clock=lambda: 5 * DAY + 100)
    a.add(0.25)
    a.add(0.30)
    b = SpendCounter(path, 1.0, clock=lambda: 5 * DAY + 5000)  # a new process the same day
    assert b.total_today() == pytest.approx(0.55) and b.remaining() == pytest.approx(0.45) and not b.exhausted()


def test_the_day_rolls_over_at_midnight_utc(tmp_path):
    t = [5 * DAY + DAY - 10]
    s = SpendCounter(tmp_path / "spend.db", 0.5, clock=lambda: t[0])
    s.add(0.5)
    assert s.exhausted()
    t[0] += 20  # past midnight
    assert s.total_today() == 0 and not s.exhausted()
    s.add(0.1)
    t[0] -= 20  # the earlier day is still its own row
    assert s.total_today() == pytest.approx(0.5)


class Priced(Counting):
    model_id = "claude-haiku-5-5"


def test_when_the_cap_is_reached_the_next_request_is_503_and_the_model_is_not_called(make):
    client, orch, _ = make(Priced(), AGENT_DAILY_BUDGET_USD="0.0005")  # 0.0002 a request: the third reaches it
    codes = [client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 503, 503] and orch.calls == 3
    body = client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).json()
    assert body["error"] == "daily_budget_used" and "VLI" not in str(body)


def test_the_remaining_budget_after_a_restart_is_the_cap_minus_what_was_spent(make, tmp_path):
    client, orch, _ = make(Priced(), AGENT_DAILY_BUDGET_USD="0.0005")
    for _ in range(3):
        client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS)
    again, orch2, _ = make(Priced(), AGENT_DAILY_BUDGET_USD="0.0005")  # same spend file: a restart
    assert again.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).status_code == 503 and orch2.calls == 0


def test_a_request_that_starts_under_the_cap_may_finish(make):
    client, orch, _ = make(Priced(), AGENT_DAILY_BUDGET_USD="0.0001")  # one request costs 0.0002, more than the cap
    assert client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).status_code == 200
    assert client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).status_code == 503


def test_the_cost_of_each_request_is_reported_in_its_usage(make):
    client, _, _ = make(Priced())
    usage = client.post("/analyze", json={"message": "VLI 100"}, headers=HEADERS).json()["usage"]
    assert usage["cost_usd"] == pytest.approx(0.0002) and usage["input_tokens"] == 1000 and usage["output_tokens"] == 200
