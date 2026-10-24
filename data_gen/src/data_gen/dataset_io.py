"""Reading and writing datasets. Output is deterministic: sorted keys, no timestamps."""

from __future__ import annotations

import json
from pathlib import Path

from .config import GenConfig
from .manifest import SPLITS, build_manifest
from .schema import Record


def dump_record(r: Record) -> str:
    data = r.model_dump(mode="json")
    if data.get("pair_group") is None:
        data.pop("pair_group", None)  # absent in schema 1, so older datasets stay byte-identical
    return json.dumps(data, sort_keys=True, ensure_ascii=True)


def dump_manifest(manifest: dict) -> str:
    return json.dumps(manifest, sort_keys=True, indent=2) + "\n"


def write_dataset(
    by_split: dict[str, list[Record]], cfg: GenConfig, out_dir: Path, llm_stats: dict | None = None
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in SPLITS:
        lines = [dump_record(r) for r in by_split[name]]
        (out_dir / f"{name}.jsonl").write_text("\n".join(lines) + "\n")
    manifest = build_manifest(cfg, by_split, llm_stats)
    (out_dir / "manifest.json").write_text(dump_manifest(manifest))
    return manifest


def read_dataset(data_dir: Path) -> tuple[dict[str, list[Record]], dict]:
    by_split = {}
    for name in SPLITS:
        path = data_dir / f"{name}.jsonl"
        by_split[name] = [
            Record.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()
        ]
    manifest = json.loads((data_dir / "manifest.json").read_text())
    return by_split, manifest
