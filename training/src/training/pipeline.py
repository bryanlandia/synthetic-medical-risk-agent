"""The whole training run: reader, classifier, dev scores, model files, manifest and the MLflow run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import risk_model
from evals.devsplit import dev_ids
from evals.targets import judge, load_targets
from risk_model.reader import NoteReader

from . import classifier_fit as cf
from . import data, reader_report, tracking

MODEL_DIR = reader_report.MODEL_DIR
MODEL_FILES = risk_model.MODEL_FILES  # the model: its hash is the hash of these two files
TARGET_KEYS = {"auc": "auc", "brier": "brier", "log_loss": "log_loss", "ece": "ece"}


def sha256(data_: bytes) -> str:
    return hashlib.sha256(data_).hexdigest()


def model_hash(directory: Path) -> str:
    return risk_model.model_hash(directory)


def against_targets(m: dict[str, dict[str, float]]) -> dict[str, Any]:
    targets = load_targets()
    out = {}
    if not targets:
        return out
    by = {(t["category"], t["metric"]): t for t in targets["targets"]}
    for name, row in m.items():
        t = by.get(("happy_path", TARGET_KEYS[name]))
        if t:
            out[name] = {"target": t["target"], "direction": t["direction"], **judge(t, row["value"], row["lo"], row["hi"])}
    return out


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def train(out_dir: Path = MODEL_DIR, tracking_dir: Path | None = tracking.DEFAULT_DIR, n_boot: int = 1000,
          dataset=None) -> dict[str, Any]:
    ds = dataset or data.load()
    grid = cf.load_grid()
    out_dir = Path(out_dir)
    reader_rep = reader_report.run(out_dir, n_boot=n_boot, seed=grid["seed"], dataset=ds)
    reader = NoteReader(json.loads((out_dir / "reader.json").read_text()))
    train_recs, dev_recs = data.training_records(ds), data.dev_records(ds)
    data.assert_trainable(ds, train_recs)
    means, sds = cf.lab_statistics(train_recs)
    x_tr, y_tr = cf.matrix(train_recs, reader, means, sds)
    x_dev, y_dev = cf.matrix(dev_recs, reader, means, sds)
    spec, candidates = cf.select(x_tr, y_tr, x_dev, y_dev, grid, means, sds)
    p = cf.dev_probabilities(spec, x_dev)
    dev = cf.dev_metrics(dev_recs, p, n_boot, grid["seed"])
    gbm = cf.gbm_diagnostic(x_tr, y_tr, x_dev, grid)
    summary = {
        "dev": dev, "against_targets": against_targets(dev),
        "probability_percentiles": {str(q): float(np.percentile(p, q)) for q in (5, 25, 50, 75, 95)},
        "spread_requirement": {"p5_at_most": 0.10, "p95_at_least": 0.60},
        "uncertain_share": float(np.mean((p >= 0.4) & (p <= 0.6))),
        "chosen": {"c": spec["fit"]["c"], "platt": spec["platt"], "oof_log_loss": spec["fit"]["oof_log_loss"]},
        "candidates": candidates,
        "gbm_diagnostic": {"served": False, **cf.dev_metrics(dev_recs, gbm, n_boot, grid["seed"])},
        "n_train": len(train_recs), "n_dev": len(dev_recs),
    }
    (out_dir / "classifier.json").write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n")
    (out_dir / "metrics.json").write_text(_dump(summary))
    files = {n: sha256((out_dir / n).read_bytes()) for n in (*MODEL_FILES, "reader_report.json", "metrics.json")}
    manifest = {
        "model_hash": model_hash(out_dir), "files": files, "seed": grid["seed"],
        "dataset_config_hash": ds.config_hash, "dataset": str(Path(ds.directory).name),
        "train_ids_sha256": sha256("\n".join(r.patient_id for r in train_recs).encode()),
        "dev_ids_sha256": sha256("\n".join(sorted(dev_ids(ds))).encode()),
        "grid_sha256": sha256(cf.GRID_PATH.read_bytes()), "n_train": len(train_recs),
        "synthetic": True, "notice": "All data is synthetic and the disease is fictional. Not medical advice.",
    }
    (out_dir / "manifest.json").write_text(_dump(manifest))
    if tracking_dir is not None:
        flat = {f"dev_{k}": v["value"] for k, v in dev.items()} | {
            "dev_reader_accuracy": reader_rep["dev"]["accuracy"]["value"], "uncertain_share": summary["uncertain_share"]}
        params = {"seed": grid["seed"], "c": spec["fit"]["c"], "folds": grid["folds"], "platt": spec["platt"] is not None,
                  "model_hash": manifest["model_hash"], "dataset_config_hash": ds.config_hash,
                  "train_ids_sha256": manifest["train_ids_sha256"], "reader_conflict_rule": reader_rep["reader"]["conflict_rule"]}
        run_id = tracking.log_run(Path(tracking_dir), params, flat, out_dir, tags={"model_hash": manifest["model_hash"]})
        (out_dir / "run.json").write_text(_dump({"mlflow_run_id": run_id, "tracking_dir": "training/mlruns (not committed)"}))
    from . import model_card

    model_card.write(out_dir)
    return {"manifest": manifest, "summary": summary, "reader": reader_rep}
