"""The pilot: a small sample of real dataset items, written first and rated by a human before the full run.

Pilot notes are items of the full dataset (same plans, same prompts), so unchanged prompts are served
from the cache in the full run and the pilot's spend is not wasted.

The rating sheet is blind: notes are shuffled across settings, no setting name appears in it, and the
mapping from note id to setting (plus the extractor's reading, for the accuracy gate) is written to a
separate key file that the rater must not open. Template-fixture notes are mixed in as controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..builder import build_record
from ..cohort import generate_cohort
from ..config import LLM_SETTINGS, GenConfig
from ..labs import SYMPTOM_KEYS
from ..seeds import rng_for
from .client import LLMClient
from .pool import ordered_parallel
from .run import PlanItem, plan_all
from .writer import ExclusionTally, NoteWriter

PLAUSIBLE_VALUES = ("y", "n")
SYMPTOM_VALUES = ("present", "possible", "absent", "none")  # 'none' = the note does not mention it
_PLAN_TO_LABEL = {"present": "present", "hedged": "possible", "negated": "absent"}


def pilot_candidates(
    cfg: GenConfig, items: list[PlanItem] | None = None, settings: tuple[str, ...] = LLM_SETTINGS, round_: int = 0,
) -> dict[str, list[PlanItem]]:
    """Ordinary train items per setting in a seeded order. ``round_`` draws a fresh, different ordering."""
    items = plan_all(cfg) if items is None else items
    pool = [i for i in items if i.split == "train" and i.case is None and i.pair_group is None]
    order = rng_for(cfg.seed, "notes", 999 + round_).permutation(len(pool))
    out: dict[str, list[PlanItem]] = {s: [] for s in settings}
    for idx in order:
        item = pool[int(idx)]
        if item.planned.plan.style in out:
            out[item.planned.plan.style].append(item)
    return out


def pilot_items(
    cfg: GenConfig, items: list[PlanItem] | None = None, settings: tuple[str, ...] = LLM_SETTINGS, round_: int = 0,
) -> list[PlanItem]:
    """``llm.pilot_per_setting`` items per setting (used for the estimate; the run tops up after exclusions)."""
    cands = pilot_candidates(cfg, items, settings, round_)
    return [i for s in settings for i in cands[s][: cfg.llm.pilot_per_setting]]


@dataclass
class PilotNote:
    record_id: str
    setting: str
    text: str
    plan_symptoms: dict[str, str]  # flag -> present | possible | absent (what the plan said)
    extraction: dict[str, str]  # the extractor's reading of the accepted note


@dataclass
class PilotResult:
    notes: list[PilotNote]
    tally: ExclusionTally
    short: dict[str, int] = field(default_factory=dict)  # settings that could not reach the target
    aborted: dict[str, float] = field(default_factory=dict)  # settings stopped early: exclusion rate when stopped


# Stop a setting early when most of its first attempts fail: that is a prompt, limit or checker problem,
# and working through every remaining candidate would only spend money on retries that cannot help.
BREAKER_MIN_ATTEMPTED = 8
BREAKER_RATE = 0.5


def run_pilot(
    cfg: GenConfig, client: LLMClient, items: list[PlanItem] | None = None,
    settings: tuple[str, ...] = LLM_SETTINGS, round_: int = 0, exclude: frozenset[str] | set[str] = frozenset(),
    progress=None,
) -> PilotResult:
    """Write notes until every requested setting has ``pilot_per_setting`` accepted ones (or candidates run out,
    or the setting is clearly failing)."""
    writer, tally = NoteWriter(client, cfg.llm), ExclusionTally()
    notes: list[PilotNote] = []
    short: dict[str, int] = {}
    aborted: dict[str, float] = {}
    target = cfg.llm.pilot_per_setting
    for setting, candidates in pilot_candidates(cfg, items, settings, round_).items():
        accepted = excluded = 0
        todo = [c for c in candidates if c.record_id not in exclude]  # excluded: already rated in an earlier round
        stream = ordered_parallel(lambda it: writer.write(it.planned.plan), todo, cfg.llm.concurrency)
        try:
            for item, outcome in stream:
                plan = item.planned.plan
                tally.record(plan, {a.type for a in item.planned.noise}, outcome)
                if outcome.accepted:
                    accepted += 1
                    notes.append(PilotNote(
                        record_id=item.record_id, setting=setting, text=outcome.text,
                        plan_symptoms={s.flag: _PLAN_TO_LABEL[s.stated] for s in plan.symptoms},
                        extraction=outcome.extraction or {}))
                else:
                    excluded += 1
                if progress:
                    progress(setting=setting, accepted=accepted, excluded=excluded, target=target, tally=tally)
                attempted = accepted + excluded
                if accepted >= target:
                    break
                if attempted >= BREAKER_MIN_ATTEMPTED and excluded / attempted > BREAKER_RATE:
                    aborted[setting] = round(excluded / attempted, 4)
                    break
        finally:
            stream.close()  # in-flight notes finish and are cached; they never enter the sample
        if accepted < target:
            short[setting] = target - accepted
    return PilotResult(notes, tally, short, aborted)


def used_record_ids(realism_dir, settings: tuple[str, ...]) -> set[str]:
    """Record ids already written to a rating sheet for these settings, across all earlier rounds."""
    import json
    from pathlib import Path

    used: set[str] = set()
    for key_file in sorted(Path(realism_dir).glob("round*/key.json")):
        for meta in json.loads(key_file.read_text())["notes"].values():
            if meta["kind"] == "note" and meta["setting"] in settings:
                used.add(meta["record_id"])
    return used


def control_notes(cfg: GenConfig) -> list[tuple[str, str]]:
    """Template-fixture notes (the old, unrealistic kind) to mix into the sheet, alternating the two styles."""
    n = cfg.llm.pilot_controls
    if n == 0:
        return []
    tcfg = GenConfig(seed=cfg.seed, n_train=cfg.n_train, n_test=cfg.n_test,
                     n_per_adversarial_type=cfg.n_per_adversarial_type, target_prevalence=cfg.target_prevalence)
    patients = [p for p in generate_cohort(tcfg) if p.split == "train"]
    order = rng_for(cfg.seed, "notes", 997).permutation(len(patients))
    out = []
    for k, idx in enumerate(order[: n * 4]):
        rec = build_record(tcfg, patients[int(idx)], "train", None)
        if rec.style == ("terse" if k % 2 == 0 else "templated"):
            out.append((rec.patient_id, rec.input.note))
        if len(out) == n:
            break
    return out


SHEET_HEADER = """# Realism rating sheet

