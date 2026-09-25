"""DR — Drift Intelligence. Remembers what you MEANT, not what you said.

Keeps a timeline of statements. "Drift" = how far today's phrasing moved
from earlier phrasing on the same topic. Honest scope: without a local
embedding model this is lexical drift (token-set distance), which still
catches real rewording. If nomic-embed-text is ever wired in, swap the
_distance function — the timeline format stays the same.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def lexical_distance(a: str, b: str) -> float:
    """Jaccard distance between token sets. 0 = identical, 1 = disjoint."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 0.0
    if not ta or not tb:
        return 1.0
    return 1.0 - len(ta & tb) / len(ta | tb)


class DriftTimeline:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS statements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        text TEXT NOT NULL,
        ts INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_drift_topic ON statements(topic);
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "drift_timeline.db"
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)

    def note(self, topic: str, text: str) -> dict:
        """Record a statement; report drift from your last take on the topic."""
        prev = self._conn.execute(
            "SELECT text, ts FROM statements WHERE topic = ? ORDER BY ts DESC LIMIT 1",
            (topic,),
        ).fetchone()
        now = int(time.time())
        self._conn.execute(
            "INSERT INTO statements (topic, text, ts) VALUES (?,?,?)", (topic, text, now))
        self._conn.commit()
        if prev:
            d = lexical_distance(prev[0], text)
            return {"topic": topic, "drift": round(d, 3),
                    "previous": prev[0], "days_since": round((now - prev[1]) / 86400, 1)}
        return {"topic": topic, "drift": 0.0, "previous": None, "days_since": 0.0}

    def timeline(self, topic: str) -> list[dict]:
        return [
            {"text": t, "ts": ts}
            for t, ts in self._conn.execute(
                "SELECT text, ts FROM statements WHERE topic = ? ORDER BY ts", (topic,))
        ]

    def close(self) -> None:
        self._conn.close()
