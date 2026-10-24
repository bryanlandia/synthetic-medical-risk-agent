"""Versioned catalog of prompt-injection strings. Injection text always comes from here, never from an LLM."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .schema import PlanInjection

_PATH = Path(__file__).with_name("injection_catalog.json")


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_PATH.read_text())


def catalog_version() -> str:
    return _load()["version"]


def entries() -> list[PlanInjection]:
    return [PlanInjection(**e) for e in _load()["entries"]]


def categories() -> set[str]:
    return {e.category for e in entries()}


def all_texts() -> list[str]:
    return [e.text for e in entries()]
