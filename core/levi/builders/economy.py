"""Economics-breaker: the no-meter ledger and the 12% marketplace hook.

This module is the answer to the category's #1 complaint — paying per
mistake, including the AI's own. The answer is structural, not a pricing
page: there is no billing unit anywhere in this package. :class:`BuildLedger`
records every build operation at a hard-zero charge and refuses any other
value, so a debugging loop has no meter to burn through. Retries are free
because charging for them is *unrepresentable*.

Revenue comes later, through the marketplace, when creators win:
PLATFORM_CUT = 0.12 is the named constant (Chauncey's law). The hook
computes the cut as a pure function; collecting it is owner-gated and
raises rather than wiring any processor.

No-free-core: entry mechanics (dollar-scale entry, volume over margin) are
owner-gated too — nothing here invents pricing or grants a free tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List

# Chauncey's law: the platform takes 12% on digital products created and
# monetized on our marketplace. Named constant — never a magic number.
# Physical-goods cut is OPEN: invent nothing here.
PLATFORM_CUT = Decimal("0.12")

_CENT = Decimal("0.01")


class OwnerGateRequired(Exception):
    """Raised when an action needs Chauncey's explicit per-action approval.

    Payments, marketplace launch, customer-facing release — all stop here.
    """


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    event: str
    detail: str
    units_charged: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        # The invariant that breaks the credit-burn model: a ledger entry
        # can only ever record zero. There is no charge() method, no price
        # table, no meter — by construction, not by policy.
        if self.units_charged != Decimal("0.00"):
            raise ValueError("builders ledger cannot record a nonzero charge")


class BuildLedger:
    """Append-only record of build work. Every entry costs exactly zero."""

    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []

    def record(self, event: str, detail: str = "") -> LedgerEntry:
        entry = LedgerEntry(
            seq=len(self._entries) + 1,
            event=event,
            detail=detail,
            units_charged=Decimal("0.00"),
        )
        self._entries.append(entry)
        return entry

    def entries(self) -> List[LedgerEntry]:
        return list(self._entries)

    def total_charged(self) -> Decimal:
        total = sum((e.units_charged for e in self._entries), Decimal("0.00"))
        assert total == Decimal("0.00"), "ledger invariant violated"
        return total


def marketplace_royalty(gross: Decimal) -> Decimal:
    """Compute the platform's 12% cut on a monetized digital product.

    Pure function — math only. Collecting the money is a separate,
    owner-gated action (see collect_payment).
    """
    if gross < 0:
        raise ValueError("gross must be >= 0")
    return (gross * PLATFORM_CUT).quantize(_CENT, rounding=ROUND_HALF_UP)


def collect_payment(*args, **kwargs) -> None:
    """Collect marketplace revenue. NEVER WIRED — owner gate stands.

    Any call raises until Chauncey gives explicit per-action approval for
    payment processing. This stub exists so the hook point is named and
    the gate is visible, not to move money.
    """
    # MONEY LAW: fail-closed stub. Always raises; no processor is wired.
    # Naming the hook point is the whole job — nothing moves.
    raise OwnerGateRequired(
        "payment collection is owner-gated: needs Chauncey's explicit "
        "per-action approval before any processor is wired"
    )
