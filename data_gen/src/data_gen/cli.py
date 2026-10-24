"""Command line: ``data-gen generate`` and ``data-gen validate``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import SYNTHETIC_NOTICE
from .builder import build_dataset
from .config import GenConfig
from .dataset_io import dump_record, read_dataset, write_dataset
from .validate import dataset_errors, distribution_errors, manifest_errors

DEFAULT_DIR = Path("data")


def _config_from_args(args: argparse.Namespace) -> GenConfig:
    base = json.loads(Path(args.config).read_text()) if args.config else {}
    for field in ("seed", "n_train", "n_test", "n_per_adversarial_type", "target_prevalence"):
        value = getattr(args, field)
        if value is not None:
            base[field] = value
    return GenConfig(**base)


def cmd_generate(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    by_split = build_dataset(cfg)
    manifest = write_dataset(by_split, cfg, Path(args.out))
    print(SYNTHETIC_NOTICE)
    for name, info in manifest["splits"].items():
        print(f"{name}: {info['n']} records, prevalence {info['prevalence']}")
    print(f"wrote {args.out}/ (seed {cfg.seed}, config {manifest['config_hash']})")
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
    print(f"OK: {n} records valid" + (" and reproducible from seed" if args.regenerate else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="data-gen", description=SYNTHETIC_NOTICE)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate the synthetic dataset (offline, deterministic)")
    gen.add_argument("--out", default=str(DEFAULT_DIR))
    gen.add_argument("--config", help="JSON file of GenConfig fields")
    gen.add_argument("--seed", type=int)
    gen.add_argument("--n-train", dest="n_train", type=int)
    gen.add_argument("--n-test", dest="n_test", type=int)
    gen.add_argument("--n-per-adversarial-type", dest="n_per_adversarial_type", type=int)
    gen.add_argument("--target-prevalence", dest="target_prevalence", type=float)
    gen.set_defaults(func=cmd_generate)

    val = sub.add_parser("validate", help="check a generated dataset against the specs")
    val.add_argument("--data", default=str(DEFAULT_DIR))
    val.add_argument("--regenerate", action="store_true",
                     help="also regenerate from the manifest config and require byte-identical output")
    val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:  # includes pydantic validation errors and reserved styles
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
