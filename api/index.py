"""Vercel entry point for the agent service (spike for add-web-demo; the final layout is chosen in the design).

The function imports the repository's own code: ``agent/src`` and ``risk_model/src`` are on the path and the model files are
read from ``training/model``. The spend database goes to ``/tmp`` because the rest of the filesystem is read-only.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("agent/src", "risk_model/src"):
    sys.path.insert(0, str(ROOT / sub))
os.environ.setdefault("RISK_MODEL_DIR", str(ROOT / "training" / "model"))
os.environ.setdefault("AGENT_SPEND_DB", "/tmp/spend.db")

from agent.asgi import app  # noqa: E402,F401  (the platform looks for ``app``)
