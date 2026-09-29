"""Money — 70/30 split, Cybrus-only, fail-closed (L4).

The law: paid flows split 70% creator / 30% platform and move ONLY
through ``levi.cybrus.money.MoneyGateway`` — the single choke point.
This module holds NO rail references, no keys, no payment data, and no
private rail registry; it is the product-side adapter that plans the
movement (the 70/30 split rides along as plan metadata) and runs it
through the gateway's six-gate flow:

    plan -> preview -> permission -> execute -> verify -> receipt

``charge()`` without an ``approval_id`` plans the movement and raises
``MoneyApprovalRequired`` carrying the pending approval id (nothing
moves); a human approves with ``levi cybrus approve <id>``; the retry
with ``approval_id`` executes through the gateway.

MONEY LAW: ``def charge`` below matches the money-verb scan in
tests/test_money_law.py — it is allowlisted there as a gateway-routed
adapter. It moves nothing itself; all movement is the gateway's.
"""

from __future__ import annotations

from typing import Dict, Optional


CREATOR_SHARE = 0.70
PLATFORM_SHARE = 0.30


class MoneyRailClosed(Exception):
    """Raised when money is asked to move with no Cybrus path. Fail-closed."""


def split_70_30(amount_cents: int) -> Dict[str, int]:
    """Deterministic 70/30 split. Creator rounds down; platform takes the rest."""
    if amount_cents < 0:
        raise ValueError("amount_cents must be >= 0")
    creator = int(amount_cents * CREATOR_SHARE)
    platform = amount_cents - creator
    return {
        "creator_cents": creator,
        "platform_cents": platform,
        "total_cents": amount_cents,
    }


def rail_status() -> Dict:
    """Read-only posture report: money moves only through the gateway.

    The module holds no rails of its own; this reports the gateway's
    registered rails plus the standing fail-closed posture. Keys
    ``mode``/``via`` are kept for ``levi buzztunes money``.
    """
    from levi.cybrus.money import MoneyGateway

    names = [r.name for r in MoneyGateway().list_rails()]
    return {
        "registered": bool(names),
        "rails": names,
        "via": "cybrus",
        "mode": "paper-only",  # no payment plug-in wired — the honest boundary
        "law": "Cybrus alone handles money.",
    }


def charge(
    customer_id: str,
    amount_cents: int,
    memo: str = "",
    *,
    currency: str = "usd",
    identity: str,
    authorized_by: str = "chauncey",
    approval_id: Optional[str] = None,
) -> Dict:
    """Charge through levi.cybrus.money.MoneyGateway — fail-closed.

    MONEY LAW (module docstring): gateway-routed adapter; moves nothing
    itself. Ceremony (mirrors voidbox.enforce.charge_guarded):

    1. Call WITHOUT ``approval_id``: plans the movement with the 70/30
       split attached, seeks the human approval, and raises
       ``MoneyApprovalRequired`` carrying the pending approval id.
       Nothing moves.
    2. A human approves: ``levi cybrus approve <id>``.
    3. Retry WITH ``approval_id``: rebuilds the EXACT plan the approval
       was minted for (a rebound approval is refused), executes through
       the gateway, and returns the gateway receipt with the split
       attached. The approval is consumed atomically; with no rail
       registered and no payment plug-in wired the movement refuses
       (fail-closed) — the honest current posture.
    """
    from levi.cybrus.money import (
        MoneyApprovalRequired,
        MoneyAuthorization,
        MoneyGateway,
        MoneyOperation,
    )

    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise MoneyRailClosed(
            "charge refused: amount_cents must be a positive integer "
            "of minor units (no float money)."
        )
    split = split_70_30(amount_cents)
    purpose = "buzztunes 70/30: creator=%d platform=%d" % (
        split["creator_cents"],
        split["platform_cents"],
    ) + (" — " + memo if memo else "")
    gw = MoneyGateway()

    if approval_id is None:
        # Raise side: plan -> request approval -> raise, nothing moves.
        plan = gw.plan(
            MoneyOperation.CHARGE,
            amount_cents,
            currency,
            "cybrus",
            purpose,
            identity,
        )
        entry = gw.request_execution_approval(plan, subject=identity)
        raise MoneyApprovalRequired(
            entry["id"],
            "buzztunes charge needs human approval: approve %s with "
            "`levi cybrus approve %s` then retry charge with "
            "approval_id=%s. Nothing moves until then."
            % (entry["id"][:8], entry["id"][:8], entry["id"][:8]),
        )

    # Consume side: rebuild the EXACT plan the approval was minted for,
    # then execute through the gateway's RED-1 consume + fail-closed
    # rail checks.
    plan = gw.plan_from_approval(approval_id, expected_operation="charge")
    gw.execute(
        plan,
        MoneyAuthorization(
            authorized_by=authorized_by,
            plan_id=plan.plan_id,
            operation="charge",
            approval_id=approval_id,
        ),
    )
    receipt = gw.receipt(plan.plan_id)
    receipt.update({"customer_id": customer_id, "split": split, "via": "cybrus"})
    return receipt
