"""The ``classifier`` system under test: the committed model behind the harness's ``run(view) -> report`` interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import risk_model

from . import pipeline

MODEL_DIR = pipeline.MODEL_DIR


class ClassifierSystem:
    """Deterministic and offline. Its version names the model files and the report logic."""

    name, reference = "classifier", False

    def __init__(self, directory: Path = MODEL_DIR):
        self.directory = Path(directory)
        self.model = risk_model.load(self.directory)
        self.model_hash = pipeline.model_hash(self.directory)
        self.version = f"classifier@{self.model_hash[:12]}+r{risk_model.LOGIC_VERSION}"

    def run(self, view: dict[str, Any]) -> dict[str, Any]:
        return self.model.report(view)
