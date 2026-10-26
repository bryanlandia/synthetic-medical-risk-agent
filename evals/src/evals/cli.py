"""The ``evals`` command. Subcommands are added as each capability lands."""

from __future__ import annotations

import argparse
import sys

from data_gen import SYNTHETIC_NOTICE

from . import HARNESS_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evals", description="Run and grade systems that score fictional patient records. " + SYNTHETIC_NOTICE)
    parser.add_argument("--version", action="version", version=f"evals {HARNESS_VERSION}")
    sub = parser.add_subparsers(dest="command")
    schema = sub.add_parser("schema", help="print or write the JSON Schema of the risk report contract")
    schema.add_argument("--write", action="store_true", help="write contract/risk_report.schema.json")

    run = sub.add_parser("run", help="run a reference system on a split and write transcripts and a summary")
    run.add_argument("--system", choices=["oracle", "floor", "lab_only", "frontier"], required=True)
    run.add_argument("--split", choices=["dev", "test", "adversarial"], default="dev")
    run.add_argument("--suites", nargs="*", help="default: every suite that applies to the split")
    run.add_argument("--limit", type=int, help="at most this many samples per suite")
    run.add_argument("--trials", type=int, default=1)
    run.add_argument("--final", action="store_true", help="required for test and adversarial; recorded in the ledger")
    run.add_argument("--dataset", default=None)
    run.add_argument("--out", default=None, help="output directory (default runs/<system>/<split>)")
    run.add_argument("--prompt", default="v1", help="frontier: the prompt file in prompts/frontier (without .md)")
    run.add_argument("--model", default="sonnet", help="frontier: haiku or sonnet (or a model id)")
    run.add_argument("--yes", action="store_true", help="frontier: confirm the spend")
    run.add_argument("--workers", type=int, default=8, help="frontier: samples in flight at once")
    run.add_argument("--force", action="store_true", help="frontier: repeat a final run (recorded and warned about)")

    est = sub.add_parser("estimate", help="frontier: the calls, tokens and cost of each stage; no call, no key")
    est.add_argument("--prompt", default="v1")
    est.add_argument("--model", default="sonnet")
    est.add_argument("--stage", choices=["all", "dev", "test", "adversarial", "trials"], default="all")
    est.add_argument("--dataset", default=None)

    it = sub.add_parser("iterate", help="frontier: score a prompt version on dev (at most 5 versions) and record it")
    it.add_argument("--prompt", required=True)
    it.add_argument("--model", default="haiku")
    it.add_argument("--limit", type=int, help="a smoke run on fewer samples; not recorded")
    it.add_argument("--note", help="what changed and what you decided; stored with the version")
    it.add_argument("--yes", action="store_true")
    it.add_argument("--workers", type=int, default=8)
    it.add_argument("--dataset", default=None)

    rep = sub.add_parser("report", help="frontier: write results/frontier/report.md; exit 1 if it is incomplete")
    rep.add_argument("--model", default="sonnet")

    fr = sub.add_parser("freeze", help="frontier: choose the prompt for the protected splits; ends dev iteration")
    fr.add_argument("--prompt", required=True)

    sub.add_parser("baselines", help="run the three reference systems on dev; write baseline summaries and targets v1")
    sub.add_parser("regression", help="the fast key-free regression subset (used by CI); exit 1 on any failure")

    fail = sub.add_parser("failures", help="print a seeded sample of failing transcripts for a grader")
    fail.add_argument("transcripts")
    fail.add_argument("--grader", required=True)
    fail.add_argument("-n", type=int, default=10)
    fail.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command in ("run", "baselines", "regression", "failures", "estimate", "iterate", "freeze", "report"):
        return _dispatch(args)
    if args.command == "schema":
        from .report import schema_text, write_schema

        if args.write:
            print(f"wrote {write_schema()}")
        else:
            print(schema_text(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


def _dispatch(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .records import DEFAULT_DATASET, load_dataset

    print(SYNTHETIC_NOTICE)
    if args.command == "report":
        from .frontier_cli import cmd_report

        return cmd_report(args)
    if args.command == "freeze":
        from .frontier_cli import cmd_freeze

        return cmd_freeze(args)
    if args.command == "failures":
        from .transcripts import failure_sample, format_failure, read_transcripts

        rows = read_transcripts(Path(args.transcripts))
        sample = failure_sample(rows, args.grader, args.n, args.seed)
        print(f"{len(sample)} failing transcripts for {args.grader}")
        for row in sample:
            print(format_failure(row, args.grader))
        return 0
    dataset = load_dataset(getattr(args, "dataset", None) or DEFAULT_DATASET)
    if args.command in ("estimate", "iterate") or (args.command == "run" and args.system == "frontier"):
        from . import frontier_cli

        if args.command == "estimate":
            return frontier_cli.cmd_estimate(args, dataset)
        if args.command == "iterate":
            return frontier_cli.cmd_iterate(args, dataset)
        return frontier_cli.cmd_run(args, dataset)
    if args.command == "regression":
        from .regression import run_regression

        failures = run_regression(dataset)
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        print("regression subset: " + ("FAILED" if failures else "passed"))
        return 1 if failures else 0
    if args.command == "baselines":
        from .regression import BASELINES_DIR, baseline_summaries
        from .summary import write_summary
        from .targets import build_targets, write_targets
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            summaries = baseline_summaries(dataset, Path(tmp))
        for name, summary in summaries.items():
            js, _ = write_summary(summary, BASELINES_DIR / name)
            print(f"wrote {js}")
        print(f"wrote {write_targets(build_targets(summaries['floor'], summaries['lab_only'], summaries['oracle']))}")
        return 0
    from .ledger import FinalRunRequired
    from .regression import reference_systems
    from .runner import run_suites
    from .summary import render_markdown, summarize, write_summary
    from .transcripts import write_transcripts

    system = reference_systems(dataset)[args.system]
    out = Path(args.out or f"runs/{args.system}/{args.split}")
    try:
        run = run_suites(dataset, system, args.split, suites=args.suites, limit=args.limit, trials=args.trials,
                         final=args.final, log_dir=out / "inspect")
    except FinalRunRequired as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_transcripts(run.rows, out / "trials.jsonl")
    summary = summarize(dataset, run)
    write_summary(summary, out)
    print(render_markdown(summary))
    print(f"wrote {out}/ ({len(run.rows)} transcripts)")
    return 0
