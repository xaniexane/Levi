"""SH — Shadow Intelligence. Learns from what you abandon.

Honest scope: a laptop daemon cannot see "tabs closed, messages unsent"
without deep OS hooks — so SH keeps an abandonment log YOU (or your tools)
feed it: drafts deleted, tasks quit, threads dropped. From that it learns
your quit-patterns and offers the smallest possible next step before the
usual quit-time.

The anti-you that keeps you honest, minus the surveillance fantasy.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class ShadowLog:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS abandonments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        task_type TEXT NOT NULL DEFAULT '',
        context TEXT NOT NULL DEFAULT '',
        ts INTEGER NOT NULL
    );
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "abandonment.db"
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)

    def log_abandoned(self, task: str, task_type: str = "", context: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO abandonments (task, task_type, context, ts) VALUES (?,?,?,?)",
            (task, task_type, context, int(time.time())),
        )
        self._conn.commit()
        return cur.lastrowid

    def quit_hours(self, task_type: str = "") -> list[int]:
        """Hours of day (local) when you usually quit this type of task."""
        q = "SELECT ts FROM abandonments"
        args: tuple = ()
        if task_type:
            q += " WHERE task_type = ?"
            args = (task_type,)
        hours = [time.localtime(ts).tm_hour for (ts,) in self._conn.execute(q, args)]
        # most common three
        freq: dict[int, int] = {}
        for h in hours:
            freq[h] = freq.get(h, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:3]  # type: ignore[arg-type]

    def nudge(self, task: str, task_type: str = "") -> str:
        """Smallest possible next step, timed against your quit pattern."""
        hours = self.quit_hours(task_type)
        when = f" (you usually quit around {hours[0]}:00 — start 15 min before)" if hours else ""
        return f"Smallest next step for '{task}': open it and do 5 minutes{when}."

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM abandonments").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
