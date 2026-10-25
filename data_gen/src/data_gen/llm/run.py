"""Plan and write an LLM-note dataset.

``plan_all`` is offline and deterministic: it lists every note to write (so the cost can be estimated
without a single API call). ``generate_llm`` writes them. Nothing is written to disk by ``generate_llm``;
``run_and_write`` writes the splits only after every note is done, so a cap or error halts the run with
no partial split (completed notes stay in the cache).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..adversarial import generate_adversarial
from ..builder import assemble_record, plan_for
from ..cohort import Patient, generate_cohort
from ..config import LLM_SETTINGS, GenConfig
from ..dataset_io import write_dataset
from ..plan import PlannedNote, _choose_missing, plan_note
from ..schema import Record
from ..seeds import rng_for
from .client import LLMClient
from .prompts import prompt_text_hash
from .pool import ordered_parallel
from .writer import ExclusionTally, NoteWriter, TooManyExclusions


# Stop the whole run if, after enough notes, most are being excluded: more calls cannot fix that.
GUARD_MIN_NOTES = 50
GUARD_RATE = 0.5


@dataclass
class PlanItem:
    patient: Patient
    split: str
    case: str | None
    planned: PlannedNote
    record_id: str
    pair_group: str | None = None


def choose_pair_patients(cfg: GenConfig, test_patients: list[Patient]) -> set[int]:
    k = min(cfg.llm.matched_pairs, len(test_patients))
    order = rng_for(cfg.seed, "split", 2).permutation(len(test_patients))
    return {test_patients[int(i)].index for i in order[:k]}


def pair_items(cfg: GenConfig, patient: Patient) -> list[PlanItem]:
    """One patient written in every setting: same labs, flags and lab panel, different documentation.

    Record ids end in -m1..-m4 assigned by a seeded shuffle, so an id never reveals its setting."""
    order = rng_for(cfg.seed, "notes", patient.index).permutation(len(LLM_SETTINGS))
    shared_missing = _choose_missing(cfg, rng_for(cfg.seed, "noise", patient.index, 0), None)
    items = []
    for j, setting_index in enumerate(order):
        setting = LLM_SETTINGS[int(setting_index)]
        planned = plan_note(
            cfg, patient.labs, patient.flags, rng_for(cfg.seed, "noise", patient.index, j + 1), None,
            style=setting, missing=shared_missing,
        )
        items.append(PlanItem(patient, "test", None, planned, f"{patient.patient_id}-m{j + 1}", patient.patient_id))
    return items


def plan_all(cfg: GenConfig) -> list[PlanItem]:
    if cfg.note_source != "llm":
        raise ValueError("plan_all is for note_source 'llm'")
    cohort = generate_cohort(cfg)
    pair_ids = choose_pair_patients(cfg, [p for p in cohort if p.split == "test"])
    items: list[PlanItem] = []
    for p in cohort:
        if p.index in pair_ids:
            items += pair_items(cfg, p)
        else:
            items.append(PlanItem(p, p.split, None, plan_for(cfg, p, None), p.patient_id))
    for patient, case in generate_adversarial(cfg):
        items.append(PlanItem(patient, "adversarial", case, plan_for(cfg, patient, case), patient.patient_id))
    return items


@dataclass
class RunResult:
    by_split: dict[str, list[Record]]
    tally: ExclusionTally
    pair_groups: int = 0
    pair_groups_dropped: int = 0
    stats: dict = field(default_factory=dict)


def generate_llm(
    cfg: GenConfig, client: LLMClient, items: list[PlanItem] | None = None,
    progress: Callable[..., None] | None = None,
) -> RunResult:
    """Write every note. Raises (for example BudgetExceeded) without writing anything to disk."""
    items = plan_all(cfg) if items is None else items
    writer, tally = NoteWriter(client, cfg.llm), ExclusionTally()
    by_split: dict[str, list[Record]] = {"train": [], "test": [], "adversarial": []}
    groups: dict[str, list[Record]] = defaultdict(list)
    all_groups: set[str] = set()
    failed_groups: set[str] = set()
    stream = ordered_parallel(lambda it: writer.write(it.planned.plan), items, cfg.llm.concurrency)
    try:
        for n, (item, outcome) in enumerate(stream):
            if item.pair_group:
                all_groups.add(item.pair_group)
            tally.record(item.planned.plan, {a.type for a in item.planned.noise}, outcome)
            if progress:
                progress(setting=item.planned.plan.style, accepted=sum(tally.accepted.values()),
                         excluded=sum(tally.excluded.values()), done=n + 1, total=len(items), tally=tally)
            if n + 1 >= GUARD_MIN_NOTES and tally.total_exclusion_rate() > GUARD_RATE:
                raise TooManyExclusions(
                    f"{tally.total_exclusion_rate():.0%} of the first {n + 1} notes were excluded (mostly: "
                    f"{tally.top_failures()}). Stopping before more money is spent; completed notes are cached.")
            if not outcome.accepted:
                if item.pair_group:
                    failed_groups.add(item.pair_group)
                continue
            record = assemble_record(
                cfg, item.patient, item.split, item.case, item.planned, outcome.text,
                patient_id=item.record_id, pair_group=item.pair_group)
            if item.pair_group:
                groups[item.pair_group].append(record)
            else:
                by_split[item.split].append(record)
    finally:
        stream.close()  # cancels notes not yet started; running ones finish and stay cached
    # A matched-pair group is all or nothing: one excluded member removes the group.
    for group, members in groups.items():
        if group not in failed_groups:
            by_split["test"] += members
    stats = _stats(cfg, client, tally, len(all_groups), len(failed_groups))
    return RunResult(by_split, tally, len(all_groups) - len(failed_groups), len(failed_groups), stats)


def _stats(cfg: GenConfig, client: LLMClient, tally: ExclusionTally, groups: int, dropped: int) -> dict:
    budget = getattr(client, "budget", None)
    return {
        "model_id": cfg.llm.model_id,
        "prompt_version": cfg.llm.prompt_version,
        "prompt_text_hashes": {s: prompt_text_hash(s) for s in LLM_SETTINGS},
        "paid_calls": getattr(client, "misses", None),
        "cache_hits": getattr(client, "hits", None),
        "estimated_spend_usd": round(budget.spend_usd, 4) if budget else None,
        "pair_groups_planned": groups,
        "pair_groups_dropped": dropped,
        **tally.as_dict(),
    }


def run_and_write(
    cfg: GenConfig, client: LLMClient, out_dir: Path, items: list[PlanItem] | None = None,
    progress: Callable[..., None] | None = None,
) -> RunResult:
    result = generate_llm(cfg, client, items, progress)  # raises before anything is written
    write_dataset(result.by_split, cfg, out_dir, llm_stats=result.stats)
    return result
