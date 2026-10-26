"""The frontier baseline: a strong model with a good prompt, returning the risk report through a tool.

The prompt is a briefing, never the answer key (``tests/test_frontier_prompt.py`` enforces that). Prompt versions
are files; a system's version hashes the prompt and the model, so the cache and the ledger never mix versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_gen.llm.client import LLMClient
from data_gen.llm.gateway import Budget

from .prompt_system import PromptSystem, RunEstimate, estimate_calls, prompt_hash

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "frontier"
DEV_MODEL = "claude-haiku-5-5"
FINAL_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 4000  # thinking shares this budget with the tool call


def prompt_path(version: str) -> Path:
    return PROMPTS_DIR / f"{version}.md"


def load_prompt(version: str) -> str:
    path = prompt_path(version)
    if not path.exists():
        raise FileNotFoundError(f"no prompt file {path}")
    return path.read_text().strip()


def build_frontier_system(version: str, model: str, client: LLMClient, cache_path: Path | str,
                          budget: Budget) -> PromptSystem:
    return PromptSystem("frontier", load_prompt(version), model, client, cache_path, budget, max_tokens=MAX_TOKENS,
                        requires_freeze=True)


# --- stages, prices and caps -------------------------------------------------------------------------------------

PRICES_PER_MTOK = {DEV_MODEL: (0.10, 0.50), FINAL_MODEL: (2.0, 10.0)}  # input, output
ASSUMED_OUTPUT_TOKENS = 700  # tool call plus adaptive thinking, until the cache holds measurements
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "frontier"


class StageOverCap(RuntimeError):
    """The estimate for a stage is above its cap, so the stage is refused before any call."""


@dataclass(frozen=True)
class Stage:
    name: str
    split: str
    suites: tuple[str, ...] | None  # None: every suite the split has
    trials: int
    injection_pairs: bool
    max_calls: int  # about 1.25 x the expected calls
    max_usd: float  # about 1.5 x the Sonnet estimate, which leaves room for thinking tokens


STAGES: dict[str, Stage] = {s.name: s for s in (
    Stage("dev", "dev", None, 1, False, max_calls=650, max_usd=8.0),
    Stage("test", "test", None, 1, False, max_calls=1800, max_usd=25.0),
    Stage("adversarial", "adversarial", None, 1, True, max_calls=600, max_usd=10.0),
    Stage("trials", "test", ("consistency",), 3, False, max_calls=1700, max_usd=20.0),
)}


def stage_for(split: str, suites: list[str] | None, trials: int) -> Stage:
    if split == "test" and trials > 1:
        if suites != ["consistency"]:
            raise ValueError("repeated trials are only run on the matched-pair subset: use --suites consistency")
        return STAGES["trials"]
    if trials > 1:
        raise ValueError(f"repeated trials are only run on the test split's matched pairs, not {split}")
    return STAGES[split]


def cache_path(model: str) -> Path:
    return RESULTS_DIR / f"cache_{model}.jsonl"


def make_budget(model: str, stage: Stage) -> Budget:
    price_in, price_out = PRICES_PER_MTOK[model]
    return Budget(stage.max_calls, stage.max_usd, price_in, price_out)


def stage_records(dataset: Any, stage: Stage, limit: int | None = None) -> list[Any]:
    """The distinct records a stage runs (a record that is in several suites is called once)."""
    from .suites import suite_records

    by_suite = suite_records(dataset, stage.split)
    seen: dict[str, Any] = {}
    for name, records in by_suite.items():
        if stage.suites is None or name in stage.suites:
            for r in (records[:limit] if limit else records):
                seen.setdefault(r.patient_id, r)
    return list(seen.values())


def estimate_stage(system: PromptSystem, dataset: Any, stage: Stage, limit: int | None = None) -> RunEstimate:
    return estimate_calls(system, stage_records(dataset, stage, limit), stage.trials,
                          injection_pairs=stage.injection_pairs, assumed_output_tokens=ASSUMED_OUTPUT_TOKENS)


def check_cap(est: RunEstimate, stage: Stage) -> None:
    """Refuse a stage whose uncached calls or cost would pass its cap."""
    if est.uncached > stage.max_calls:
        raise StageOverCap(f"stage {stage.name}: {est.uncached} calls to make, cap is {stage.max_calls}")
    if est.cost_usd > stage.max_usd:
        raise StageOverCap(f"stage {stage.name}: estimated ${est.cost_usd:.2f}, cap is ${stage.max_usd:.2f}")
