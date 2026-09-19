"""Visible-record system: every record's status strip stays in view.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #14)

The load-bearing mechanism: one record per card, a *persistent labeled
status strip* on each card, and the whole file arranged so every strip
is readable at a glance — the state of the system is ambiently legible,
no opening anything. Updating costs one record-swap: change one card,
the board is current. Each strip keeps its history, so a strip's past is
as inspectable as its present.

:meth:`Kardex.board` is the visible file — all strips, one view.
:meth:`Kardex.update_status` is the single-card swap. Pass a rule to
:meth:`Kardex.needs_attention` and the board flags the strips that
turned red.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is the ambient status board with
one-swap updates and strip history. Not revived: the physical trays —
the density that lost to the screen is conceded, not mourned.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


ORIGIN = "levi-revival/kardex"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class KardexError(Exception):
    """Base class for kardex failures."""


class UnknownRecord(KardexError):
    """No record with that id."""


class DuplicateRecord(KardexError):
    """A record with that id already exists."""


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class StripEvent:
    """One change to a record's status strip."""

    seq: int
    old: str
    new: str
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"seq": self.seq, "old": self.old, "new": self.new, "at": self.at}

    @classmethod
    def from_dict(cls, data: dict) -> "StripEvent":
        return cls(data["seq"], data["old"], data["new"], data.get("at", 0.0))


@dataclass
class Record:
    """One visible card: an id, a label, and its persistent status strip."""

    rec_id: str
    label: str
    status: str
    detail: str = ""
    history: list[StripEvent] = field(default_factory=list)

    def strip(self) -> dict:
        """The labeled edge-strip: what the board shows."""
        return {"rec_id": self.rec_id, "label": self.label, "status": self.status}

    def to_dict(self) -> dict:
        return {
            "rec_id": self.rec_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "history": [e.to_dict() for e in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        return cls(
            data["rec_id"],
            data["label"],
            data["status"],
            data.get("detail", ""),
            [StripEvent.from_dict(e) for e in data.get("history", [])],
        )


# ---------------------------------------------------------------------------
# The visible file
# ---------------------------------------------------------------------------


class Kardex:
    """The tray: records whose status strips are all visible at once."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._records: dict[str, Record] = {}
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "kardex.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self._records = {
            d["rec_id"]: Record.from_dict(d) for d in data.get("records", [])
        }

    def save(self) -> Path:
        """Persist the file. Only meaningful when constructed with a path."""
        if self.path is None:
            raise KardexError("no path: this file is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"records": [r.to_dict() for r in self._records.values()]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- filing -------------------------------------------------------------
    def add_record(
        self, rec_id: str, label: str, status: str, detail: str = ""
    ) -> Record:
        """Slide a new card into the tray."""
        if not rec_id or not rec_id.strip():
            raise ValueError("rec_id must be non-empty")
        if rec_id in self._records:
            raise DuplicateRecord(rec_id)
        if not status or not status.strip():
            raise ValueError("status must be non-empty")
        record = Record(rec_id, label, status.strip(), detail)
        self._records[rec_id] = record
        return record

    def remove_record(self, rec_id: str) -> Record:
        """Pull a card out of the tray."""
        try:
            return self._records.pop(rec_id)
        except KeyError:
            raise UnknownRecord(rec_id) from None

    # -- the single-card swap -------------------------------------------------
    def update_status(self, rec_id: str, new_status: str) -> Record:
        """One record-swap: the board is current the moment this returns.
        The old strip is appended to the card's history, not discarded."""
        record = self.get(rec_id)
        new_status = new_status.strip()
        if not new_status:
            raise ValueError("status must be non-empty")
        if new_status != record.status:
            record.history.append(
                StripEvent(len(record.history) + 1, record.status, new_status)
            )
            record.status = new_status
        return record

    def get(self, rec_id: str) -> Record:
        try:
            return self._records[rec_id]
        except KeyError:
            raise UnknownRecord(rec_id) from None

    def history(self, rec_id: str) -> list[StripEvent]:
        """The strip's past, oldest first."""
        return list(self.get(rec_id).history)

    # -- the visible file: ambient legibility ---------------------------------
    def board(self) -> list[dict]:
        """Every record's labeled strip, all in one view — sorted for a
        stable glance."""
        return [self._records[k].strip() for k in sorted(self._records)]

    def needs_attention(self, rule: Callable[[Record], bool]) -> list[dict]:
        """The strips that turned red: every record where ``rule`` holds.
        The rule sees the full record; the board shows the strips."""
        return [r.strip() for r in self._records.values() if rule(r)]

    def record_count(self) -> int:
        return len(self._records)


__all__ = [
    "ORIGIN",
    "KardexError",
    "UnknownRecord",
    "DuplicateRecord",
    "StripEvent",
    "Record",
    "Kardex",
]
