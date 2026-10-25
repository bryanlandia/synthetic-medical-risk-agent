"""A one-line-per-note progress report for long runs, written to stderr so stdout stays clean.

A run that makes hundreds of sequential API calls takes minutes; silence looks like a hang. Each line
shows how far along the run is, how many notes are being excluded (and why), and the money spent so far.
"""

from __future__ import annotations

import sys
import time
from typing import TextIO


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


class Progress:
    def __init__(self, label: str, client=None, stream: TextIO | None = None, tally=None, every: int = 1):
        self.label, self.client, self.tally, self.every = label, client, tally, max(1, every)
        self.stream = stream if stream is not None else sys.stderr
        self.started = time.monotonic()
        self.lines = 0

    def __call__(self, *, setting: str, accepted: int, excluded: int, done: int | None = None,
                 total: int | None = None, target: int | None = None, tally=None) -> None:
        self.lines += 1
        if self.lines % self.every:
            return
        elapsed = time.monotonic() - self.started
        parts = []
        if done is not None and total:
            parts.append(f"[{done}/{total}]")
        parts.append(f"{setting}: {accepted}" + (f"/{target}" if target else "") + " accepted"
                     + (f", {excluded} excluded" if excluded else ""))
        c = self.client
        if c is not None and getattr(c, "misses", None) is not None:
            spend = getattr(getattr(c, "budget", None), "spend_usd", None)
            parts.append(f"calls {c.misses} (cached {c.hits})" + (f", ${spend:.3f}" if spend is not None else ""))
        parts.append(_clock(elapsed))
        if done and total and done < total and elapsed > 5:
            parts.append(f"eta {_clock(elapsed / done * (total - done))}")
        t = tally or self.tally
        if t is not None and excluded:
            parts.append(f"failing on: {t.top_failures()}")
        print(f"{self.label} " + " | ".join(parts), file=self.stream, flush=True)
