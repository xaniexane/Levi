"""Bounty payments — through the Cybrus money gateway, and ONLY there.

Binding law (Chauncey, 2026-09-17): Cybrus is the only one ever allowed
to handle money. This module never moves money itself; it plans quotes
and routes settlement through ``levi.cybrus.money.MoneyGateway``.

Payment states on the bounty: none -> quoted -> agreed -> delivered -> paid.

- quoted: a gateway PLAN exists (a quote — preview, not permission).
- agreed: client agreed to the terms (recorded on the bounty).
- delivered: solution delivered (no money moved yet).
- paid: ONLY on a gateway receipt showing an executed movement.

Honest boundary: with no payment rails registered and no rail plug-ins
wired, ``MoneyGateway.execute()`` always refuses (fail-closed). So
``paid`` is structurally unreachable until Chauncey deliberately
registers a rail. This module records that refusal truthfully instead
of pretending payment happened. Quotes are quotes, not charges.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from levi.bounty.hunts import Bounty, BountyError, BountyState
from levi.cybrus.money import (
    MoneyAuthorization,
    MoneyGateway,
    MoneyOperation,
    MoneyPlan,
    MoneyRefused,
)

# The only money-moving API this module may call. Nothing else in
# levi.bounty may import a payment SDK, call a payment endpoint, or
# otherwise move funds. (Enforced by tests/test_bounty_hunter.py.)
_GATEWAY = MoneyGateway()


def _usd_to_cents(amount_usd: float) -> int:
    cents = int(round(amount_usd * 100))
    if cents <= 0:
        raise BountyError(f"payment amount must be positive, got {amount_usd!r}")
    return cents


def request_payment(bounty: Bounty, *, gateway: Optional[MoneyGateway] = None) -> Dict[str, Any]:
    """PLAN the payment: build the gateway plan, move nothing.

    Requires the bounty to be at least QUOTED. Records the plan on the
    bounty and sets payment_state=quoted. The preview is NOT permission.
    """
    if bounty.quote_usd is None:
        raise BountyError("cannot plan payment without a quote — run quote first")
    gw = gateway or _GATEWAY
    plan = gw.plan(
        MoneyOperation.CHARGE,
        _usd_to_cents(bounty.quote_usd),
        "USD",
        rail="bounty-pending",
        purpose=f"bounty {bounty.id}: {bounty.title}",
        identity=bounty.client or "client",
    )
    bounty.payment_plan = asdict(plan)
    bounty.payment_plan_id = plan.plan_id
    bounty.payment_state = "quoted"
    bounty.log("payment_planned", f"gateway plan {plan.plan_id} (quote, not a charge)")
    return {"plan_id": plan.plan_id, "preview": gw.preview(plan), "moved": False}


def record_agreement(bounty: Bounty, *, note: str) -> Bounty:
    """Record the client's agreement to the quoted terms."""
    if bounty.payment_state != "quoted":
        raise BountyError("agreement requires a planned payment first (payment_state=quoted)")
    if not note.strip():
        raise BountyError("agreement requires a recorded note")
    bounty.payment_state = "agreed"
    bounty.log("payment_agreed", note.strip())
    return bounty


def mark_delivered_for_payment(bounty: Bounty) -> Bounty:
    """Mark the payment side delivered (solution already delivered)."""
    if bounty.state != BountyState.DELIVERED.value:
        raise BountyError("payment can only follow an actual delivery")
    bounty.payment_state = "delivered"
    bounty.log("payment_deliverable", "solution delivered; payment now due")
    return bounty


def settle_bounty(
    bounty: Bounty,
    *,
    authorized_by: str,
    note: str = "",
    gateway: Optional[MoneyGateway] = None,
) -> Dict[str, Any]:
    """Attempt settlement through the Cybrus gateway. Fail-closed.

    ``authorized_by`` must be Chauncey's keeper identity — the module
    never defaults it, never forges it. With no rails registered this
    ALWAYS refuses; the refusal is recorded on the bounty and re-raised.
    On success (rails + authorization), the gateway receipt is recorded
    and the bounty moves to PAID.
    """
    if not authorized_by or not authorized_by.strip():
        raise BountyError("settlement requires an explicit authorized_by identity")
    if bounty.payment_plan is None:
        raise BountyError("no payment plan — run payment plan first")
    if bounty.state != BountyState.DELIVERED.value:
        raise BountyError("settlement requires a delivered bounty")
    gw = gateway or _GATEWAY
    plan = MoneyPlan(**bounty.payment_plan)
    auth = MoneyAuthorization(
        authorized_by=authorized_by.strip(),
        plan_id=plan.plan_id,
        operation=plan.operation,
        note=note,
    )
    try:
        result = gw.execute(plan, auth)
    except MoneyRefused as exc:
        bounty.log("payment_refused", f"gateway refused: {exc}")
        raise
    receipt = gw.receipt(plan.plan_id)
    bounty.payment_receipt = receipt
    bounty.payment_state = "paid"
    bounty.log("payment_settled", f"gateway receipt for plan {plan.plan_id}")
    from levi.bounty.hunts import transition

    transition(bounty, BountyState.PAID)
    return {"plan_id": plan.plan_id, "receipt": receipt, "result": result}


def payment_status(
    bounty: Bounty, *, gateway: Optional[MoneyGateway] = None
) -> Dict[str, Any]:
    """Honest payment status: what was planned, what the gateway says."""
    gw = gateway or _GATEWAY
    out: Dict[str, Any] = {
        "bounty_id": bounty.id,
        "payment_state": bounty.payment_state,
        "plan_id": bounty.payment_plan_id,
        "moved": False,
    }
    if bounty.payment_plan_id:
        out["gateway"] = gw.verify(bounty.payment_plan_id)
        out["moved"] = "executed" in (out["gateway"].get("events") or [])
    return out


__all__ = [
    "MoneyRefused",
    "request_payment",
    "record_agreement",
    "mark_delivered_for_payment",
    "settle_bounty",
    "payment_status",
]
