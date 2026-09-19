"""Charity currency sink: earned credits fund real-world good.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #18]

The studied shape: honest labor credits tied to philanthropy — a
currency earned by doing real work that can be sunk into causes
("Lunch Money Causes" remixed). The sink matters as much as the mint:
credits leave circulation permanently when donated, which is what
gives the earning its meaning.

LEVI-native re-expression: a ledger of labor credits. Earning events
(labeled by kind of work — contribution, review, tending — with a
per-event cap and a daily earn ceiling) mint credits. Donations sink
them: credits move to a named cause and are destroyed, recorded in a
permanent, append-only giving record. Balances can never go negative;
donations are atomic.

Honest limits: credits are an internal accounting unit, not money and
not convertible to money here. "Causes" are names in a local registry,
not live donation endpoints — wiring a real donation is deliberately
out of scope (no network, no payment rails). The daily earn ceiling is
a heuristic against grinding, not a judgment of work quality.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/charity-sink"

DAILY_EARN_CEILING = 100  # credits any one earner can mint per day
PER_EVENT_CAP = 25  # max credits a single earning event can grant


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    kind: str  # "earn" | "donate" | "cause-add"
    who: str
    amount: int  # + for earn, - for donate
    note: str
    at: float = field(default_factory=time.time)


@dataclass
class Cause:
    name: str
    blurb: str
    received: int = 0  # lifetime credits sunk into this cause
    added_at: float = field(default_factory=time.time)


class CharitySinkError(ValueError):
    pass


class CharitySink:
    """Earn credits by honest labor; sink them into causes, permanently."""

    def __init__(self) -> None:
        self._balances: Dict[str, int] = {}
        self._causes: Dict[str, Cause] = {}
        self._ledger: List[LedgerEntry] = []
        self._seq = itertools.count(1)
        # (who, day) -> credits earned that day, for the ceiling
        self._daily: Dict[tuple, int] = {}

    # --- causes ---------------------------------------------------------
    def add_cause(self, name: str, blurb: str = "") -> Cause:
        if not name.strip():
            raise CharitySinkError("cause name cannot be empty")
        if name in self._causes:
            raise CharitySinkError(f"cause {name!r} already registered")
        cause = Cause(name=name, blurb=blurb)
        self._causes[name] = cause
        self._record("cause-add", "system", 0, f"registered cause {name!r}")
        return cause

    def causes(self) -> List[Cause]:
        return sorted(self._causes.values(), key=lambda c: c.name)

    def get_cause(self, name: str) -> Optional[Cause]:
        return self._causes.get(name)

    # --- earning --------------------------------------------------------
    @staticmethod
    def _day(ts: float) -> str:
        return time.strftime("%Y-%m-%d", time.localtime(ts))

    def earn(self, who: str, amount: int, kind: str = "labor", note: str = "") -> int:
        """Mint credits for honest labor. Returns the amount actually minted."""
        if amount <= 0:
            raise CharitySinkError("earn amount must be positive")
        minted = min(amount, PER_EVENT_CAP)
        now = time.time()
        key = (who, self._day(now))
        used = self._daily.get(key, 0)
        room = DAILY_EARN_CEILING - used
        if room <= 0:
            raise CharitySinkError(
                f"{who} has hit the daily earn ceiling ({DAILY_EARN_CEILING})"
            )
        minted = min(minted, room)
        self._daily[key] = used + minted
        self._balances[who] = self._balances.get(who, 0) + minted
        self._record("earn", who, minted, f"{kind}: {note or 'honest labor'}".strip())
        return minted

    # --- donating (the sink) --------------------------------------------
    def donate(self, who: str, cause_name: str, amount: int) -> LedgerEntry:
        """Sink credits into a cause. Credits are destroyed, not transferred."""
        if amount <= 0:
            raise CharitySinkError("donation amount must be positive")
        balance = self._balances.get(who, 0)
        if amount > balance:
            raise CharitySinkError(
                f"{who} has {balance} credits; cannot donate {amount}"
            )
        cause = self._causes.get(cause_name)
        if cause is None:
            raise CharitySinkError(f"unknown cause {cause_name!r}")
        self._balances[who] = balance - amount
        cause.received += amount
        return self._record(
            "donate", who, -amount, f"sunk into {cause_name!r} (destroyed, not moved)"
        )

    # --- reads ----------------------------------------------------------
    def balance(self, who: str) -> int:
        return self._balances.get(who, 0)

    def lifetime_sunk(self, who: str) -> int:
        return sum(
            -e.amount for e in self._ledger if e.kind == "donate" and e.who == who
        )

    def lifetime_earned(self, who: str) -> int:
        return sum(e.amount for e in self._ledger if e.kind == "earn" and e.who == who)

    def giving_record(self, who: Optional[str] = None) -> List[LedgerEntry]:
        """Append-only giving history; the sink's permanent memory."""
        if who is None:
            return list(self._ledger)
        return [e for e in self._ledger if e.who == who]

    def total_sunk(self) -> int:
        return sum(c.received for c in self._causes.values())

    # --- internals ------------------------------------------------------
    def _record(self, kind: str, who: str, amount: int, note: str) -> LedgerEntry:
        entry = LedgerEntry(
            seq=next(self._seq), kind=kind, who=who, amount=amount, note=note
        )
        self._ledger.append(entry)
        return entry
