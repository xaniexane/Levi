"""GR — Gleaner Intelligence. Learns from your digital dust.

Background metadata scan: file names, folder structures, note titles —
never file contents unless you explicitly allow a path. Stored in SQLite
FTS (stdlib). If a local embedding model is ever wired in, vectors upgrade
it; until then honest keyword search beats a fake vector story.

Default posture: metadata only, local only, never syncs.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


class Gleaner:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS dust (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent TEXT NOT NULL,
        kind TEXT NOT NULL,      -- file | dir
        size INTEGER NOT NULL DEFAULT 0,
        mtime INTEGER NOT NULL,
        scanned INTEGER NOT NULL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS dust_fts USING fts5(name, parent);
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "dust.db"
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)

    def scan(self, roots: list[str | Path], max_entries: int = 20000) -> int:
        """Walk directory trees, recording metadata only. Returns entry count."""
        now = int(time.time())
        count = 0
        batch, fts_batch = [], []
        for root in roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                # stay cheap: skip hidden and cache dirs
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
                for name in dirnames + filenames:
                    p = Path(dirpath) / name
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    kind = "dir" if p.is_dir() else "file"
                    batch.append((name, dirpath, kind, st.st_size, int(st.st_mtime), now))
                    fts_batch.append((name, dirpath))
                    count += 1
                    if count >= max_entries:
                        break
                if count >= max_entries:
                    break
        self._conn.executemany(
            "INSERT INTO dust (name, parent, kind, size, mtime, scanned) VALUES (?,?,?,?,?,?)", batch)
        self._conn.executemany("INSERT INTO dust_fts (name, parent) VALUES (?,?)", fts_batch)
        self._conn.commit()
        return count

    def search(self, query: str, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT name, parent FROM dust_fts WHERE dust_fts MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
        return [{"name": n, "parent": p} for n, p in rows]

    def stats(self) -> dict:
        n = self._conn.execute("SELECT COUNT(*) FROM dust").fetchone()[0]
        last = self._conn.execute("SELECT MAX(scanned) FROM dust").fetchone()[0]
        return {"entries": n, "last_scan": last}

    def close(self) -> None:
        self._conn.close()
