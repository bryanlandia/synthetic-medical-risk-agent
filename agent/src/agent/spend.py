"""The day's spend in a SQLite file, so a restart does not forget what was spent."""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


class SpendCounter:
    def __init__(self, path: Path, daily_cap_usd: float, clock: Callable[[], float] = time.time):
        self.path, self.cap, self.clock = Path(path), daily_cap_usd, clock
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute("create table if not exists spend (day text primary key, usd real not null, requests integer not null)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def _day(self) -> str:
        return datetime.fromtimestamp(self.clock(), tz=timezone.utc).strftime("%Y-%m-%d")

    def total_today(self) -> float:
        with self._lock, self._connect() as db:
            row = db.execute("select usd from spend where day = ?", (self._day(),)).fetchone()
        return float(row[0]) if row else 0.0

    def remaining(self) -> float:
        return max(0.0, self.cap - self.total_today())

    def exhausted(self) -> bool:
        return self.total_today() >= self.cap

    def add(self, usd: float) -> float:
        """Add one request's cost to today's total and return the new total."""
        with self._lock, self._connect() as db:
            db.execute("insert into spend(day, usd, requests) values(?, ?, 1) "
                       "on conflict(day) do update set usd = usd + excluded.usd, requests = requests + 1", (self._day(), usd))
            row = db.execute("select usd from spend where day = ?", (self._day(),)).fetchone()
        return float(row[0])
