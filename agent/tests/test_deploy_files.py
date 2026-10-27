"""The repository-root files the agent's Vercel project is built from must agree with the agent's own pins."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pins(text: str) -> dict[str, str]:
    return {m.group(1).lower(): m.group(2) for m in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+(?:\[[a-z]+\])?)==([0-9][^",\s]*)', text, flags=re.M)}


def test_the_root_requirements_pin_what_the_agent_pins():
    deployed = _pins((ROOT / "requirements.txt").read_text())
    agent = _pins((ROOT / "agent" / "pyproject.toml").read_text())
    for name in ("fastapi", "httpx", "strands-agents[anthropic]"):
        assert deployed[name] == agent[name], name


def test_the_deployed_numpy_is_one_the_model_package_accepts():
    version = _pins((ROOT / "requirements.txt").read_text())["numpy"]
    major, minor = (int(x) for x in version.split(".")[:2])
    assert (major, minor) >= (2, 1) and major < 3  # risk_model asks for numpy>=2.1,<3


def test_the_function_entry_point_and_config_exist():
    assert (ROOT / "index.py").exists() and (ROOT / "vercel.json").exists()
    assert ".env*" in (ROOT / ".vercelignore").read_text()
