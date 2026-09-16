"""Archive store: durable, local-first persistence for ArchiveRecords.

State lives under ``~/.levi/archive/``:

- ``records.jsonl`` — one JSON record per line (append-friendly, diffable).
- ``index.json``   — token → [record ids] search index, rebuilt on ingest.

Writes are atomic (temp file + rename) and owner-only (dir 0o700, files
0o600). ``add()`` refuses duplicate ids — records are never silently
overwritten; a conflicting find gets its own id with its own provenance.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .record import ArchiveRecord

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def default_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".levi" / "archive"


def _atomic_write_jsonl(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class ArchiveStore:
    """The trophy room's shelves."""

    def __init__(self, home: Optional[Path] = None):
        self.dir = default_dir(home)
        self.records_path = self.dir / "records.jsonl"
        self.index_path = self.dir / "index.json"
        self._records: Dict[str, ArchiveRecord] = {}
        self._index: Dict[str, List[str]] = {}
        self.load()

    # -- persistence ----------------------------------------------------

    def load(self) -> None:
        self._records = {}
        if self.records_path.is_file():
            for line in self.records_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = ArchiveRecord.from_dict(json.loads(line))
                self._records[rec.id] = rec  # last write wins on disk; add() never dupes
        self._index = {}
        if self.index_path.is_file():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save(self) -> None:
        _atomic_write_jsonl(
            self.records_path,
            (json.dumps(r.to_dict(), ensure_ascii=False) for r in self._records.values()),
        )
        _atomic_write_jsonl(self.index_path, [json.dumps(self._index, ensure_ascii=False)])

    # -- mutation -------------------------------------------------------

    def add(self, record: ArchiveRecord) -> None:
        """Store a record. Raises on duplicate id — never silently overwrite."""
        if not isinstance(record, ArchiveRecord):
            raise ValueError("can only store ArchiveRecord, got %r" % type(record))
        if record.id in self._records:
            raise ValueError("duplicate record id (refusing to overwrite): %s" % record.id)
        self._records[record.id] = record
        self._index_record(record)
        self._save()

    def add_many(self, records: Iterable[ArchiveRecord]) -> Dict[str, int]:
        """Add many; returns counts. Duplicate ids are skipped and counted."""
        added = skipped = 0
        for rec in records:
            if rec.id in self._records:
                skipped += 1
                continue
            self._records[rec.id] = rec
            self._index_record(rec)
            added += 1
        self._save()
        return {"added": added, "skipped": skipped}

    def rebuild_index(self) -> int:
        self._index = {}
        for rec in self._records.values():
            self._index_record(rec)
        self._save()
        return len(self._records)

    # -- reads ----------------------------------------------------------

    def get(self, record_id: str) -> Optional[ArchiveRecord]:
        return self._records.get(record_id)

    def all(self) -> List[ArchiveRecord]:
        return list(self._records.values())

    def count(self) -> int:
        return len(self._records)

    def ids_for_token(self, token: str) -> List[str]:
        return self._index.get(token.lower(), [])

    # -- indexing -------------------------------------------------------

    def _index_record(self, rec: ArchiveRecord) -> None:
        text = " ".join([rec.title, rec.era, rec.summary, rec.mechanism,
                         rec.decline, rec.revival_recipe, rec.levi_application])
        for token in set(tokenize(text)):
            self._index.setdefault(token, [])
            if rec.id not in self._index[token]:
                self._index[token].append(rec.id)
