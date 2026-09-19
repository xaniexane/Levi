"""Money for the creator platform — Cybrus only, fail-closed.

Every paid flow (subscriptions, tips) on both tracks routes through the
Cybrus :class:`MoneyGateway`. There are no real payment rails, so
``charge()`` always ends blocked: the intent is planned, previewed, and
authorized, then execution refuses with ``NoRailConfigured`` and the
subscription is recorded as ``pending_payment`` with the plan id. Money
never moves; the record is honest about that.

The caller must supply an explicit :class:`MoneyAuthorization` — it is
never fabricated here. A non-keeper authorization refuses with
``NotAuthorized`` before any rail is consulted.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

from levi.cybrus.money import (
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
) -> Dict[str, Any]:
    """Attempt a charge through Cybrus. Returns a status record.

    Status is one of ``blocked`` (no rail — the honest steady state),
    ``refused`` (authorization not the keeper's), or ``moved`` (only if a
    real rail and plug-in ever exist). Raises MoneyRefused on invalid
    input (e.g. non-positive amount).
    """
    gw = MoneyGateway()
    plan = gw.plan(
        MoneyOperation.CHARGE,
        amount_minor,
        currency,
        rail,
        purpose,
        identity,
    )
    # Bind the caller's authorization to THIS plan. The identity on the
    # authorization is the caller's and is never altered — only the plan_id
    # is bound, so the keeper's approval covers exactly this movement.
    bound = replace(authorization, plan_id=plan.plan_id)
    try:
        gw.execute(plan, bound)
    except NotAuthorized as exc:
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
