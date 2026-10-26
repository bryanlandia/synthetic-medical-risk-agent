"""Final runs on ``test`` and ``adversarial`` are explicit and counted, so a headline number can be shown to be
one look at the test set. The ledger is a committed JSON file."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from . import HARNESS_VERSION

PROTECTED = ("test", "adversarial")
LEDGER_PATH = Path(__file__).resolve().parents[2] / "results" / "ledger.json"


class FinalRunRequired(RuntimeError):
    """A protected split was requested without the final-run flag."""


def final_runs(system_version: str, split: str, path: Path = LEDGER_PATH) -> int:
    if not path.exists():
        return 0
    return sum(1 for e in json.loads(path.read_text())["entries"]
               if e["system_version"] == system_version and e["split"] == split)


def record_final_run(system_version: str, split: str, *, final: bool, path: Path = LEDGER_PATH) -> int:
    """Check and, for a protected split, record the run. Returns how many final runs this system version has had
    on the split (including this one). Raises FinalRunRequired without the flag; warns on the second."""
    if split not in PROTECTED:
        return 0
    if not final:
        raise FinalRunRequired(
            f"{split} is only scored in a final run: pass --final (this run will be recorded in the ledger). "
            "Iterate on dev.")
    data = json.loads(path.read_text()) if path.exists() else {"entries": []}
    count = sum(1 for e in data["entries"] if e["system_version"] == system_version and e["split"] == split) + 1
    data["entries"].append({"system_version": system_version, "split": split, "run": count,
                            "harness_version": HARNESS_VERSION})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    if count > 1:
        warnings.warn(f"{system_version} has now been scored on {split} {count} times; a headline number should "
                      "come from one final run per system version", stacklevel=2)
    return count
