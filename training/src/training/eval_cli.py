"""``evals run --system classifier``: the harness run for the committed model, with the one-look rule for the protected
splits (a frozen model hash, ``--final``, and no repeat without ``--force``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from evals.frontier import RESULTS_DIR as FRONTIER_RESULTS
from evals.frontier import stage_for
from evals.ledger import FinalRunRequired, final_runs
from evals.runner import run_suites
from evals.summary import render_markdown, summarize, write_summary
from evals.transcripts import write_transcripts

from .system import MODEL_DIR, ClassifierSystem

RESULTS_DIR = FRONTIER_RESULTS.parent / "classifier"
FROZEN_NAME = "frozen.json"


class NotFrozen(RuntimeError):
    pass


def freeze(directory: Path = MODEL_DIR) -> dict[str, Any]:
    """Record the model hash as the one the protected splits may be scored with. Refuses a model whose dev run is missing."""
    system = ClassifierSystem(directory)
    dev = RESULTS_DIR / "dev" / "run.json"
    if not dev.exists() or json.loads(dev.read_text()).get("system_version") != system.version:
        raise NotFrozen("run this model on dev first (`evals run --system classifier --split dev`), then freeze it")
    entry = {"model_hash": system.model_hash, "system_version": system.version}
    (Path(directory) / FROZEN_NAME).write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n")
    return entry


def require_frozen(system: ClassifierSystem, split: str) -> None:
    path = system.directory / FROZEN_NAME
    if not path.exists():
        raise NotFrozen(f"{split} is only scored with a frozen model: iterate on dev, then `training freeze`")
    frozen = json.loads(path.read_text())
    if frozen["system_version"] != system.version:
        raise NotFrozen(f"{split} must use the frozen model ({frozen['system_version']}), not {system.version}")


def cmd_run(args: Any, dataset: Any, directory: Path = MODEL_DIR, out_root: Path | None = None,
            ledger_path: Path | None = None) -> int:
    system = ClassifierSystem(directory)
    try:
        stage = stage_for(args.split, args.suites, args.trials)
        protected = stage.split in ("test", "adversarial")
        if protected:
            require_frozen(system, stage.split)
            if not args.final:
                raise FinalRunRequired(f"{stage.split} is only scored in a final run: pass --final")
            if final_runs(system.version, stage.split, ledger_path, stage.name) and not args.force:
                raise FinalRunRequired(f"{stage.name} has already had its final run for this model: a repeat is a second "
                                       "look at the protected data. Pass --force to repeat it anyway (it is recorded and "
                                       "warned about).")
    except (ValueError, NotFrozen, FinalRunRequired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else (out_root or RESULTS_DIR) / stage.name
    run = run_suites(dataset, system, stage.split, suites=args.suites, limit=args.limit, trials=stage.trials,
                     final=args.final, log_dir=out / "inspect", ledger_path=ledger_path,
                     ledger_stage=stage.name if protected else None, workers=1)
    summary = summarize(dataset, run, reference=False)
    write_transcripts(run.rows, out / "trials.jsonl")
    write_summary(summary, out)
    out.mkdir(parents=True, exist_ok=True)
    info = {"model_hash": system.model_hash, "system_version": system.version, "stage": stage.name,
            "limit": args.limit, "stopped": run.stopped}
    (out / "run.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    print(render_markdown(summary))
    print(f"wrote {out}/ ({len(run.rows)} transcripts)")
    return 0
