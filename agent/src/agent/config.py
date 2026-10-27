"""Configuration from the environment, failing closed. No error message ever contains a secret's value."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ENVIRONMENTS = ("development", "test", "production")


class ConfigError(RuntimeError):
    """The service must not start with this configuration."""


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in ("1", "true", "yes")


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number") from None
    if value <= 0:
        raise ConfigError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    environment: str
    shared_secret: str | None
    api_key: str | None
    model_id: str
    scripted_model: bool
    local_dev: bool
    relaxed_limits: bool
    daily_budget_usd: float
    rate_per_minute: int
    rate_per_day: int
    max_message_chars: int
    max_tokens: int
    effort: str
    spend_db: Path
    model_dir: Path | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        environment = env.get("AGENT_ENV", "development").strip().lower()
        if environment not in ENVIRONMENTS:
            raise ConfigError(f"AGENT_ENV must be one of {', '.join(ENVIRONMENTS)}")
        production = environment == "production"
        scripted, local_dev, relaxed = (_flag(env, "AGENT_SCRIPTED_MODEL"), _flag(env, "AGENT_LOCAL_DEV"),
                                        _flag(env, "AGENT_RELAX_LIMITS"))
        secret = env.get("AGENT_SHARED_SECRET") or None
        api_key = env.get("ANTHROPIC_API_KEY") or None
        if production and scripted:
            raise ConfigError("AGENT_SCRIPTED_MODEL is not allowed when AGENT_ENV is production")
        if production and relaxed:
            raise ConfigError("AGENT_RELAX_LIMITS is not allowed when AGENT_ENV is production")
        if production and local_dev:
            raise ConfigError("AGENT_LOCAL_DEV is not allowed when AGENT_ENV is production")
        if secret is None and not local_dev:
            raise ConfigError("AGENT_SHARED_SECRET is not set (set AGENT_LOCAL_DEV=1 for local development without one)")
        if api_key is None and not scripted:
            raise ConfigError("ANTHROPIC_API_KEY is not set (set AGENT_SCRIPTED_MODEL=1 to run without a key, outside production)")
        effort = env.get("AGENT_EFFORT", "low").strip().lower()
        if effort not in ("low", "medium", "high"):
            raise ConfigError("AGENT_EFFORT must be low, medium or high")
        high = 1_000_000 if relaxed else None
        return cls(
            environment=environment, shared_secret=secret, api_key=api_key,
            model_id=env.get("AGENT_MODEL_ID", "claude-haiku-5-5"), scripted_model=scripted, local_dev=local_dev,
            relaxed_limits=relaxed,
            daily_budget_usd=1_000_000.0 if relaxed and "AGENT_DAILY_BUDGET_USD" not in env else _number(env, "AGENT_DAILY_BUDGET_USD", 2.0),
            rate_per_minute=int(high or _number(env, "AGENT_RATE_PER_MINUTE", 10)),
            rate_per_day=int(high or _number(env, "AGENT_RATE_PER_DAY", 200)),
            max_message_chars=int(_number(env, "AGENT_MAX_MESSAGE_CHARS", 6000)),
            max_tokens=int(_number(env, "AGENT_MAX_TOKENS", 2000)),
            effort=effort,
            spend_db=Path(env.get("AGENT_SPEND_DB", "spend.db")),
            model_dir=Path(env["RISK_MODEL_DIR"]) if env.get("RISK_MODEL_DIR") else None,
        )
