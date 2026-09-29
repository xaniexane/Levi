"""Edit journal: append-only, per-project, local-first.

Every consequential edit lands here as a small JSON line. The journal is
the seed of Phase-4's builder-aware assistance ("you fixed this pattern
twice last month") and of continuity across app kills — but it lives in
the USER'S tree (<project>/.hicomb/journal.jsonl), daemon-synced, never
held hostage by the UI process. Uninstall the editor; the journal stays.

Bounded: rotation keeps the newest MAX_ENTRIES. No telemetry, no network —
this journal never leaves the device except by the builder's explicit act.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

JOURNAL_DIRNAME = ".hicomb"
JOURNAL_FILENAME = "journal.jsonl"
MAX_ENTRIES = 5000


@dataclass
class JournalEntry:
    ts: float
    op: str  # open | edit | save | search | replace | theme | command | note
    path: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {"ts": self.ts, "op": self.op, "path": self.path, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        return cls(
            ts=float(data.get("ts", 0.0)),
            op=str(data.get("op", "")),
            path=str(data.get("path", "")),
            detail=str(data.get("detail", "")),
        )


class EditJournal:
    """Append-only journal for one project root."""

    def __init__(self, project_root: str) -> None:
        self.root = os.path.abspath(project_root)
        self.dir = os.path.join(self.root, JOURNAL_DIRNAME)
        self.path = os.path.join(self.dir, JOURNAL_FILENAME)
        os.makedirs(self.dir, exist_ok=True)

    def append(self, op: str, path: str, detail: str = "") -> JournalEntry:
        entry = JournalEntry(ts=time.time(), op=op, path=path, detail=detail)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
        self._rotate_if_needed()
        return entry

    def entries(self, limit: int | None = None) -> list[JournalEntry]:
        out: list[JournalEntry] = []
        if not os.path.exists(self.path):
            return out
        with open(self.path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(JournalEntry.from_dict(json.loads(raw)))
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue  # a corrupt line never kills the journal
        if limit is not None:
            limit = max(0, int(limit))
            out = out[-limit:] if limit else []
        return out

    def recall(self, keyword: str, limit: int = 10) -> list[JournalEntry]:
        """'You fixed this pattern before' — keyword recall over the journal."""
        kw = keyword.lower()
        if not kw.strip():
            return []  # an empty keyword recalls nothing, not everything
        limit = max(0, int(limit))
        hits = [
            e
            for e in self.entries()
            if kw in e.detail.lower() or kw in e.path.lower() or kw in e.op.lower()
        ]
        return hits[-limit:] if limit else []

    def count(self) -> int:
        return len(self.entries())

    # ------------------------------------------------------------- internals
    def _rotate_if_needed(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            return
        if len(lines) <= MAX_ENTRIES:
            return
        kept = lines[-MAX_ENTRIES:]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
        os.replace(tmp, self.path)
