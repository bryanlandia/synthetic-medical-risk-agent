"""Rating files: what one rater (a clinician or an LLM reviewer) said about each blind note.

One file per rater, ``ratings.<rater>.json``, next to the round's ``sheet.json``. The rater kind is set when the
file is created (by the app's launch settings or by the reviewer command), never by the rater while rating.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..labs import SYMPTOM_KEYS

RATINGS_VERSION = 1
RaterKind = Literal["human", "llm"]
PlausibleValue = Literal["y", "n"]
SymptomValue = Literal["present", "possible", "absent", "none"]
_SAFE = re.compile(r"[^a-z0-9._-]+")


class NoteRating(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plausible: PlausibleValue | None = None
    symptoms: dict[str, SymptomValue | None] = Field(default_factory=dict)
    comment: str = ""
    reason: str = ""  # an LLM reviewer's one-sentence reason for an 'n'

    @model_validator(mode="after")
    def _known_symptoms(self) -> "NoteRating":
        unknown = set(self.symptoms) - set(SYMPTOM_KEYS)
        if unknown:
            raise ValueError(f"unknown symptom keys: {sorted(unknown)}")
        return self

    @property
    def complete(self) -> bool:
        return self.plausible is not None and all(self.symptoms.get(k) for k in SYMPTOM_KEYS)


class RatingFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = RATINGS_VERSION
    rater: str = Field(min_length=1, max_length=80)
    kind: RaterKind
    model_id: str | None = None  # llm only
    prompt_version: str | None = None  # llm only
    ratings: dict[str, NoteRating] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _llm_provenance(self) -> "RatingFile":
        if self.kind == "llm" and not (self.model_id and self.prompt_version):
            raise ValueError("an llm rating file must record model_id and prompt_version")
        if self.kind == "human" and (self.model_id or self.prompt_version):
            raise ValueError("a human rating file cannot carry a model id or prompt version")
        return self


def rater_slug(name: str) -> str:
    slug = _SAFE.sub("-", name.strip().lower()).strip("-.")
    if not slug:
        raise ValueError("rater name has no usable characters")
    return slug[:60]


def rating_path(directory: Path | str, rater: str) -> Path:
    return Path(directory) / f"ratings.{rater_slug(rater)}.json"


def write_rating_file(directory: Path | str, rf: RatingFile) -> Path:
    """Atomic write (temp file, then rename): a crash never leaves a half-written file."""
    path = rating_path(directory, rf.rater)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(rf.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return path


def read_rating_file(path: Path | str) -> RatingFile:
    return RatingFile.model_validate_json(Path(path).read_text())


def rating_files(directory: Path | str) -> list[Path]:
    return sorted(Path(directory).glob("ratings.*.json"))
