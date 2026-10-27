"""MLflow tracking for training runs, in a local file store (``training/mlruns/``, not committed).

MLflow marks its file store as in maintenance mode and refuses it unless ``MLFLOW_ALLOW_FILE_STORE`` is set. It is kept on
purpose: ``mlflow-skinny`` has no SQL backend, and the full package would add pandas and a server for a local run log."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from mlflow import MlflowClient  # noqa: E402

EXPERIMENT = "risk-classifier"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "mlruns"


def _client(directory: Path) -> MlflowClient:
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return MlflowClient(tracking_uri=directory.as_uri())


def log_run(directory: Path, params: dict[str, Any], metrics: dict[str, float], artifact_dir: Path,
            tags: dict[str, str] | None = None, run_name: str = "train") -> str:
    """One finished run holding the parameters, metrics and the model files. Returns the run id."""
    client = _client(directory)
    exp = client.get_experiment_by_name(EXPERIMENT)
    exp_id = exp.experiment_id if exp else client.create_experiment(EXPERIMENT)
    run = client.create_run(exp_id, tags={"mlflow.runName": run_name, "synthetic": "true", **(tags or {})})
    run_id = run.info.run_id
    for k, v in sorted(params.items()):
        client.log_param(run_id, k, str(v)[:480])
    for k, v in sorted(metrics.items()):
        client.log_metric(run_id, k, float(v))
    client.log_artifacts(run_id, str(artifact_dir))
    client.set_terminated(run_id)
    return run_id


def read_run(directory: Path, run_id: str) -> dict[str, Any]:
    client = _client(directory)
    run = client.get_run(run_id)
    arts = sorted(a.path for a in client.list_artifacts(run_id))
    return {"params": dict(run.data.params), "metrics": dict(run.data.metrics), "artifacts": arts,
            "status": run.info.status, "tags": dict(run.data.tags)}
