"""FR — Friction Intelligence. Gets smarter only when corrected.

No fine-tuning, no model: a SQLite table of original -> corrected pairs
plus your note on state. Retrieval by token overlap (stdlib). Over enough
corrections it stops making the same mistake because the mistake is
literally on file.

This is the highest-value class per line of code. It is also the export
source if you ever do train BT: corrections.db is the dataset.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


class FrictionStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT NOT NULL,
        corrected TEXT NOT NULL,
        mood TEXT NOT NULL DEFAULT '',
        ts INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_corr_ts ON corrections(ts);
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "corrections.db"
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)

    def correct(self, original: str, corrected: str, mood: str = "") -> int:
        """File a correction: what it said -> what you meant."""
        cur = self._conn.execute(
            "INSERT INTO corrections (original, corrected, mood, ts) VALUES (?, ?, ?, ?)",
            (original, corrected, mood, int(time.time())),
        )
        self._conn.commit()
        return cur.lastrowid

    def find_similar(self, text: str, limit: int = 3, min_overlap: float = 0.3) -> list[dict]:
        """Retrieve past corrections whose original resembles this text."""
        toks = _tokens(text)
        if not toks:
            return []
        out = []
        for cid, original, corrected, mood, ts in self._conn.execute(
            "SELECT id, original, corrected, mood, ts FROM corrections ORDER BY ts DESC"
        ):
            otoks = _tokens(original)
            if not otoks:
                continue
            overlap = len(toks & otoks) / max(len(toks), len(otoks))
            if overlap >= min_overlap:
                out.append({
                    "id": cid, "original": original, "corrected": corrected,
                    "mood": mood, "ts": ts, "overlap": round(overlap, 3),
                })
                if len(out) >= limit:
                    break
        return out

    def apply(self, text: str) -> tuple[str, dict | None]:
        """If a near-identical original is on file, return the corrected form."""
        hits = self.find_similar(text, limit=1, min_overlap=0.85)
        if hits:
            return hits[0]["corrected"], hits[0]
        return text, None

    def export_pairs(self) -> list[tuple[str, str]]:
        """Dataset export for BT training. Your data only."""
        return [(o, c) for o, c in self._conn.execute(
            "SELECT original, corrected FROM corrections ORDER BY id")]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
