"""How fast and how big: time to produce one report on dev records, one at a time in one thread, and the model's size."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from evals.records import input_view
from threadpoolctl import threadpool_limits

from . import data
from .system import MODEL_DIR, ClassifierSystem

LIMIT_MS, LIMIT_BYTES = 100.0, 10_000_000


def measure(directory: Path = MODEL_DIR, dataset=None, n: int = 500) -> dict[str, Any]:
    ds = dataset or data.load()
    system = ClassifierSystem(directory)
    views = [input_view(r) for r in data.dev_records(ds)[:n]]
    system.run(views[0])  # the first call imports lazily-loaded pieces; the loading itself is not timed
    times = []
    with threadpool_limits(limits=1):
        for v in views:
            t0 = time.perf_counter()
            system.run(v)
            times.append((time.perf_counter() - t0) * 1000)
    size = sum(p.stat().st_size for p in (Path(directory) / "reader.json", Path(directory) / "classifier.json"))
    out = {"records": len(views), "threads": 1, "median_ms": float(np.median(times)),
           "p95_ms": float(np.percentile(times, 95)), "max_ms": float(max(times)), "model_bytes": int(size),
           "limits": {"p95_ms": LIMIT_MS, "bytes": LIMIT_BYTES}}
    out["meets_limits"] = out["p95_ms"] < LIMIT_MS and size < LIMIT_BYTES
    return out


def write(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
