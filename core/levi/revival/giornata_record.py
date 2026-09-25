"""giornata_record — fresco buono: the day carbonates into immutable stone.

Studied from: lost-crafts-20260916 — report.md [Batch 4] (Fresco Buono).

Load-bearing idea: a fresco is painted on wet plaster and can only be
worked while the plaster is damp; once it carbonates it is stone, and
revisions demand *new* plaster laid over the old — a giornata is one
day's patch, sealed forever at day close. LEVI's take: ``Giornata``
accumulates a day's journal entries while open; ``close_day()`` freezes
it into a checksummed, hash-chained immutable record (each giornata
chains the previous day's seal, like courses of plaster). Sealed
records cannot be edited — ``revise()`` lays a *new* giornata that
references the old one, superseding it explicitly. Tamper evidence is
real: ``verify()`` replays the seal computation and the chain.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/giornata-record"


def _seal(day: str, entries: List[Tuple[float, str, str]], prev_seal: str) -> str:
    payload = json.dumps(
        {"day": day, "entries": entries, "prev": prev_seal}, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SealedDay:
    """One carbonated giornata: immutable, checksummed, chain-linked."""

    day: str
    entries: Tuple[Tuple[float, str, str], ...]  # (ts, kind, text)
    prev_seal: str
    seal: str
    supersedes: Optional[str] = None  # seal of the day this revises, if any


class FrescoJournal:
    """A daily journal that carbonates at day close into immutable records."""

    def __init__(self) -> None:
        self.open_day: Optional[str] = None
        self._open_entries: List[Tuple[float, str, str]] = []
        self.sealed: Dict[str, SealedDay] = {}  # seal -> record
        self._by_day: Dict[str, List[str]] = {}  # day -> seals (revisions layer up)

    # -- the wet plaster -----------------------------------------------------

    def begin_day(self, day: str, now: Optional[float] = None) -> None:
        """Open a giornata. Only one patch of plaster is wet at a time."""
        if self.open_day is not None:
            raise ValueError(f"giornata {self.open_day!r} is still wet; close it first")
        self.open_day = day
        self._open_entries = []

    def paint(self, kind: str, text: str, now: Optional[float] = None) -> None:
        """Add an entry while the plaster is damp."""
        if self.open_day is None:
            raise ValueError("no giornata is open; call begin_day() first")
        self._open_entries.append((now if now is not None else time.time(), kind, text))

    # -- carbonation -----------------------------------------------------------

    def close_day(self, now: Optional[float] = None) -> SealedDay:
        """Carbonate the day: freeze, seal, chain. The record is now stone."""
        if self.open_day is None:
            raise ValueError("no giornata is open to close")
        prev_seal = self._latest_seal()
        seal = _seal(self.open_day, self._open_entries, prev_seal)
        record = SealedDay(
            day=self.open_day,
            entries=tuple(self._open_entries),
            prev_seal=prev_seal,
            seal=seal,
        )
        self.sealed[seal] = record
        self._by_day.setdefault(self.open_day, []).append(seal)
        self.open_day = None
        self._open_entries = []
        return record

    # -- revisions are new layers ----------------------------------------------

    def revise(
        self, old_seal: str, day: str, corrections: List[Tuple[str, str]]
    ) -> SealedDay:
        """Revise a sealed day by laying a NEW giornata over it.

        The old record is never touched; the new one carries
        ``supersedes`` pointing at it. ``corrections`` is a list of
        (kind, text) pairs, timestamped at layer time.
        """
        if old_seal not in self.sealed:
            raise KeyError(f"unknown sealed day {old_seal!r}")
        old = self.sealed[old_seal]
        ts = time.time()
        entries = list(old.entries) + [(ts, kind, text) for kind, text in corrections]
        prev_seal = self._latest_seal()
        seal = _seal(day, entries, prev_seal)
        record = SealedDay(
            day=day,
            entries=tuple(entries),
            prev_seal=prev_seal,
            seal=seal,
            supersedes=old_seal,
        )
        self.sealed[seal] = record
        self._by_day.setdefault(day, []).append(seal)
        return record

    # -- tamper evidence ---------------------------------------------------------

    def verify(self, seal: str) -> bool:
        """Recompute the seal and confirm the chain link. True = untampered."""
        record = self.sealed.get(seal)
        if record is None:
            return False
        if _seal(record.day, list(record.entries), record.prev_seal) != record.seal:
            return False
        if record.prev_seal and record.prev_seal not in self.sealed:
            return False
        return True

    def current(self, day: str) -> Optional[SealedDay]:
        """The latest layer for a day (after any revisions)."""
        seals = self._by_day.get(day, [])
        return self.sealed[seals[-1]] if seals else None

    def _latest_seal(self) -> str:
        latest = ""
        for seals in self._by_day.values():
            if seals:
                latest = seals[-1]
        return latest
