"""Start the agent service for an eval run: a subprocess in the agent project's own environment.

The evals never import the agent. With no key the service runs its scripted model (free, deterministic, for CI and plumbing
checks); with ``live`` it uses the key in the environment. The run's own daily cap is set to the stage cap, so the service
itself stops spending when the stage budget is reached.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Service:
    base_url: str
    secret: str
    log_path: Path
    health: dict


def _uv() -> str:
    found = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if not Path(found).exists():
        raise RuntimeError("uv was not found: install it or put it on PATH to start the agent service")
    return found


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def service_env(*, live: bool, budget_usd: float | None, secret: str, spend_db: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for the service process. The API key is passed on only for a live run."""
    src = os.environ if base is None else base
    env = {k: v for k, v in src.items() if k in ("PATH", "HOME", "LANG", "TMPDIR", "SSL_CERT_FILE")}
    env.update({"UV_PYTHON_PREFERENCE": "only-managed", "AGENT_ENV": "test", "AGENT_SHARED_SECRET": secret,
                "AGENT_RELAX_LIMITS": "1", "AGENT_SPEND_DB": str(spend_db)})
    if budget_usd is not None:
        env["AGENT_DAILY_BUDGET_USD"] = str(budget_usd)
    if live:
        if not src.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("a live run needs ANTHROPIC_API_KEY in your environment")
        env["ANTHROPIC_API_KEY"] = src["ANTHROPIC_API_KEY"]
    else:
        env["AGENT_SCRIPTED_MODEL"] = "1"
    return env


@contextmanager
def launch(*, live: bool = False, budget_usd: float | None = None, startup_timeout: float = 90.0) -> Iterator[Service]:
    secret = secrets.token_hex(16)
    work = Path(tempfile.mkdtemp(prefix="agent-eval-"))
    port, log_path = _free_port(), work / "service.log"
    env = service_env(live=live, budget_usd=budget_usd, secret=secret, spend_db=work / "spend.db")
    with open(log_path, "wb") as log:
        proc = subprocess.Popen([_uv(), "run", "--project", str(REPO_ROOT / "agent"), "agent", "serve", "--port", str(port)],
                                cwd=REPO_ROOT / "agent", env=env, stdout=log, stderr=log)
    base_url, deadline = f"http://127.0.0.1:{port}", time.monotonic() + startup_timeout
    try:
        while True:
            if proc.poll() is not None:
                raise RuntimeError(f"the agent service exited with code {proc.returncode}: {log_path.read_text()[-600:]}")
            try:
                r = httpx.get(f"{base_url}/healthz", timeout=2.0)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"the agent service did not start within {startup_timeout:.0f} s: {log_path.read_text()[-600:]}")
            time.sleep(0.3)
        yield Service(base_url, secret, log_path, r.json())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
