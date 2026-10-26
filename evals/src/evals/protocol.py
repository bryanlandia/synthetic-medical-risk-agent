"""The prompt-iteration protocol, enforced by code and recorded in a tamper-evident file.

``results/frontier/prompt_versions.json`` is append-only. Every entry carries the hash of the entry before it, so
editing or removing an earlier entry is detected when the file is loaded. Entries are:

- ``version``: a new prompt (by hash) scored on dev. At most ``MAX_VERSIONS`` of these are allowed.
- ``dev_run``: a prompt that already has a version entry, scored on dev with another model (the final model's
  comparison run). It does not count toward the cap.
- ``freeze``: the prompt chosen for the protected splits. No version or dev run may follow it, and ``test`` and
  ``adversarial`` are refused until it exists and then only for that prompt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MAX_VERSIONS = 5
PROTOCOL_PATH = Path(__file__).resolve().parents[2] / "results" / "frontier" / "prompt_versions.json"
GENESIS = "0" * 16


class ProtocolError(RuntimeError):
    """The iteration protocol forbids this step (the message says which rule)."""


def _digest(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]


def load_chain(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or PROTOCOL_PATH
    if not path.exists():
        return []
    entries = json.loads(path.read_text())["entries"]
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("prev") != prev or e.get("hash") != _digest(e) or e.get("index") != i:
            raise ProtocolError(f"{path.name} was edited: entry {i} does not follow from the one before it")
        prev = e["hash"]
    return entries


def _append(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    entries = load_chain(path)
    entry = {**entry, "index": len(entries), "prev": entries[-1]["hash"] if entries else GENESIS}
    entry["hash"] = _digest(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": [*entries, entry]}, indent=2, sort_keys=True) + "\n")
    return entry


def versions(path: Path | None = None) -> list[dict[str, Any]]:
    return [e for e in load_chain(path) if e["kind"] == "version"]


def frozen(path: Path | None = None) -> dict[str, Any] | None:
    return next((e for e in load_chain(path) if e["kind"] == "freeze"), None)


def check_can_score_dev(prompt_hash: str, path: Path | None = None) -> str:
    """Raise unless the prompt may be scored on dev now. Returns ``version`` (a new prompt) or ``dev_run``."""
    path = path or PROTOCOL_PATH
    if frozen(path):
        raise ProtocolError("the prompt is frozen; dev iteration is over. Changing the prompt now would be a new look.")
    if any(v["prompt_hash"] == prompt_hash for v in versions(path)):
        return "dev_run"
    if len(versions(path)) >= MAX_VERSIONS:
        raise ProtocolError(f"{MAX_VERSIONS} prompt versions have already been scored on dev; a sixth is refused. "
                            "Freeze the best one with `evals freeze`.")
    return "version"


def record_dev_score(prompt_hash: str, prompt_version: str, model: str, metrics: dict[str, Any], *,
                     spend_usd: float, note: str = "", path: Path | None = None) -> dict[str, Any]:
    path = path or PROTOCOL_PATH
    kind = check_can_score_dev(prompt_hash, path)
    return _append(path, {"kind": kind, "prompt_hash": prompt_hash, "prompt_version": prompt_version, "model": model,
                          "metrics": metrics, "spend_usd": round(spend_usd, 4), "note": note})


def freeze(prompt_hash: str, *, path: Path | None = None) -> dict[str, Any]:
    path = path or PROTOCOL_PATH
    if frozen(path):
        raise ProtocolError("the prompt is already frozen")
    if not any(v["prompt_hash"] == prompt_hash for v in versions(path)):
        raise ProtocolError("only a prompt that was scored on dev can be frozen")
    return _append(path, {"kind": "freeze", "prompt_hash": prompt_hash})


def require_frozen(prompt_hash: str, split: str, path: Path | None = None) -> None:
    """Gate for the protected splits: the prompt must be the frozen one."""
    f = frozen(path)
    if f is None:
        raise ProtocolError(f"{split} is only scored with a frozen prompt: iterate on dev, then `evals freeze`")
    if f["prompt_hash"] != prompt_hash:
        raise ProtocolError(f"{split} must use the frozen prompt ({f['prompt_hash']}), not {prompt_hash}")
