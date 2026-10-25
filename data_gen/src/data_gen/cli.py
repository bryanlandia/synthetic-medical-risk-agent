"""Command line: ``data-gen generate``, ``estimate``, ``pilot``, ``gate`` and ``validate``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import SYNTHETIC_NOTICE
from .builder import build_dataset
from .config import GenConfig
from .dataset_io import dump_record, read_dataset, write_dataset
from .validate import dataset_errors, distribution_errors, manifest_errors

DEFAULT_DIR = Path("data")
DEFAULT_LLM_DIR = Path("data_llm")
DEFAULT_CACHE = Path("cache/llm_cache.jsonl")
DEFAULT_REALISM = Path("realism")
DEFAULT_REVIEW_CACHE = Path("cache/review_cache.jsonl")


def _configure_logging(verbose: int) -> None:
    level = logging.WARNING if verbose == 0 else logging.INFO if verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, stream=sys.stderr, force=True, datefmt="%H:%M:%S",
                        format="%(asctime)s %(levelname)s %(message)s")
    if verbose:
        os.environ.setdefault("ANTHROPIC_LOG", "info")  # also show the SDK's own retries


def _config_from_args(args: argparse.Namespace) -> GenConfig:
    base = json.loads(Path(args.config).read_text()) if args.config else {}
    for field in ("seed", "n_train", "n_test", "n_per_adversarial_type", "target_prevalence", "note_source"):
        value = getattr(args, field, None)
        if value is not None:
            base[field] = value
    return GenConfig(**base)


def _out_dir(args: argparse.Namespace, cfg: GenConfig) -> Path:
    return Path(args.out) if args.out else (DEFAULT_LLM_DIR if cfg.note_source == "llm" else DEFAULT_DIR)


def cmd_generate(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    if cfg.note_source == "llm":
        return _generate_llm(args, cfg)
    out = _out_dir(args, cfg)
    by_split = build_dataset(cfg)
    manifest = write_dataset(by_split, cfg, out)
    print(SYNTHETIC_NOTICE)
    for name, info in manifest["splits"].items():
        print(f"{name}: {info['n']} records, prevalence {info['prevalence']}")
    print(f"wrote {out}/ (seed {cfg.seed}, config {manifest['config_hash']})")
    return 0


def _print_estimate(cfg: GenConfig, est, label: str) -> None:
    print(f"{label}: {est.notes} notes {est.per_setting}")
    print(f"  calls: {est.first_attempt_calls} first-attempt + ~{est.expected_retry_calls} expected retries "
          f"({est.cached_calls} already cached)")
    print(f"  tokens: ~{est.input_tokens:,} in, ~{est.output_tokens:,} out")
    print(f"  estimated cost: ${est.cost_usd:.2f}  (caps: {cfg.llm.max_calls} calls, ${cfg.llm.max_spend_usd:.2f})")
    a = est.assumptions
    basis = "measured from the cache" if a["measured_writer_tokens_used"] else "assumed (no measurements yet)"
    print(f"  token counts: {basis}; retry rate {a['retry_rate']:.0%}; model {a['model_id']}")


def cmd_estimate(args: argparse.Namespace) -> int:
    from .llm.estimate import estimate, exceeds_caps
    from .llm.gateway import DiskCache
    from .llm.pilot import pilot_items
    from .llm.run import plan_all

    cfg = _config_from_args(args)
    if cfg.note_source != "llm":
        print("error: estimate is for the LLM note source (pass --note-source llm)", file=sys.stderr)
        return 2
    items = plan_all(cfg)
    if args.pilot:
        items = pilot_items(cfg, items)
    est = estimate(cfg, items, DiskCache(Path(args.cache)))
    if args.json:
        print(json.dumps(est.as_dict(), indent=2, sort_keys=True))
    else:
        print(SYNTHETIC_NOTICE)
        _print_estimate(cfg, est, "pilot" if args.pilot else "full run")
    for warning in exceeds_caps(cfg, est):
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


def _generate_llm(args: argparse.Namespace, cfg: GenConfig) -> int:
    from .llm.client import AnthropicClient, LLMCallError, MissingApiKeyError
    from .llm.estimate import estimate
    from .llm.gate import load_gate_result
    from .llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache
    from .llm.progress import Progress
    from .llm.run import plan_all, run_and_write
    from .llm.writer import TooManyExclusions

    out = _out_dir(args, cfg)
    cache = DiskCache(Path(args.cache))
    items = plan_all(cfg)
    est = estimate(cfg, items, cache)
    print(SYNTHETIC_NOTICE)
    _print_estimate(cfg, est, "full run")
    if est.first_attempt_calls and not args.yes:
        print("\nThis run would spend money. Re-run with --yes to proceed (the caps above still apply).",
              file=sys.stderr)
        return 4
    try:
        client = CachedClient(AnthropicClient(), cache, Budget.for_run(cfg.llm), cfg.llm.prompt_version)
        result = run_and_write(cfg, client, out, items, None if args.quiet else Progress("generate", client),
                               realism_review=load_gate_result(Path(args.realism_dir)))
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (BudgetExceeded, TooManyExclusions) as exc:
        print(f"stopped: {exc}\nnothing was written to {out}/; completed notes are cached.", file=sys.stderr)
        return 3
    except LLMCallError as exc:
        print(f"stopped: {exc}\nnothing was written to {out}/; completed notes are cached.", file=sys.stderr)
        return 3
    cache.compact()  # sorted by key, so the committed cache does not depend on which worker finished first
    s = result.stats
    print(f"wrote {out}/: {sum(len(v) for v in result.by_split.values())} records, "
          f"{s['paid_calls']} paid calls, {s['cache_hits']} cache hits, ~${s['estimated_spend_usd']} spent")
    return 0


def cmd_pilot(args: argparse.Namespace) -> int:
    from .config import LLM_SETTINGS
    from .llm.client import AnthropicClient, LLMCallError, MissingApiKeyError
    from .llm.estimate import estimate
    from .llm.gateway import Budget, BudgetExceeded, CachedClient, DiskCache
    from .llm.pilot import pilot_items, run_pilot, used_record_ids, write_pilot
    from .llm.progress import Progress
    from .llm.run import plan_all

    cfg = _config_from_args(args)
    if cfg.note_source != "llm":
        print("error: pilot is for the LLM note source (pass --note-source llm)", file=sys.stderr)
        return 2
    settings = tuple(args.setting) if args.setting else LLM_SETTINGS
    items = plan_all(cfg)
    cache = DiskCache(Path(args.cache))
    est = estimate(cfg, pilot_items(cfg, items, settings, args.round), cache)
    print(SYNTHETIC_NOTICE)
    _print_estimate(cfg, est, f"pilot round {args.round} ({', '.join(settings)})")
    if est.first_attempt_calls and not args.yes:
        print("\nThis pilot would spend money. Re-run with --yes to proceed.", file=sys.stderr)
        return 4
    directory = Path(args.out) / f"round{args.round}"
    try:
        client = CachedClient(AnthropicClient(), cache, Budget.for_run(cfg.llm, pilot=True), cfg.llm.prompt_version)
        used = used_record_ids(args.out, settings) if args.round > 0 else set()
        progress = None if args.quiet else Progress("pilot", client)
        result = run_pilot(cfg, client, items, settings, args.round, exclude=used, progress=progress)
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (BudgetExceeded, LLMCallError) as exc:
        print(f"stopped: {exc}\nnothing was written; completed notes are cached.", file=sys.stderr)
        return 3
    cache.compact()
    meta = write_pilot(cfg, result, directory, args.round, settings, round(client.budget.spend_usd, 4))
    spent = meta["estimated_spend_usd"]
    print(f"wrote {directory}/sheet.md and key.json: {len(result.notes)} notes, about ${spent} spent")
    for setting, rate in meta["exclusion_rates"].items():
        flag = "  <-- above the limit: revise this setting's prompt" if rate > cfg.llm.exclusion_threshold else ""
        print(f"  exclusion rate {setting:13s} {rate:.0%}{flag}")
    for setting, v in meta["variety"].items():
        flag = "" if v["passed"] else "  <-- too uniform: check the traits and exemplars"
        print(f"  variety {setting:13s} top opener '{v['top_opener']}' {v['top_opener_share']:.0%} "
              f"(max {v['max_top_opener_share']:.0%}); {v['distinct_trait_combos']} trait combinations{flag}")
    for setting, rate in result.aborted.items():
        print(f"  ABORTED {setting}: {rate:.0%} of its notes failed validation, so it was stopped early "
              f"(mostly: {result.tally.top_failures()}). Fix the cause, then re-run with --round and --setting.",
              file=sys.stderr)
    if result.short:
        print(f"  WARNING: could not reach {cfg.llm.pilot_per_setting} accepted notes for {result.short}", file=sys.stderr)
    print(f"Next: rate the notes in {directory}/sheet.md, save it as {directory}/ratings.md, then run: data-gen gate")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    from .llm.gate import evaluate, load_round, save_gate_result

    cfg = _config_from_args(args)
    base = Path(args.dir)
    dirs = [base / f"round{r}" for r in args.rounds] if args.rounds else sorted(base.glob("round*"))
    if not dirs:
        print(f"error: no round directories found in {base}/", file=sys.stderr)
        return 2
    rounds, problems = [], []
    for d in dirs:
        loaded, probs = load_round(d, tuple(cfg.llm.gate_rater_kinds), cfg.llm.reviewer_min_control_gap)
        rounds.append(loaded)
        problems += probs
    report = evaluate(cfg, rounds, problems)
    save_gate_result(base, report)
    print(SYNTHETIC_NOTICE)
    print(report.render())
    return 0 if report.passed else 1


def _review_in_browser(args: argparse.Namespace, cfg: GenConfig, directory: Path) -> int:
    from .llm.client import LLMCallError, MissingApiKeyError
    from .llm.gateway import Budget
    from .review.browser import AnthropicToolClient, AppServer, run_browser_review

    budget = Budget.for_review(cfg.llm)
    try:
        tool_client = AnthropicToolClient(effort=cfg.llm.reviewer_effort)
        with AppServer(Path(args.app_dir), directory, cfg) as app:
            print(f"rating app running at {app.url} (this session only)")
            result = run_browser_review(cfg, tool_client, budget, directory, app.url, max_notes=args.max_notes,
                                        headless=not args.headed, record_video=not args.no_video,
                                        pause=args.pause)
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, LLMCallError) as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 3
    print(f"browser review done: {result.notes_attempted} notes visited in {result.steps} model turns, "
          f"~${budget.spend_usd:.3f} spent; refused {result.refused} actions, "
          f"blocked {len(result.blocked_requests)} outside requests")
    print(f"  session log: {result.session_log}" + (f"\n  video: {result.video}" if result.video else ""))
    if result.stopped:
        print(f"stopped early: {result.stopped}", file=sys.stderr)
        return 3
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from .llm.client import AnthropicClient, LLMCallError, MissingApiKeyError
    from .llm.gateway import Budget, CachedClient, DiskCache
    from .llm.progress import Progress
    from .review.estimate import estimate_browser, estimate_review
    from .review.reviewer import (ReviewerConfigError, check_independent, controls_gap, load_blind_sheet,
                                  review_round)

    cfg = _config_from_args(args)
    directory = Path(args.dir) / f"round{args.round}"
    if not (directory / "sheet.json").exists():
        print(f"error: {directory}/sheet.json not found; run the pilot first", file=sys.stderr)
        return 2
    try:
        check_independent(cfg)
    except ReviewerConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    cache = DiskCache(Path(args.cache))
    sheet = load_blind_sheet(directory)
    browser = args.mode == "browser"
    if browser:
        est = estimate_browser(cfg, min(len(sheet["notes"]), args.max_notes or len(sheet["notes"])))
    else:
        est = estimate_review(cfg, sheet, cache)
    print(SYNTHETIC_NOTICE)
    print(f"review of {directory}: {est.notes} notes by {cfg.llm.reviewer_model_id} (an LLM review, not a clinician)")
    if browser:
        print("  mode: browser (the reviewer operates the rating app and the session is recorded)")
        print(f"  model turns: ~{est.calls} (capped at {cfg.llm.reviewer_max_steps}; {cfg.llm.reviewer_max_calls} calls)")
    else:
        print(f"  calls: {est.calls} to make + ~{est.expected_retry_calls} expected retries ({est.cached} already cached)")
    print(f"  tokens: ~{est.input_tokens:,} in, ~{est.output_tokens:,} out ({'measured' if est.measured else 'assumed'})")
    print(f"  estimated cost: ${est.cost_usd:.2f}  (caps: {cfg.llm.reviewer_max_calls} calls, ${cfg.llm.reviewer_max_spend_usd:.2f})")
    if args.estimate:
        return 0
    if est.calls and not args.yes:
        print("\nThis review would spend money. Re-run with --yes to proceed (the caps above still apply).", file=sys.stderr)
        return 4
    if browser:
        return _review_in_browser(args, cfg, directory)
    try:
        client = CachedClient(AnthropicClient(effort=cfg.llm.reviewer_effort), cache, Budget.for_review(cfg.llm),
                              cfg.llm.reviewer_prompt_version, kind="reviewer")
        result = review_round(cfg, client, directory)
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except LLMCallError as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 3
    cache.compact()
    print(f"wrote {result.path}: {len(result.ratings)} rated, {len(result.unrated)} unrated, "
          f"~${client.budget.spend_usd:.3f} spent")
    key = json.loads((directory / "key.json").read_text()) if (directory / "key.json").exists() else None
    gap = controls_gap(result.ratings, key) if key else None
    if gap:
        flag = "" if gap["gap"] >= cfg.llm.reviewer_min_control_gap else "  <-- NON-DISCRIMINATING"
        print(f"  plausible: LLM notes {gap['notes_rate']:.0%}, controls {gap['controls_rate']:.0%}{flag}")
    if result.stopped:
        print(f"stopped early: {result.stopped}", file=sys.stderr)
        return 3
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data)
    by_split, manifest = read_dataset(data_dir)
    cfg = GenConfig(**manifest["config"])
    errors = (
        manifest_errors(by_split, manifest)
        + dataset_errors(by_split, min_per_type=min(50, cfg.n_per_adversarial_type))
        + distribution_errors(by_split)
    )
    if args.regenerate:
        if cfg.note_source != "template":
            print("note: --regenerate applies to template datasets; LLM notes are reproduced from the cache.")
        else:
            again = build_dataset(cfg)
            for name, recs in again.items():
                if [dump_record(r) for r in recs] != [dump_record(r) for r in by_split[name]]:
                    errors.append(f"regenerating from the manifest config does not reproduce {name}")
    print(SYNTHETIC_NOTICE)
    if errors:
        print(f"INVALID: {len(errors)} problem(s)")
        for e in errors[:25]:
            print(" -", e)
        return 1
    n = sum(len(v) for v in by_split.values())
    reproducible = " and reproducible from seed" if args.regenerate and cfg.note_source == "template" else ""
    print(f"OK: {n} records valid{reproducible}")
    return 0


def _add_config_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="log every API call with tokens, stop reason and duration (-vv for cache hits too)")
    p.add_argument("--quiet", action="store_true", help="no live progress line")
    p.add_argument("--config", help="JSON file of GenConfig fields")
    p.add_argument("--seed", type=int)
    p.add_argument("--n-train", dest="n_train", type=int)
    p.add_argument("--n-test", dest="n_test", type=int)
    p.add_argument("--n-per-adversarial-type", dest="n_per_adversarial_type", type=int)
    p.add_argument("--target-prevalence", dest="target_prevalence", type=float)
    p.add_argument("--note-source", dest="note_source", choices=["template", "llm"],
                   help="template (offline, default) or llm (calls the Anthropic API; needs ANTHROPIC_API_KEY)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="data-gen", description=SYNTHETIC_NOTICE)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate the synthetic dataset (template: offline; llm: spends money)")
    gen.add_argument("--out", help="output directory (default data/, or data_llm/ for the llm source)")
    gen.add_argument("--cache", default=str(DEFAULT_CACHE), help="LLM response cache (llm source)")
    gen.add_argument("--realism-dir", default=str(DEFAULT_REALISM), help="where gate.json is read from (llm source)")
    gen.add_argument("--yes", action="store_true", help="confirm that an llm run may spend money")
    _add_config_args(gen)
    gen.set_defaults(func=cmd_generate)

    est = sub.add_parser("estimate", help="dry-run the cost of an llm run; makes no API call, needs no key")
    est.add_argument("--cache", default=str(DEFAULT_CACHE))
    est.add_argument("--pilot", action="store_true", help="estimate the pilot sample only")
    est.add_argument("--json", action="store_true")
    _add_config_args(est)
    est.set_defaults(func=cmd_estimate)

    pil = sub.add_parser("pilot", help="write the small rating sample for the human realism gate (spends a little)")
    pil.add_argument("--out", default=str(DEFAULT_REALISM))
    pil.add_argument("--cache", default=str(DEFAULT_CACHE))
    pil.add_argument("--round", type=int, default=0, help="0 for the first pilot; higher rounds draw fresh notes")
    pil.add_argument("--setting", action="append",
                     choices=["shorthand", "ehr_template", "ai_scribe", "copy_forward"],
                     help="only this setting (repeat for several); used to re-rate a revised setting")
    pil.add_argument("--yes", action="store_true", help="confirm that the pilot may spend money")
    _add_config_args(pil)
    pil.set_defaults(func=cmd_pilot)

    gate = sub.add_parser("gate", help="evaluate the owner's ratings; exit 0 only if the full run may proceed")
    gate.add_argument("--dir", default=str(DEFAULT_REALISM))
    gate.add_argument("--rounds", type=int, nargs="*", help="rounds to include (default: all found)")
    _add_config_args(gate)
    gate.set_defaults(func=cmd_gate)

    rev = sub.add_parser("review", help="have the adversarial LLM reviewer rate a pilot round (spends a little)")
    rev.add_argument("--dir", default=str(DEFAULT_REALISM))
    rev.add_argument("--round", type=int, default=0)
    rev.add_argument("--cache", default=str(DEFAULT_REVIEW_CACHE))
    rev.add_argument("--estimate", action="store_true", help="dry run: print the cost; no API call, no key needed")
    rev.add_argument("--yes", action="store_true", help="confirm that the review may spend money")
    rev.add_argument("--mode", choices=["direct", "browser"], default="direct",
                     help="direct: rate from the note text; browser: operate the rating app on video (needs the review extra)")
    rev.add_argument("--app-dir", default="../rating_ui", help="the built rating app (browser mode)")
    rev.add_argument("--max-notes", type=int, help="browser mode: rate only the first N notes (a short demo)")
    rev.add_argument("--pause", type=float, help="browser mode: seconds to dwell on each finished note and comment "
                     "(default llm.reviewer_pause_seconds, 3)")
    rev.add_argument("--headed", action="store_true", help="browser mode: show the browser window")
    rev.add_argument("--no-video", action="store_true", help="browser mode: do not record a video")
    _add_config_args(rev)
    rev.set_defaults(func=cmd_review)

    val = sub.add_parser("validate", help="check a generated dataset against the specs")
    val.add_argument("--data", default=str(DEFAULT_DIR))
    val.add_argument("--regenerate", action="store_true",
                     help="also regenerate from the manifest config and require byte-identical output")
    val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    _configure_logging(getattr(args, "verbose", 0))
    try:
        return args.func(args)
    except ValueError as exc:  # includes pydantic validation errors and unsupported styles
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
