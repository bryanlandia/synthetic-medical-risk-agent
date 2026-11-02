"""``evals playground``: the dial and the assistant must agree on seeded invented patients, with and without a hidden instruction.

Needs no dataset. With no ``--live`` the service runs its scripted model (free); a live run spends money, so it needs ``--yes`` and the
service's own daily cap is set to the run's cap. ``--base-url URL --secret S`` checks a running service.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION, playground_eval as pg
from .agent_cli import RESULTS_ROOT, connect, per_call_cost, stage_cap


def results_dir(scripted: bool) -> Path:
    return RESULTS_ROOT / ("playground_scripted" if scripted else "playground")


def cmd_playground(args: Any, out_root: Path | None = None) -> int:
    n = args.n
    unit, _ = per_call_cost()
    calls = 2 * n  # two assistant calls a patient; the estimate route calls no model
    if args.live and not getattr(args, "base_url", None):
        cap = stage_cap(calls, unit)
        print(f"live run: {calls} calls, about ${calls * unit:,.2f}, cap ${cap:.2f} (the service stops at the cap)")
        if not args.yes:
            print("error: a live run spends money: pass --yes to go ahead", file=sys.stderr)
            return 2
    with connect(args, stage_cap(calls, unit)) as system:
        scripted = system.health.get("model_id") == "scripted"
        results = pg.run_check(system, n, args.seed)
        rows = pg.grade(results, seed=args.seed)
        base = out_root or results_dir(scripted)
        base.mkdir(parents=True, exist_ok=True)
        summary = {"notice": SYNTHETIC_NOTICE, "harness": HARNESS_VERSION, "system_version": system.version, "patients": n, "seed": args.seed,
                   "rows": rows, "disagreements": [c["key"] for c in results if not (c["patient_agrees"] and c["injection_unchanged"])]}
        (base / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    for row in rows:
        print(f"{row['metric']:<28} {row['value']:.3f}  [{row['lo']:.3f}, {row['hi']:.3f}]  {row['label']}")
    print(f"wrote {base / 'summary.json'}")
    return 0 if all(r["reached"] for r in rows) and len(rows) == 3 else 1
