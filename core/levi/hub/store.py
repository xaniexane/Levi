"""hub.store: sqlite state for the hub. stdlib only.

Tables:
  users  — local accounts (single-user in practice; no billing, no tiers)
  tokens — opaque bearer tokens
  hitl   — approval queue (kind, detail JSON, status, timestamps)
  runs   — orchestrator/agent run receipts
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    label TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hitl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created TEXT NOT NULL,
    decided_at TEXT,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    receipt TEXT NOT NULL,
    created TEXT NOT NULL
);
"""


def hub_dir(path: Optional[Path] = None) -> Path:
    """Hub state dir. ``LEVI_HUB_DIR`` overrides (tests use this)."""
    if path is not None:
        return Path(path)
    env = os.environ.get("LEVI_HUB_DIR")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".levi" / "hub"


def db_path(path: Optional[Path] = None) -> Path:
    return hub_dir(path) / "hub.db"


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    """Open the hub db, creating dir + schema. Never raises on schema."""
    d = hub_dir(path)
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    conn = sqlite3.connect(str(d / "hub.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
