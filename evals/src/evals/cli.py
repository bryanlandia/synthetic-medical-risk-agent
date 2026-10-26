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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "schema":
        from .report import schema_text, write_schema

        if args.write:
            print(f"wrote {write_schema()}")
        else:
            print(schema_text(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
