"""Inference for the note reader and the risk classifier: numpy and the standard library only."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .classifier import RiskClassifier
from .reader import NoteReader
from .report import build

# Bumped when the report logic (conflict rule, data-quality checks, evidence wording) changes without a new model file,
# so that a system version names the behavior and not only the weights.
LOGIC_VERSION = "1"

MODEL_FILES = ("reader.json", "classifier.json")  # the model: its hash is the hash of these two files

__all__ = ["RiskClassifier", "NoteReader", "RiskModel", "load", "model_hash", "LOGIC_VERSION"]


class RiskModel:
    """The committed model: the reader and the classifier behind one ``report(view)`` call."""

    def __init__(self, reader: NoteReader, classifier: RiskClassifier):
        self.reader, self.classifier = reader, classifier

    def report(self, view: dict[str, Any]) -> dict[str, Any]:
        return build(view, self.reader, self.classifier)


def default_directory() -> Path:
    """``RISK_MODEL_DIR``, else ``training/model`` beside this project (the repository layout)."""
    env = os.environ.get("RISK_MODEL_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "training" / "model"


def load(directory: Path | str | None = None) -> RiskModel:
    directory = Path(directory) if directory is not None else default_directory()
    return RiskModel(NoteReader(json.loads((directory / "reader.json").read_text())),
                     RiskClassifier(json.loads((directory / "classifier.json").read_text())))


def model_hash(directory: Path | str | None = None) -> str:
    """SHA-256 over the model files' names and bytes: what a manifest, a ledger entry and a health check call the model."""
    directory = Path(directory) if directory is not None else default_directory()
    h = hashlib.sha256()
    for name in MODEL_FILES:
        h.update(name.encode() + b"\0" + (directory / name).read_bytes())
    return h.hexdigest()
