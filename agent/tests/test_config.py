import pytest

from agent.config import ConfigError, Settings

from conftest import API_KEY, SECRET, env


def start(tmp_path, **over):
    return Settings.from_env(env(tmp_path, **over))


def test_a_complete_configuration_starts(tmp_path):
    s = start(tmp_path)
    assert s.shared_secret == SECRET and s.model_id == "claude-haiku-5-5" and s.rate_per_minute == 10 and s.rate_per_day == 200
    assert s.max_message_chars == 6000 and s.daily_budget_usd == 2.0 and not s.relaxed_limits


def test_no_shared_secret_stops_the_service_and_names_the_variable_not_a_value(tmp_path):
    e = env(tmp_path)
    del e["AGENT_SHARED_SECRET"]
    with pytest.raises(ConfigError, match="AGENT_SHARED_SECRET") as info:
        Settings.from_env(e)
    assert API_KEY not in str(info.value)


def test_local_development_mode_allows_no_secret(tmp_path):
    e = env(tmp_path, AGENT_LOCAL_DEV="1")
    del e["AGENT_SHARED_SECRET"]
    assert Settings.from_env(e).shared_secret is None


def test_no_api_key_stops_the_service_unless_the_scripted_model_is_on(tmp_path):
    e = env(tmp_path, AGENT_SCRIPTED_MODEL="0")
    del e["ANTHROPIC_API_KEY"]
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY") as info:
        Settings.from_env(e)
    assert SECRET not in str(info.value)
    assert Settings.from_env({**e, "AGENT_SCRIPTED_MODEL": "1"}).scripted_model


@pytest.mark.parametrize("name", ["AGENT_SCRIPTED_MODEL", "AGENT_RELAX_LIMITS", "AGENT_LOCAL_DEV"])
def test_testing_switches_are_refused_in_production(tmp_path, name):
    with pytest.raises(ConfigError, match=name):
        start(tmp_path, **{"AGENT_ENV": "production", "AGENT_SCRIPTED_MODEL": "0", name: "1"})


def test_production_with_a_secret_and_a_key_starts(tmp_path):
    s = start(tmp_path, AGENT_ENV="production", AGENT_SCRIPTED_MODEL="0")
    assert s.environment == "production"


def test_an_unknown_environment_and_bad_numbers_are_refused(tmp_path):
    with pytest.raises(ConfigError, match="AGENT_ENV"):
        start(tmp_path, AGENT_ENV="staging")
    with pytest.raises(ConfigError, match="AGENT_DAILY_BUDGET_USD"):
        start(tmp_path, AGENT_DAILY_BUDGET_USD="lots")
    with pytest.raises(ConfigError, match="positive"):
        start(tmp_path, AGENT_RATE_PER_MINUTE="0")


def test_relaxed_limits_raise_the_rate_and_budget_for_eval_runs(tmp_path):
    s = start(tmp_path, AGENT_RELAX_LIMITS="1")
    assert s.rate_per_minute >= 100_000 and s.daily_budget_usd >= 1_000
    assert start(tmp_path, AGENT_RELAX_LIMITS="1", AGENT_DAILY_BUDGET_USD="25").daily_budget_usd == 25.0


def test_the_token_ceiling_leaves_room_for_thinking_and_the_effort_is_low_by_default(tmp_path):
    s = start(tmp_path)
    assert s.max_tokens == 2000 and s.effort == "low" and s.model_timeout_s == 30.0
    assert start(tmp_path, AGENT_EFFORT="medium").effort == "medium"
    with pytest.raises(ConfigError, match="AGENT_EFFORT"):
        start(tmp_path, AGENT_EFFORT="extreme")


def test_the_real_model_is_built_with_the_ceiling_and_the_effort(tmp_path):
    from agent.runtime import build_orchestrator

    s = Settings.from_env(env(tmp_path, AGENT_SCRIPTED_MODEL="0"))
    orch = build_orchestrator(s)
    first, second = orch._model(), orch._model()
    assert first is not second and first.client is not second.client  # a client per request: loops are not shared
    config = first.get_config()
    assert config["max_tokens"] == 2000 and config["model_id"] == "claude-haiku-5-5"
    assert config["params"] == {"output_config": {"effort": "low"}}