All data here is fictional. Rate each note on its own, without looking at where it came from. DO NOT open
`key.json` until you have finished.

For every note fill in these lines (replace the blank after the colon):

- `plausible:` `y` if it reads like something a clinician or a documentation tool could really have
  written for a visit, `n` if it reads wrong, stilted, or artificial.
- `tremor`, `fatigue`, `photophobia`, `joint_stiffness`, `dizziness`: how the NOTE describes that symptom:
  `present`, `possible` (uncertain or hedged), `absent` (denied or negative), or `none` (not mentioned).
- `comment:` optional, free text.

Save the filled sheet as `ratings.md` next to this file.
"""


def _reveals_setting(text: str) -> str | None:
    lowered = text.lower().replace("-", " ").replace("_", " ")
    return next((s for s in LLM_SETTINGS if s.replace("_", " ") in lowered), None)


def build_sheet(cfg: GenConfig, notes: list[PilotNote], controls: list[tuple[str, str]]) -> tuple[str, dict]:
    """(sheet markdown, key). Shuffled, no setting names; the key maps every note id back."""
    for text in [n.text for n in notes] + [t for _, t in controls]:
        if (leak := _reveals_setting(text)):
            raise ValueError(f"a note names its own setting ({leak!r}); the sheet would not be blind")
    entries: list[tuple[str, str, dict]] = []
    for n in notes:
        entries.append((n.text, "note", {"record_id": n.record_id, "setting": n.setting,
                                         "plan_symptoms": n.plan_symptoms, "extraction": n.extraction}))
    for rid, text in controls:
        entries.append((text, "control", {"record_id": rid, "setting": "control"}))
    order = rng_for(cfg.seed, "notes", 998).permutation(len(entries))
    parts = [SHEET_HEADER]
    key: dict[str, dict] = {}
    for pos, idx in enumerate(order, start=1):
        text, kind, meta = entries[int(idx)]
        note_id = f"n{pos:02d}"
        key[note_id] = {"kind": kind, **meta}
        fields = "\n".join(f"{k}:" for k in ("plausible", *SYMPTOM_KEYS, "comment"))
        parts.append(f"---\n\n## {note_id}\n\n```\n{text}\n```\n\n{fields}\n")
    return "\n".join(parts), key


def write_pilot(
    cfg: GenConfig, result: PilotResult, directory, round_: int,
    settings: tuple[str, ...] = LLM_SETTINGS, estimated_spend_usd: float | None = None,
) -> dict:
    """Write ``sheet.md`` (blind) and ``key.json`` (setting, plan and extractor reading per note id)."""
    import json
    from pathlib import Path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    controls = control_notes(cfg) if round_ == 0 else []  # controls go into the first sheet only
    sheet, notes_key = build_sheet(cfg, result.notes, controls)
    meta = {
        "round": round_,
        "settings": list(settings),
        "model_id": cfg.llm.model_id,
        "prompt_version": cfg.llm.prompt_version,
        "exclusion_rates": {s: round(result.tally.exclusion_rate(s), 4) for s in settings},
        "short_of_target": result.short,
        "aborted_early": result.aborted,
        "estimated_spend_usd": estimated_spend_usd,
        "tally": result.tally.as_dict(),
    }
    (directory / "sheet.md").write_text(sheet)
    (directory / "key.json").write_text(json.dumps({"meta": meta, "notes": notes_key}, indent=2, sort_keys=True) + "\n")
    return meta
