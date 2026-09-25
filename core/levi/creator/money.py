"""Money for the creator platform — Cybrus only, fail-closed.

Every paid flow (subscriptions, tips) on both tracks routes through the
Cybrus :class:`MoneyGateway`. There are no real payment rails, so
``charge()`` always ends blocked: the intent is planned, previewed, and
authorized, then execution refuses with ``NoRailConfigured`` and the
subscription is recorded as ``pending_payment`` with the plan id. Money
never moves; the record is honest about that.

RIGHT mandate (2026-09-22): every money path needs an approval receipt.
The caller passes ``approval_id`` naming a human-approved approval for
this charge; without one, ``charge()`` requests the approval and raises
:class:`MoneyApprovalRequired` carrying the resumable approval id (L11 —
the caller retries after the human approves). Bare authorizations are
refused.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

from levi.cybrus.money import (
    ApprovalReceiptMissing,
    ApprovalReplayRefused,
    DoubleSpendRefused,
    MoneyApprovalRequired,
    MoneyAuthorization,
    MoneyGateway,
    MoneyOperation,
    MoneyRefused,
    NoRailConfigured,
    NotAuthorized,
)

__all__ = ["charge", "MoneyAuthorization", "MoneyRefused", "NoRailConfigured", "NotAuthorized"]


def charge(
    *,
    amount_minor: int,
    currency: str,
    purpose: str,
    identity: str,
    authorization: MoneyAuthorization,
    rail: str = "cybrus",
    approval_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attempt a charge through Cybrus. Returns a status record.

    Status is one of ``blocked`` (no rail — the honest steady state),
    ``refused`` (authorization not the keeper's, or no approval receipt),
    or ``moved`` (only if a real rail and plug-in ever exist). Raises
    :class:`MoneyApprovalRequired` when no ``approval_id`` is supplied —
    the human approval is requested first and the call is retried after
    approval. Raises MoneyRefused on invalid input (e.g. non-positive
    amount).
    """
    gw = MoneyGateway()
    if approval_id is None:
        plan = gw.plan(
            MoneyOperation.CHARGE,
            amount_minor,
            currency,
            rail,
            purpose,
            identity,
        )
        # L11 forward-motion: raise immediately with the resumable id.
        entry = gw.request_execution_approval(plan, subject=identity)
        raise MoneyApprovalRequired(
            entry["id"],
            f"charge of {amount_minor} {currency} needs human approval: "
            f"approve {entry['id'][:8]} (levi cybrus approve {entry['id'][:8]}) "
            f"then retry charge() with approval_id={entry['id'][:8]}",
        )
    # Resumed after human approval: rebuild the EXACT plan the approval
    # was minted for — never a fresh plan (that would rebind the receipt
    # to a different plan_id and the binding check would refuse it).
    plan = gw.plan_from_approval(
        approval_id, expected_operation=MoneyOperation.CHARGE.value
    )
    if (
        plan.amount_minor != amount_minor
        or plan.currency != currency.upper()
        or plan.rail != rail
        or plan.purpose != purpose
        or plan.identity != identity
    ):
        raise MoneyRefused(
            "approval does not match this charge (amount/currency/rail/"
            "purpose/identity differ): request a fresh approval"
        )
    # Bind the caller's authorization to THIS plan and THIS approval. The
    # identity on the authorization is the caller's and is never altered —
    # only the plan_id and approval_id are bound, so the keeper's approval
    # covers exactly this movement.
    bound = replace(authorization, plan_id=plan.plan_id, approval_id=approval_id)
    try:
        gw.execute(plan, bound)
    except (NotAuthorized, ApprovalReceiptMissing, ApprovalReplayRefused,
            DoubleSpendRefused) as exc:
        return {
            "status": "refused",
            "plan_id": plan.plan_id,
            "reason": str(exc),
            "receipt": gw.receipt(plan.plan_id),
        }
    except NoRailConfigured as exc:
        return {
            "status": "blocked",
            "plan_id": plan.plan_id,
            "reason": str(exc),
            "preview": gw.preview(plan),
            "receipt": gw.receipt(plan.plan_id),
        }
    return {
        "status": "moved",
        "plan_id": plan.plan_id,
        "receipt": gw.receipt(plan.plan_id),
    }
