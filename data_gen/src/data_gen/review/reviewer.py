"""Direct-mode review: one call per note, cached and capped like the writer, then a rating file of kind ``llm``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..config import GenConfig
from ..llm.client import LLMCallError, LLMClient, LLMRefusal
from ..llm.gateway import BudgetExceeded, DiskCache
from ..llm.pool import ordered_parallel
from ..llm.ratings import NoteRating, RatingFile, write_rating_file
from .prompt import REVIEWER_SYSTEM, parse_review, review_prompt

log = logging.getLogger("data_gen.review")


class ReviewerConfigError(ValueError):
    pass


def check_independent(cfg: GenConfig) -> None:
    if cfg.llm.reviewer_model_id == cfg.llm.model_id:
        raise ReviewerConfigError(
            f"the reviewer must be a different model from the note writer ({cfg.llm.model_id}); "
            "an independent model is required. Set llm.reviewer_model_id.")


def reviewer_name(cfg: GenConfig) -> str:
    return f"reviewer-{cfg.llm.reviewer_model_id}"


@dataclass
class ReviewResult:
    ratings: dict[str, NoteRating] = field(default_factory=dict)
    unrated: list[str] = field(default_factory=list)  # note ids with no valid rating after the attempts
    path: Path | None = None
    stopped: str | None = None  # why the run ended early (a cap), if it did


def load_blind_sheet(round_dir: Path) -> dict:
    return json.loads((Path(round_dir) / "sheet.json").read_text())


def review_note(client: LLMClient, cfg: GenConfig, text: str) -> NoteRating | None:
    for attempt in range(cfg.llm.reviewer_max_attempts):
        try:
            result = client.complete(system=REVIEWER_SYSTEM, prompt=review_prompt(text), model=cfg.llm.reviewer_model_id,
                                     max_tokens=cfg.llm.reviewer_max_tokens, nonce=attempt)
        except LLMRefusal:
            continue
        except LLMCallError as exc:
            if not exc.retryable:
                raise
            continue
        if result.stop_reason == "max_tokens":
            continue  # a cut-off answer is never trusted
        if (rating := parse_review(result.text)) is not None:
            return rating
    return None


def review_round(cfg: GenConfig, client: LLMClient, round_dir: Path, progress=None) -> ReviewResult:
    """Rate every note of a round. A cap or a fatal error ends the run, but ratings already made are saved."""
    check_independent(cfg)
    sheet = load_blind_sheet(round_dir)
    notes = sheet["notes"]
    out = ReviewResult()
    stream = ordered_parallel(lambda n: review_note(client, cfg, n["text"]), notes, cfg.llm.concurrency)
    try:
        for note, rating in stream:
            if rating is None:
                out.unrated.append(note["id"])
            else:
                out.ratings[note["id"]] = rating
            if progress:
                progress(rated=len(out.ratings), unrated=len(out.unrated), total=len(notes))
    except BudgetExceeded as exc:
        out.stopped = str(exc)
        out.unrated += [n["id"] for n in notes if n["id"] not in out.ratings and n["id"] not in out.unrated]
    finally:
        stream.close()
        out.path = save_review(cfg, round_dir, out.ratings)
    return out


def save_review(cfg: GenConfig, round_dir: Path, ratings: dict[str, NoteRating]) -> Path:
    rf = RatingFile(rater=reviewer_name(cfg), kind="llm", model_id=cfg.llm.reviewer_model_id,
                    prompt_version=cfg.llm.reviewer_prompt_version, ratings=ratings)
    return write_rating_file(round_dir, rf)


def controls_gap(ratings: dict[str, NoteRating], key: dict) -> dict | None:
    """Plausible rates of the LLM-written notes and the template controls, or None if there are no controls."""
    def rate(kind: str) -> tuple[float, int] | None:
        ids = [i for i, m in key["notes"].items() if m["kind"] == kind and ratings.get(i) and ratings[i].plausible]
        if not ids:
            return None
        return sum(ratings[i].plausible == "y" for i in ids) / len(ids), len(ids)

    notes, controls = rate("note"), rate("control")
    if notes is None or controls is None:
        return None
    return {"notes_rate": notes[0], "controls_rate": controls[0], "gap": notes[0] - controls[0],
            "n_notes": notes[1], "n_controls": controls[1]}
