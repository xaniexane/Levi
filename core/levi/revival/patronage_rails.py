"""patronage_rails — protocol-level patronage, no platform wallet.

Studied from: github-pattern-hunt-20260916-0018 (report.md [Ranked additions 10]).
Load-bearing idea: funding rails that move peer-to-peer — no platform
wallet, no platform fee, no custody. The protocol records intents and
receipts; the money never parks with a middleman.

LEVI's take: ``Patronage`` keeps a ledger of ``Pledge``s (a patron's
promise to a creator: amount, currency, cadence) and ``Receipt``s (both
parties confirm a transfer completed *off-system*). Platform fee is
structurally zero — there is no field, no hook, no way to levy one. The
ledger is an honest accounting surface, not a custodian.

Honest limits: LEVI moves no money. Settlement happens wherever patron
and creator agree to settle; the receipt is only as true as the two
confirmations behind it.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/patronage-rails"

PLATFORM_FEE = 0.0  # structural: no fee exists in this protocol


@dataclass
class Pledge:
    """A patron's funding promise to a creator."""

    id: str
    patron: str
    creator: str
    amount: float
    currency: str
    cadence: str = "one-off"  # one-off | monthly | quarterly | yearly
    note: str = ""
    created_at: float = 0.0
    active: bool = True
    settled_total: float = 0.0

    def due_epochs(self) -> int:
        """Number of settlement epochs this pledge covers so far."""
        return {"one-off": 1, "monthly": 1, "quarterly": 1, "yearly": 1}[self.cadence]


@dataclass
class Receipt:
    """Both parties confirmed a transfer completed off-system."""

    id: str
    pledge_id: str
    amount: float
    currency: str
    patron_confirmed: bool = False
    creator_confirmed: bool = False
    settled_at: float = 0.0
    note: str = ""

    @property
    def complete(self) -> bool:
        return self.patron_confirmed and self.creator_confirmed


class Patronage:
    """Peer-to-peer patronage ledger. No wallet, no custody, no fee."""

    def __init__(self) -> None:
        self.pledges: Dict[str, Pledge] = {}
        self.receipts: Dict[str, Receipt] = {}

    # -- pledges --------------------------------------------------------------

    def pledge(
        self,
        patron: str,
        creator: str,
        amount: float,
        currency: str = "USD",
        cadence: str = "one-off",
        note: str = "",
    ) -> Pledge:
        if amount <= 0:
            raise ValueError("pledge amount must be positive")
        if cadence not in ("one-off", "monthly", "quarterly", "yearly"):
            raise ValueError(f"unknown cadence {cadence!r}")
        if patron == creator:
            raise ValueError("patron and creator must differ")
        p = Pledge(
            id=f"plg-{uuid.uuid4().hex[:8]}",
            patron=patron,
            creator=creator,
            amount=amount,
            currency=currency,
            cadence=cadence,
            note=note,
            created_at=time.time(),
        )
        self.pledges[p.id] = p
        return p

    def pause_pledge(self, pledge_id: str) -> Pledge:
        p = self.pledges[pledge_id]
        p.active = False
        return p

    def resume_pledge(self, pledge_id: str) -> Pledge:
        p = self.pledges[pledge_id]
        p.active = True
        return p

    def pledges_for(self, who: str, as_patron: bool = True) -> List[Pledge]:
        side = "patron" if as_patron else "creator"
        return [p for p in self.pledges.values() if getattr(p, side) == who]

    # -- receipts: off-system settlement, dual confirmation -------------------

    def open_receipt(
        self, pledge_id: str, amount: Optional[float] = None, note: str = ""
    ) -> Receipt:
        p = self.pledges[pledge_id]
        r = Receipt(
            id=f"rcp-{uuid.uuid4().hex[:8]}",
            pledge_id=pledge_id,
            amount=p.amount if amount is None else amount,
            currency=p.currency,
            note=note,
        )
        self.receipts[r.id] = r
        return r

    def confirm(self, receipt_id: str, by: str) -> Receipt:
        """Confirm a receipt as patron or creator. Two confirmations settle it."""
        r = self.receipts[receipt_id]
        p = self.pledges[r.pledge_id]
        if by == p.patron:
            r.patron_confirmed = True
        elif by == p.creator:
            r.creator_confirmed = True
        else:
            raise ValueError(f"{by!r} is not a party to this pledge")
        if r.complete and r.settled_at == 0.0:
            r.settled_at = time.time()
            p.settled_total += r.amount
            if p.cadence == "one-off":
                p.active = False
        return r

    # -- accounting -----------------------------------------------------------

    def creator_totals(self) -> Dict[str, float]:
        """Settled amounts per creator (dual-confirmed receipts only)."""
        totals: Dict[str, float] = {}
        for r in self.receipts.values():
            if r.complete:
                creator = self.pledges[r.pledge_id].creator
                totals[creator] = totals.get(creator, 0.0) + r.amount
        return totals

    def open_pledges_total(self, creator: str) -> float:
        return sum(
            p.amount for p in self.pledges.values() if p.creator == creator and p.active
        )

    # -- snapshots ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "pledges": {k: asdict(v) for k, v in self.pledges.items()},
            "receipts": {k: asdict(v) for k, v in self.receipts.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Patronage":
        pat = cls()
        for k, v in d.get("pledges", {}).items():
            pat.pledges[k] = Pledge(**v)
        for k, v in d.get("receipts", {}).items():
            pat.receipts[k] = Receipt(**v)
        return pat
