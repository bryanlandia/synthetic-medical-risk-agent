"""The frontier baseline's commands: estimate, iterate, freeze and run. Paid steps need ``--yes`` and the key in the
environment; every other path (estimate, protocol checks, caps) needs neither."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from data_gen.llm.client import LLMResult, MissingApiKeyError

from . import protocol
from .frontier import (DEV_MODEL, FINAL_MODEL, RESULTS_DIR, STAGES, Stage, StageOverCap, build_frontier_system,
                       cache_path, check_cap, estimate_stage, load_prompt, make_budget, stage_for)
from .ledger import FinalRunRequired
from .prompt_system import PromptSystem
from .runner import run_suites
from .summary import render_markdown, summarize, write_summary
from .transcripts import write_transcripts

MODELS = {"haiku": DEV_MODEL, "sonnet": FINAL_MODEL, DEV_MODEL: DEV_MODEL, FINAL_MODEL: FINAL_MODEL}


class _NoClient:
    def complete(self, **_: Any) -> LLMResult:  # pragma: no cover - guards the keyless paths
        raise RuntimeError("a keyless command tried to call the API")


def make_client():
    """The paid client. A seam, so tests run the whole flow with a scripted one."""
    from .report_tool import ReportToolClient

    return ReportToolClient()


def _system(args: Any, stage: Stage, client: Any, cache: Path | None = None) -> PromptSystem:
    model = MODELS[args.model]
    return build_frontier_system(args.prompt, model, client, cache or cache_path(model), make_budget(model, stage))


def _show(name: str, est: Any, stage: Stage) -> str:
    over = est.uncached > stage.max_calls or est.cost_usd > stage.max_usd
    return (f"{name:<12} {est.calls:>5} calls ({est.cached} cached, {est.uncached} to make)  "
            f"~{est.input_tokens:,} in / {est.output_tokens:,} out tokens  ~${est.cost_usd:.2f}  "
            f"cap {stage.max_calls} calls / ${stage.max_usd:.2f}  {'OVER CAP' if over else 'ok'}"
            f"{'' if est.measured else '  (output tokens assumed)'}")


def cmd_estimate(args: Any, dataset: Any, cache: Path | None = None) -> int:
    stages = [STAGES[args.stage]] if args.stage != "all" else list(STAGES.values())
    system = _system(args, stages[0], _NoClient(), cache)
    print(f"prompt {args.prompt} (hash {system.prompt_hash}), model {system.model}, system {system.version}")
    for stage in stages:
        print(_show(stage.name, estimate_stage(system, dataset, stage), stage))
    if any(s.name == "trials" for s in stages):
        print("trials: counts trial 0 as already made by the test stage; run test first (its 676 matched-pair "
              "calls are then free)")
    print("no call was made and no key was needed")
    return 0


def _dev_metrics(summary: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {f"{r['category']}.{r['metric']}": {"value": r["value"], "lo": r["lo"], "hi": r["hi"], "mdd": r["mdd"]}
            for r in summary["rows"]}


def _write_stage(out: Path, system: PromptSystem, stage: Stage, run: Any, summary: dict[str, Any]) -> None:
    write_transcripts(run.rows, out / "trials.jsonl")
    write_summary(summary, out)
    info = {"prompt_hash": system.prompt_hash, "model": system.model, "system_version": system.version,
            "stage": stage.name, "calls_made": system.client.misses, "cache_hits": system.client.hits,
            "spend_usd": round(system.budget.spend_usd, 4), "stopped": run.stopped}
    (out / "run.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")


def _paid(args: Any, system_factory: Any, stage: Stage, dataset: Any, limit: int | None) -> tuple[PromptSystem, bool]:
    """Estimate, check the cap, and require --yes. Returns the system, or None-ish via exit code on refusal."""
    est = estimate_stage(system_factory(_NoClient()), dataset, stage, limit)
    print(_show(stage.name, est, stage))
    check_cap(est, stage)
    if est.uncached and not args.yes:
        print("this spends money: re-run with --yes (the key is read from ANTHROPIC_API_KEY)", file=sys.stderr)
        return None, False  # type: ignore[return-value]
    return system_factory(make_client() if est.uncached else _NoClient()), True


def cmd_iterate(args: Any, dataset: Any, protocol_path: Path | None = None, out_root: Path | None = None,
                cache: Path | None = None) -> int:
    """Score one prompt version on dev with the development model, and record it in the protocol file."""
    stage = STAGES["dev"]
    factory = lambda client: _system(args, stage, client, cache)  # noqa: E731
    probe = factory(_NoClient())
    smoke = args.limit is not None
    try:
        kind = protocol.check_can_score_dev(probe.prompt_hash, protocol_path)
        system, go = _paid(args, factory, stage, dataset, args.limit)
    except (protocol.ProtocolError, StageOverCap) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not go:
        return 2
    out = (out_root or RESULTS_DIR) / "dev" / f"{args.prompt}_{system.model}{'_smoke' if smoke else ''}"
    run = run_suites(dataset, system, "dev", limit=args.limit, log_dir=out / "inspect", protocol_path=protocol_path)
    summary = summarize(dataset, run, reference=False)
    _write_stage(out, system, stage, run, summary)
    print(render_markdown(summary))
    if run.stopped:
        print(f"stopped early: {run.stopped}; nothing recorded in the protocol", file=sys.stderr)
        return 2
    if smoke:
        print("smoke run (--limit): not recorded in the protocol and not counted as a version")
        return 0
    entry = protocol.record_dev_score(system.prompt_hash, args.prompt, system.model, _dev_metrics(summary),
                                      spend_usd=system.budget.spend_usd, note=args.note or "", path=protocol_path)
    count = len(protocol.versions(protocol_path))
    print(f"recorded as a {entry['kind']} ({count} of {protocol.MAX_VERSIONS} prompt versions used); "
          f"spend ${system.budget.spend_usd:.3f}")
    return 0


def cmd_freeze(args: Any, protocol_path: Path | None = None) -> int:
    try:
        entry = protocol.freeze(_hash(args.prompt), path=protocol_path)
    except protocol.ProtocolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"frozen: prompt {args.prompt} (hash {entry['prompt_hash']}); test and adversarial may now be scored with it")
    return 0


def _hash(version: str) -> str:
    from .prompt_system import prompt_hash

    return prompt_hash(load_prompt(version))


def cmd_run(args: Any, dataset: Any, protocol_path: Path | None = None, out_root: Path | None = None,
            ledger_path: Path | None = None, cache: Path | None = None) -> int:
    """A stage on any split with the frontier system. ``test`` and ``adversarial`` need a freeze and ``--final``."""
    try:
        stage = stage_for(args.split, args.suites, args.trials)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    factory = lambda client: _system(args, stage, client, cache)  # noqa: E731
    try:
        if stage.split in ("test", "adversarial"):  # refuse before any estimate or call
            protocol.require_frozen(factory(_NoClient()).prompt_hash, stage.split, protocol_path)
            if not args.final:
                raise FinalRunRequired(f"{stage.split} is only scored in a final run: pass --final")
        system, go = _paid(args, factory, stage, dataset, args.limit)
    except (protocol.ProtocolError, FinalRunRequired, StageOverCap, MissingApiKeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not go:
        return 2
    out = (out_root or RESULTS_DIR) / system.model / stage.name
    run = run_suites(dataset, system, stage.split, suites=args.suites, limit=args.limit, trials=stage.trials,
                     final=args.final, log_dir=out / "inspect", ledger_path=ledger_path, protocol_path=protocol_path)
    summary = summarize(dataset, run, reference=False)
    _write_stage(out, system, stage, run, summary)
    print(render_markdown(summary))
    if run.stopped:
        print(f"stopped early: {run.stopped}", file=sys.stderr)
        return 2
    print(f"wrote {out}/ ({len(run.rows)} transcripts); spend ${system.budget.spend_usd:.3f}")
    return 0
