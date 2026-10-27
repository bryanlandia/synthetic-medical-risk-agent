"""``uv run training <command>`` (from ``training/``)."""

from __future__ import annotations

import argparse
import sys

from . import lexicon, reader_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="training", description="Note reader and risk classifier for a FICTIONAL disease. Synthetic data.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("lexicon", help="regenerate data/symptom_lexicon.json")
    r = sub.add_parser("reader", help="fit the note reader on train without dev, score it on dev, write model/reader.json")
    r.add_argument("--n-boot", type=int, default=1000)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "lexicon":
        lexicon.write()
        print(f"wrote {lexicon.LEXICON_PATH}")
        return 0
    if args.command == "reader":
        rep = reader_report.run(n_boot=args.n_boot)
        d = rep["dev"]["accuracy"]
        print(f"reader: dev accuracy {d['value']:.4f} [{d['lo']:.4f}, {d['hi']:.4f}] (floor {rep['dev']['floor']}); "
              f"conflict rule {rep['reader']['conflict_rule']}")
        for row in rep["held_out"]["with_cues"]:
            print(f"  held out {row['held_out']:<13} {row['value']:.4f} (in-distribution {row['in_distribution']:.4f})")
        print(f"  injection pairs identical: {rep['injection']['agreement']:.4f}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
