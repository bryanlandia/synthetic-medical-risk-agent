"""The ASGI app built from the environment: the object a platform or ``uvicorn agent.asgi:app`` imports."""

from __future__ import annotations

from fastapi import FastAPI

from .app import create_app
from .config import Settings
from .runtime import build_orchestrator


def build() -> FastAPI:
    settings = Settings.from_env()
    return create_app(settings, build_orchestrator(settings))


app = build()
