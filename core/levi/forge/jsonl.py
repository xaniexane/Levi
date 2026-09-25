"""Atomic JSONL helpers — the same discipline as ``levi.archive.store``.

Writes go to a temp file in the same directory, get owner-only perms
(0o600), then ``os.replace()`` into place. Appends write the new line(s)
to the temp copy of the whole file: simple, crash-safe, and diffable.
Parent dirs are created owner-only (0o700).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)


def read_jsonl(path: Path):
    """Return list of decoded JSON objects; missing file -> []."""
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records) -> None:
    """Atomically replace ``path`` with one JSON object per line."""
    ensure_parent(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def append_jsonl(path: Path, record) -> None:
    """Atomically append one record (read-modify-write, crash-safe)."""
    records = read_jsonl(path)
    records.append(record)
    write_jsonl(path, records)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, obj) -> None:
    ensure_parent(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
