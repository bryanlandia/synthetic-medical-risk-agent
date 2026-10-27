"""Inference for the note reader and the risk classifier: numpy and the standard library only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .classifier import RiskClassifier
from .reader import NoteReader
from .report import build

# Bumped when the report logic (conflict rule, data-quality checks, evidence wording) changes without a new model file,
# so that a system version names the behavior and not only the weights.
LOGIC_VERSION = "1"

__all__ = ["RiskClassifier", "NoteReader", "RiskModel", "load", "LOGIC_VERSION"]


class RiskModel:
    """The committed model: the reader and the classifier behind one ``report(view)`` call."""

    def __init__(self, reader: NoteReader, classifier: RiskClassifier):
        self.reader, self.classifier = reader, classifier

    def report(self, view: dict[str, Any]) -> dict[str, Any]:
        return build(view, self.reader, self.classifier)


def load(directory: Path | str) -> RiskModel:
    directory = Path(directory)
    return RiskModel(NoteReader(json.loads((directory / "reader.json").read_text())),
                     RiskClassifier(json.loads((directory / "classifier.json").read_text())))
