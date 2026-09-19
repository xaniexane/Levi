"""Total-immersion sandboxed foreign posting before touching live trade.

Studied from: lost-crafts-20260916/report.md [Batch 1] (the Kontor years:
young merchants spent years at a foreign trading post — a total-immersion
sandbox — copying business letters onto wax tablets (c. 1370 student copies)
before they were trusted with live trade).

This is an original, from-scratch implementation for LEVI. A ``Posting``
places a candidate at a simulated foreign ``Kontor`` (market) for a run of
practice seasons. Each season the sandbox deals a deterministic simulated
market state; the candidate records *copy-book entries* — practice drafts of
the decisions a real trader would make (buy/sell/hold quantities at quoted
prices). Entries are scored against the sandbox's own outcomes (a simple
mark-to-market ledger), never against real markets. Promotion to live trade
requires: every season attempted, a minimum number of copy-book entries, and
a ledger balance at or above the starting stake — i.e. the candidate must not
have lost the sandbox's money. The ``live_trade_clearance()`` gate returns a
clear pass/fail with reasons; nothing here touches real trade.

The mechanism is heuristic simulation, and the docstring says so: the market
generator is a deterministic seeded walk, not a model of any real market.

Public surface:
- ``Kontor``: ``post(candidate)`` -> ``Posting``.
- ``Posting``: ``season_market()``, ``copy_entry(...)``, ``ledger()``,
  ``live_trade_clearance()`` -> ``Clearance``.
- ``Clearance``, ``MarketError`` for embedding.

stdlib-only. No network. Deterministic (seeded; no random module).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/kontor-years"


class MarketError(ValueError):
    """Raised when a sandbox step cannot be honored."""


@dataclass(frozen=True)
class MarketState:
    season: int
    good: str
    bid: float
    ask: float


@dataclass(frozen=True)
class CopyEntry:
    """A wax-tablet copy: the candidate's practice draft of a trade."""

    season: int
    action: str  # buy | sell | hold
    quantity: int
    price: float


@dataclass(frozen=True)
class Clearance:
    candidate: str
    granted: bool
    reasons: List[str]


class _Ledger:
    """Sandbox mark-to-market ledger. Practice money only."""

    def __init__(self, stake: float) -> None:
        self.stake = stake
        self.cash = stake
        self.inventory: Dict[str, int] = {}
        self.entries: List[CopyEntry] = []

    def apply(self, entry: CopyEntry, market: MarketState) -> None:
        if entry.action == "buy":
            cost = entry.quantity * market.ask
            if cost > self.cash:
                raise MarketError("sandbox: insufficient practice cash")
            self.cash -= cost
            self.inventory[market.good] = (
                self.inventory.get(market.good, 0) + entry.quantity
            )
        elif entry.action == "sell":
            held = self.inventory.get(market.good, 0)
            if entry.quantity > held:
                raise MarketError("sandbox: cannot sell what the sandbox does not hold")
            self.cash += entry.quantity * market.bid
            self.inventory[market.good] = held - entry.quantity
        elif entry.action == "hold":
            if entry.quantity != 0:
                raise MarketError("sandbox: hold must have quantity 0")
        else:
            raise MarketError(f"sandbox: unknown action {entry.action!r}")
        self.entries.append(entry)

    def net_worth(self, market: MarketState) -> float:
        held = self.inventory.get(market.good, 0)
        return self.cash + held * market.bid


class Kontor:
    """A simulated foreign trading post. Deterministic sandbox markets."""

    def __init__(
        self,
        name: str,
        good: str = "cloth",
        seasons: int = 4,
        stake: float = 1000.0,
        min_entries: int = 6,
        seed: str = "levi-kontor",
    ) -> None:
        if not name:
            raise MarketError("kontor must be named")
        if seasons < 1:
            raise MarketError("seasons must be >= 1")
        if stake <= 0:
            raise MarketError("stake must be positive")
        self.name = name
        self.good = good
        self.seasons = seasons
        self.stake = stake
        self.min_entries = min_entries
        self.seed = seed

    def market(self, season: int) -> MarketState:
        """Deterministic simulated market for a season (1-based)."""
        if not 1 <= season <= self.seasons:
            raise MarketError(f"season {season} out of range 1..{self.seasons}")
        # Seeded walk: mid price drifts deterministically per season.
        digest = hashlib.sha256(
            f"{self.seed}|{self.good}|{season}".encode()
        ).hexdigest()
        drift = (int(digest[:8], 16) % 2000 - 1000) / 10000.0  # -10%..+10%
        mid = 100.0 * (1.0 + drift * season)
        spread = 2.0
        return MarketState(
            season=season, good=self.good, bid=mid - spread / 2, ask=mid + spread / 2
        )

    def post(self, candidate: str) -> "Posting":
        return Posting(kontor=self, candidate=candidate)


class Posting:
    """One candidate's total-immersion sandbox posting."""

    def __init__(self, kontor: Kontor, candidate: str) -> None:
        if not candidate:
            raise MarketError("candidate must be named")
        self.kontor = kontor
        self.candidate = candidate
        self._ledger = _Ledger(kontor.stake)
        self._seasons_done: List[int] = []
        self._current: Optional[MarketState] = None

    def begin_season(self, season: int) -> MarketState:
        if self._current is not None:
            raise MarketError("finish the current season first (end_season)")
        if season in self._seasons_done:
            raise MarketError(f"season {season} already completed")
        self._current = self.kontor.market(season)
        return self._current

    def copy_entry(self, action: str, quantity: int, price: float) -> CopyEntry:
        """Draft one wax-tablet copy against the current season's market."""
        if self._current is None:
            raise MarketError("no season in progress; call begin_season first")
        if quantity < 0:
            raise MarketError("quantity must be >= 0")
        entry = CopyEntry(
            season=self._current.season, action=action, quantity=quantity, price=price
        )
        self._ledger.apply(entry, self._current)
        return entry

    def end_season(self) -> MarketState:
        if self._current is None:
            raise MarketError("no season in progress")
        done = self._current
        self._seasons_done.append(done.season)
        self._current = None
        return done

    def seasons_completed(self) -> List[int]:
        return list(self._seasons_done)

    def ledger_entries(self) -> List[CopyEntry]:
        return list(self._ledger.entries)

    def sandbox_worth(self) -> float:
        """Practice net worth marked against the last completed season."""
        if not self._seasons_done:
            return self._ledger.cash
        market = self.kontor.market(self._seasons_done[-1])
        return self._ledger.net_worth(market)

    def live_trade_clearance(self) -> Clearance:
        """The gate: pass only if the candidate finished every season, wrote
        enough copy-book entries, and did not lose the sandbox stake."""
        reasons: List[str] = []
        missing = [
            s for s in range(1, self.kontor.seasons + 1) if s not in self._seasons_done
        ]
        if missing:
            reasons.append(f"seasons not completed: {missing}")
        n = len(self._ledger.entries)
        if n < self.kontor.min_entries:
            reasons.append(
                f"only {n} copy-book entries; need {self.kontor.min_entries}"
            )
        worth = self.sandbox_worth()
        if worth < self.kontor.stake:
            reasons.append(
                f"sandbox stake lost: worth {worth:.2f} < stake {self.kontor.stake:.2f}"
            )
        granted = not reasons
        if granted:
            reasons.append(
                f"cleared: {self.kontor.seasons} seasons, {n} entries, worth {worth:.2f}"
            )
        return Clearance(candidate=self.candidate, granted=granted, reasons=reasons)
