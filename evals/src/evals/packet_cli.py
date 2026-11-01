"""``evals packet {estimate,run,freeze,fixtures}``: the PET-CT readiness packet, scored through the service's HTTP interface.

The same rules as the agent system: iterate on dev, a protected stage needs a dev run of the same system version, a freeze and
``--final``, is recorded once in the ledger, and a repeat needs ``--force``. A live run spends money, so it needs ``--yes`` and
sets the service's own daily cap to the stage cap.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION, packet_eval as pe
from .agent_cli import CAP_FACTOR, MIN_CAP, PRICE_IN, PRICE_OUT, RESULTS_ROOT, connect
from .agent_system import RETRYABLE, AgentSystem
from .ledger import FinalRunRequired, final_runs, record_final_run
from .messages import render_message
from .records import input_view, patient_key
from .summary import render_markdown, write_summary

ASSUMED_IN, ASSUMED_OUT = 1100, 600  # one summary call: the criteria table, the evidence and the prompt in; the sentences out
STAGES = ("dev", "test", "adversarial")


def results_dir(scripted: bool) -> Path:
    return RESULTS_ROOT / ("packet_scripted" if scripted else "packet")


def version_of(system: AgentSystem) -> str:
    h = system.health
    return f"{system.version}+pk{h.get('packet_prompt_hash', '?')}+{h.get('policy_id', '?')}"


def post_packet(system: AgentSystem, message: str, answers: dict[str, str]) -> dict[str, Any]:
    """One packet request: ``{status, body}``. A transport error is status 0."""
    for attempt in (1, 2):
        try:
            r = system.http.post("/packet", json={"message": message, "attestations": pe.wire(answers)})
            try:
                body = r.json()
            except ValueError:
                body = {"error": "unreadable body"}
            return {"status": r.status_code, "body": body if isinstance(body, dict) else {"error": "unexpected body"}}
        except RETRYABLE as exc:
            if attempt == 2:
                return {"status": 0, "body": {"error": type(exc).__name__}}
        except httpx.HTTPError as exc:
            return {"status": 0, "body": {"error": type(exc).__name__}}
    return {"status": 0, "body": {}}


def stage_calls(dataset: Any, split: str) -> int:
    if split == "adversarial":
        cases = pe.adversarial_cases(dataset)
        return len({c["message"] for c in cases} | {c["control"] for c in cases if c["control"]})
    return len(pe.stage_records(dataset, split))


def unit_cost() -> float:
    return (ASSUMED_IN * PRICE_IN + ASSUMED_OUT * PRICE_OUT) / 1e6


def stage_cap(calls: int) -> float:
    return round(max(MIN_CAP, CAP_FACTOR * calls * unit_cost()), 2)


def cmd_estimate(args: Any, dataset: Any) -> int:
    print(f"packet on Haiku 5.5; assumed {ASSUMED_IN} input and {ASSUMED_OUT} output tokens a call")
    total = 0.0
    for split in STAGES:
        calls = stage_calls(dataset, split)
        total += calls * unit_cost()
        print(f"{split:<12} {calls:>6} calls  ~${calls * unit_cost():,.2f}  cap ${stage_cap(calls):.2f}")
    print(f"total ~${total:,.2f}\nno call was made and no key was needed")
    return 0


def cmd_fixtures(args: Any, dataset: Any) -> int:
    text = pe.fixtures_text(dataset)
    if args.write:
        pe.FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pe.FIXTURE_PATH.write_text(text)
        print(f"wrote {pe.FIXTURE_PATH}")
        return 0
    same = pe.FIXTURE_PATH.exists() and pe.FIXTURE_PATH.read_text() == text
    print("fixtures are current" if same else "fixtures differ from a fresh draw (run with --write)")
    return 0 if same else 1


def _dev_version(base: Path) -> str | None:
    path = base / "dev" / "run.json"
    return json.loads(path.read_text()).get("system_version") if path.exists() else None


def _frozen_version(base: Path) -> str | None:
    path = base / "freeze.json"
    return json.loads(path.read_text()).get("system_version") if path.exists() else None


def cmd_freeze(args: Any, dataset: Any = None, out_root: Path | None = None) -> int:
    base = out_root or results_dir(bool(getattr(args, "scripted", False)))
    version = _dev_version(base)
    if version is None:
        print("error: no dev run to freeze: run `evals packet run --split dev` first", file=sys.stderr)
        return 2
    base.mkdir(parents=True, exist_ok=True)
    (base / "freeze.json").write_text(json.dumps({"system_version": version}, indent=2) + "\n")
    print(f"froze {version}: iteration on the packet is over; test and adversarial may be run once each")
    return 0


def _run_standard(system: AgentSystem, dataset: Any, split: str, limit: int | None, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    answers = pe.load_fixtures()
    records = pe.stage_records(dataset, split)[: limit or None]

    def one(record: Any) -> dict[str, Any]:
        given = answers[record.patient_id]
        result = post_packet(system, render_message(input_view(record)), given)
        body = result["body"]
        packet = body if result["status"] == 200 and not body.get("declined") else None
        return {"record_id": record.patient_id, "key": patient_key(record), "status": result["status"], "packet": packet,
                "reference": pe.reference(record, given), "answers": given}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        calls = list(pool.map(one, records))
    return calls, pe.grade(calls)


def _run_adversarial(system: AgentSystem, dataset: Any, limit: int | None, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = pe.adversarial_cases(dataset)[: limit or None]
    messages = sorted({c["message"] for c in cases} | {c["control"] for c in cases if c["control"]})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = dict(zip(messages, pool.map(lambda m: post_packet(system, m, {}), messages)))
    items = [{"case": c, "result": got[c["message"]], "control": got[c["control"]] if c["control"] else None} for c in cases]
    calls = [{"id": i["case"]["id"], "kind": i["case"]["kind"], "resisted": pe.resisted(i["case"], i["result"], i["control"]),
              "status": i["result"]["status"], "declined": i["result"]["body"].get("declined"),
              "summary_source": i["result"]["body"].get("summary_source")} for i in items]
    return calls, pe.grade_adversarial(items)


def cmd_run(args: Any, dataset: Any, out_root: Path | None = None, ledger_path: Path | None = None) -> int:
    split = args.split
    calls_planned = stage_calls(dataset, split)
    if getattr(args, "live", False) and not getattr(args, "base_url", None):
        cap = stage_cap(calls_planned)
        print(f"live run: {calls_planned} calls, about ${calls_planned * unit_cost():,.2f}, stage cap ${cap:.2f} (the service stops at the cap)")
        if not args.yes:
            print("error: a live run spends money: pass --yes to go ahead", file=sys.stderr)
            return 2
    protected = split in ("test", "adversarial")
    started = time.monotonic()
    with connect(args, stage_cap(calls_planned)) as system:
        scripted = system.health.get("model_id") == "scripted"
        base = out_root or results_dir(scripted)
        version = version_of(system)
        try:
            if protected:
                if _dev_version(base) != version:
                    raise FinalRunRequired(f"{split} is only scored for a system version that has had a dev run: run `--split dev` first ({version})")
                if _frozen_version(base) != version:
                    raise FinalRunRequired("freeze first: run `evals packet freeze` after the dev run; it ends iteration on the packet")
                if not args.final:
                    raise FinalRunRequired(f"{split} is only scored in a final run: pass --final")
                if final_runs(version, split, ledger_path, "packet") and not args.force:
                    raise FinalRunRequired(f"the packet {split} stage has already had its final run for this system: a repeat is a second look "
                                           "at the protected data. Pass --force to repeat it anyway (it is recorded and warned about).")
        except FinalRunRequired as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if protected:
            record_final_run(version, split, final=True, path=ledger_path, stage="packet")
        workers = getattr(args, "workers", 8)
        if split == "adversarial":
            calls, rows = _run_adversarial(system, dataset, args.limit, workers)
        else:
            calls, rows = _run_standard(system, dataset, split, args.limit, workers)
    out = Path(args.out) if getattr(args, "out", None) else base / split
    summary = {"notice": SYNTHETIC_NOTICE, "harness_version": HARNESS_VERSION, "system_version": version, "split": split,
               "dataset_config_hash": dataset.config_hash, "seed": 0, "n_boot": 1000, "reference": False, "rows": rows,
               "mdd_note": "Patients are the clusters; an adversarial case is its own cluster.",
               "status_counts": _status_counts(calls)}
    write_summary(summary, out)
    (out / "calls.jsonl").write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in calls))
    (out / "run.json").write_text(json.dumps({"system_version": version, "split": split, "limit": args.limit, "calls": len(calls),
                                              "seconds": round(time.monotonic() - started, 1)}, indent=2, sort_keys=True) + "\n")
    print(render_markdown(summary))
    print(f"wrote {out}/ ({len(calls)} calls)")
    return 0


def _status_counts(calls: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """How many patients have each true status per criterion: an accuracy figure means little if one status is almost all of them."""
    counts: dict[str, dict[str, int]] = {}
    for c in pe.CRITERIA:
        seen = [x["reference"][c] for x in calls if "reference" in x]
        if seen:
            counts[c] = {s: seen.count(s) for s in ("met", "unmet", "unknown")}
    return counts
