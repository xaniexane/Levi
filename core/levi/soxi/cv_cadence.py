"""CV — Cadence Intelligence. Reads emotion from typing rhythm.

Honest scope: this module works on rhythm samples you hand it — lists of
inter-key intervals in milliseconds. Real keystroke capture needs OS-level
permission (evdev on Linux, accessibility service on Android) and is NOT
done silently here. No keylogger ships in this file, by design.

The 12-byte vector: mean, std, and 10 quantized bucket counts of intervals.
"""

from __future__ import annotations

import math
import sqlite3
import struct
import time
from pathlib import Path


def rhythm_vector(intervals_ms: list[float]) -> bytes:
    """Compress a typing sample into a 12-byte rhythm vector."""
    if not intervals_ms:
        return bytes(12)
    n = len(intervals_ms)
    mean = sum(intervals_ms) / n
    var = sum((x - mean) ** 2 for x in intervals_ms) / n
    std = math.sqrt(var)
    buckets = [0] * 10
    for x in intervals_ms:
        b = min(9, int(x // 100))  # 0-99ms, 100-199ms, ... 900ms+
        buckets[b] += 1
    # 4 bytes: mean/50ms, std/50ms; 8 bytes: 10 buckets as 4-bit nibbles (5B) + 3 pad
    packed = struct.pack(">HH", min(65535, int(mean / 50)), min(65535, int(std / 50)))
    nibbles = bytes((min(15, buckets[i]) << 4 | min(15, buckets[i + 1])) for i in range(0, 10, 2))
    return packed + nibbles + bytes(3)


def read_vector(vec: bytes) -> dict:
    mean, std = struct.unpack(">HH", vec[:4])
    buckets = []
    for b in vec[4:9]:
        buckets += [b >> 4, b & 0xF]
    buckets = buckets[:10]
    # heuristic read, labeled as such
    if mean * 50 < 120 and std * 50 < 80:
        mood = "flowing — fast, even"
    elif std * 50 > 250:
        mood = "agitated or interrupted — uneven"
    elif mean * 50 > 400:
        mood = "slow, deliberate or tired"
    else:
        mood = "neutral"
    return {"mean_ms": mean * 50, "std_ms": std * 50, "buckets": buckets,
            "heuristic_read": mood}


class CadenceLog:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS rhythm (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL DEFAULT '',
        vec BLOB NOT NULL,
        ts INTEGER NOT NULL
    );
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "rhythm.db"
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)

    def record(self, intervals_ms: list[float], label: str = "") -> dict:
        vec = rhythm_vector(intervals_ms)
        self._conn.execute(
            "INSERT INTO rhythm (label, vec, ts) VALUES (?,?,?)",
            (label, vec, int(time.time())),
        )
        self._conn.commit()
        return read_vector(vec)

    def close(self) -> None:
        self._conn.close()
