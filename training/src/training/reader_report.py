"""Fit the note reader, choose its conflict rule on dev, score it, and write ``reader.json`` plus ``reader_report.json``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from risk_model.reader import NoteReader

from . import data, reader_eval, reader_fit

MODEL_DIR = Path(__file__).resolve().parents[2] / "model"
SEED = 0


def run(out_dir: Path = MODEL_DIR, n_boot: int = 1000, seed: int = SEED, dataset=None) -> dict[str, Any]:
    ds = dataset or data.load()
    train, dev = data.training_records(ds), data.dev_records(ds)
    data.assert_trainable(ds, train)
    spec = reader_fit.choose_conflict_rule(reader_fit.fit(train, seed=seed, cues=True), dev)
    reader = NoteReader(spec)
    dev_acc = reader_eval.accuracy_with_interval(reader, dev, n_boot, seed)
    per_setting = reader_eval.per_setting(reader, dev, n_boot)
    report = {
        "reader": {k: spec["fit"][k] for k in ("c", "seed", "n_mentions", "min_df", "conflict_rule_dev_accuracy")}
                  | {"conflict_rule": spec["conflict_rule"], "cues": spec["cues"], "n_features": len(spec["features"]),
                     "n_train_records": len(train)},
        "dev": {"accuracy": dev_acc, "floor": reader_eval.FLOOR_DEV, "meets_floor": dev_acc["value"] >= reader_eval.FLOOR_DEV,
                "per_setting": per_setting},
        "held_out": {
            "with_cues": reader_eval.leave_one_setting_out(train, dev, per_setting, seed=seed, n_boot=n_boot, cues=True),
            "without_cues": reader_eval.leave_one_setting_out(train, dev, per_setting, seed=seed, n_boot=n_boot, cues=False),
            "floor": reader_eval.FLOOR_HELD_OUT},
        "injection": {k: v for k, v in reader_eval.injection_agreement(reader, dev).items() if k != "differing"}
                     | {"floor": reader_eval.MIN_PAIR_AGREEMENT, "where": "dev notes with each catalog addendum appended"},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reader.json").write_text(reader_fit.to_json(spec))
    (out_dir / "reader_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
