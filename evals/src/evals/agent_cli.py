"""``evals run --system agent``, ``evals agent-scope`` and ``evals estimate --system agent``.

A run starts the service itself (scripted model unless ``--live``) or attaches to one you started (``--base-url``). A live run
costs money, so it needs ``--yes``, prints its stage estimate first, and sets the service's own daily cap to the stage cap, so
the service stops spending by itself if the estimate was wrong.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION, agent_graders, scope_set
from .agent_service import launch
from .agent_system import AgentSystem
from .frontier import RESULTS_DIR as FRONTIER_RESULTS
from .frontier import stage_for
from .injection import injection_tag, strip_injection
from .ledger import FinalRunRequired, final_runs
from .messages import render_message
from .records import input_view, patient_key
from .runner import run_suites
from .suites import suite_records
from .summary import render_markdown, summarize, write_summary
from .transcripts import write_transcripts

RESULTS_ROOT = FRONTIER_RESULTS.parent
PRICE_IN, PRICE_OUT = 0.10, 0.50  # Haiku 5.5, dollars per million tokens
ASSUMED_IN, ASSUMED_OUT = 5200, 330  # two model calls per scored message, until a live dev run measures them
CAP_FACTOR, MIN_CAP = 1.5, 1.0


class NoDevRun(RuntimeError):
    pass


def results_dir(scripted: bool) -> Path:
    return RESULTS_ROOT / ("agent_scripted" if scripted else "agent")


def stage_calls(dataset: Any, stage: Any) -> int:
    """Distinct messages in the stage (a record in several suites is sent once per trial), times the trials."""
    messages: set[str] = set()
    suites = suite_records(dataset, stage.split)
    for name, records in suites.items():
        if stage.suites and name not in stage.suites:
            continue
        for r in records:
            view = input_view(r)
            messages.add(render_message(view))
            if name == "adversarial" and injection_tag(r):
                messages.add(render_message(strip_injection(view)))
    return len(messages) * stage.trials


def per_call_cost(root: Path | None = None) -> tuple[float, str]:
    """Mean dollars per scored call from a live dev run if there is one, else from the assumed token counts."""
    measured = (root or results_dir(False)) / "dev" / "calls.jsonl"
    if measured.exists():
        rows = [json.loads(line) for line in measured.read_text().splitlines() if line.strip()]
        paid = [r["cost_usd"] for r in rows if r["status"] == 200 and r.get("model_calls") and not r.get("cached")]
        if paid:
            return sum(paid) / len(paid), f"measured on {len(paid)} calls of the live dev run"
    return (ASSUMED_IN * PRICE_IN + ASSUMED_OUT * PRICE_OUT) / 1e6, f"assumed {ASSUMED_IN} input and {ASSUMED_OUT} output tokens a call"


def stage_cap(calls: int, unit: float) -> float:
    return round(max(MIN_CAP, CAP_FACTOR * calls * unit), 2)


def cmd_estimate(args: Any, dataset: Any) -> int:
    unit, basis = per_call_cost()
    print(f"agent on Haiku 5.5; {basis}")
    names = ["dev", "test", "adversarial", "trials"] if args.stage == "all" else [args.stage]
    total = 0.0
    for name in names:
        stage = stage_for("test" if name == "trials" else name, ["consistency"] if name == "trials" else None, 3 if name == "trials" else 1)
        calls = stage_calls(dataset, stage)
        cost = calls * unit
        total += cost
        print(f"{name:<12} {calls:>6} calls  ~${cost:,.2f}  cap ${stage_cap(calls, unit):.2f}")
    scope = len(scope_set.load()) + sum("clean" in r for r in scope_set.load())
    print(f"{'scope':<12} {scope:>6} calls  ~${scope * unit:,.2f}  cap ${stage_cap(scope, unit):.2f}")
    print(f"total ~${total + scope * unit:,.2f}\nno call was made and no key was needed")
    return 0


@contextmanager
def connect(args: Any, cap: float | None) -> Iterator[AgentSystem]:
    if getattr(args, "base_url", None):
        yield AgentSystem(args.base_url, getattr(args, "secret", None) or os.environ.get("AGENT_SHARED_SECRET"))
        return
    with launch(live=bool(getattr(args, "live", False)), budget_usd=cap if getattr(args, "live", False) else None) as service:
        yield AgentSystem(service.base_url, service.secret)


def _check_live(args: Any, calls: int, unit: float) -> int | None:
    if not getattr(args, "live", False) or getattr(args, "base_url", None):
        return None
    cap = stage_cap(calls, unit)
    print(f"live run: {calls} calls, about ${calls * unit:,.2f}, stage cap ${cap:.2f} (the service stops at the cap)")
    if not args.yes:
        print("error: a live run spends money: pass --yes to go ahead", file=sys.stderr)
        return 2
    return None


def _dev_version(directory: Path) -> str | None:
    path = directory / "dev" / "run.json"
    return json.loads(path.read_text()).get("system_version") if path.exists() else None


def cmd_run(args: Any, dataset: Any, out_root: Path | None = None, ledger_path: Path | None = None) -> int:
    try:
        stage = stage_for(args.split, args.suites, args.trials)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    unit, _ = per_call_cost()
    calls = stage_calls(dataset, stage)
    if (code := _check_live(args, calls, unit)) is not None:
        return code
    protected = stage.split in ("test", "adversarial")
    with connect(args, stage_cap(calls, unit)) as system:
        scripted = system.health.get("model_id") == "scripted"
        base = out_root or results_dir(scripted)
        try:
            if protected:
                if _dev_version(base) != system.version:
                    raise NoDevRun(f"{stage.split} is only scored for a system version that has had a dev run: "
                                   f"run `--split dev` first ({system.version})")
                if not args.final:
                    raise FinalRunRequired(f"{stage.split} is only scored in a final run: pass --final")
                if final_runs(system.version, stage.split, ledger_path, stage.name) and not args.force:
                    raise FinalRunRequired(f"{stage.name} has already had its final run for this system: a repeat is a second look "
                                           "at the protected data. Pass --force to repeat it anyway (it is recorded and warned about).")
        except (NoDevRun, FinalRunRequired) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out) if args.out else base / stage.name
        run = run_suites(dataset, system, stage.split, suites=args.suites, limit=args.limit, trials=stage.trials, final=args.final,
                         log_dir=out / "inspect", ledger_path=ledger_path, ledger_stage=stage.name if protected else None,
                         workers=getattr(args, "workers", 8))
        summary = summarize(dataset, run, reference=False)
        keys = {c["record_id"]: patient_key(dataset.record(c["record_id"])) for c in system.calls}
        summary["rows"] += agent_graders.record_rows(system.calls, keys)
        write_transcripts(run.rows, out / "trials.jsonl")
        write_summary(summary, out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "calls.jsonl").write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in system.calls))
        spend = sum(c["cost_usd"] for c in system.calls if not c.get("cached"))
        (out / "run.json").write_text(json.dumps({"system_version": system.version, "stage": stage.name, "limit": args.limit,
                                                  "calls": len(system.calls), "spend_usd": round(spend, 4), "stopped": run.stopped},
                                                 indent=2, sort_keys=True) + "\n")
    print(render_markdown(summary))
    print(f"wrote {out}/ ({len(run.rows)} transcripts); spend ${spend:.4f}")
    return 0


def cmd_scope(args: Any, dataset: Any = None, out_root: Path | None = None) -> int:
    prompts = scope_set.load()
    calls = len(prompts) + sum("clean" in p for p in prompts)
    unit, _ = per_call_cost()
    if (code := _check_live(args, calls, unit)) is not None:
        return code
    results = []
    with connect(args, stage_cap(calls, unit)) as system:
        scripted = system.health.get("model_id") == "scripted"
        for p in prompts:
            status, body = system.post(p["text"])
            r = {**p, "status": status, "declined": bool(body.get("declined")), "decline_reason": body.get("decline_reason"),
                 "reply": body.get("reply"), "reply_source": body.get("reply_source"), "tool_calls": (body.get("usage") or {}).get("tool_calls", 0),
                 "probability": (body.get("report") or {}).get("probability"), "cost_usd": (body.get("usage") or {}).get("cost_usd", 0.0)}
            if "clean" in p:
                _, clean = system.post(p["clean"])
                r["clean_probability"] = (clean.get("report") or {}).get("probability")
                r["cost_usd"] += (clean.get("usage") or {}).get("cost_usd", 0.0)
            results.append(r)
        version = system.version
    rows = agent_graders.grade_scope(results)
    out = (out_root or results_dir(scripted)) / "scope"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in results))
    summary = {"notice": SYNTHETIC_NOTICE, "harness_version": HARNESS_VERSION, "system_version": version, "split": "scope",
               "dataset_config_hash": "n/a (committed prompt set)", "seed": 0, "n_boot": 1000, "reference": False, "rows": rows,
               "mdd_note": "The scope set is a fixed list of prompts; each prompt is its own cluster."}
    write_summary(summary, out)
    print(render_markdown(summary))
    print(f"wrote {out}/ ({len(results)} prompts); spend ${sum(r['cost_usd'] for r in results):.4f}")
    return 0
