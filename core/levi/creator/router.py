"""Creator service -> Cybrus choke-point wiring (Build 6 integration).

The creator service is the FIRST live consumer of the Cybrus router
choke point (Build 1, :mod:`levi.cybrus.enforce`): every subscription-token
verification and every payout recording crosses the choke point —
authenticated, rate-limited, policy-checked, audit-logged (metadata
only). This is the compounding rule in action: finished modules go to
work immediately.

Wiring points (in :mod:`levi.creator.subscriptions`):
- ``verify_access`` is guarded with
  ``@cybrus_guarded(service="creator", callee="levi.cybrus")`` — a refused
  call means the token-verification body never runs (fail closed).
- ``record_payout`` routes explicitly through :func:`route` and attaches
  the returned Cybrus routing ticket to the payout record — the money
  itself still moves only through the Cybrus MoneyGateway (L1); the
  choke point adds the routing/audit envelope around it.

Callee choice: the call crosses INTO the Cybrus security core, so the
callee is ``levi.cybrus`` (a first-class internal route) — not
``levi.creator``, which is not a registered route and this module does
not invent routes (originals-first, L7). Policy therefore evaluates as
``("creator", "service.levi.cybrus", <action>)``.

Deployment (deliberate, operator-run — never silent):
1. :func:`ensure_creator_routing` installs the seed-policy addition below
   (additive only; existing rules are never edited or removed).
2. Give the ``creator`` caller a rate-limit tier of at least ``starter``
   (``rate_limits.set_tier("creator", "starter")``) — free-tier callers
   cannot cross the choke point at all.
3. Present a service credential on each call: a Cybrus ``api``-kind token
   carrying the ``service.call`` scope (``cybrus_credential=...``), or a
   named vault API key (``cybrus_api_key=...`` + ``cybrus_gateway=...``).

LAW->GUARD->PROVE: the creator laws (L1-L5, subscriptions.py) and the
choke-point laws (L1-L12, enforce.py) all still hold; the conjunction is
asserted in tests/test_creator_router_integration.py — invariant tests,
honestly named (nothing here is formally proven, only machine-checked).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

#: The choke-point caller identity for the creator service.
CREATOR_CALLER = "creator"

#: The callee the creator service crosses into: the Cybrus security core.
CREATOR_CALLEE = "levi.cybrus"

#: Choke-point actions the creator service uses.
ACTION_VERIFY_ACCESS = "verify_access"
ACTION_RECORD_PAYOUT = "record_payout"


# ---------------------------------------------------------------------------
# SEED-POLICY ADDITION (additive only)
# ---------------------------------------------------------------------------
# Default-deny means the creator service's choke-point crossings need
# explicit allow rules. These are ADDED by ensure_creator_routing() —
# never edited, never removed, never reordered relative to sibling
# rules (no-cancellation, L9). verify_access is low-risk (read-only
# verification); record_payout is medium-risk (money planning stays
# gated by the MoneyGateway's own keeper-authorization, so no human
# approval is required at the choke point — the floor is high).
CREATOR_POLICY_RULES: List[Tuple[str, str, str, str, str]] = [
    # (subject, resource, action, effect, risk)
    (CREATOR_CALLER, "service.levi.cybrus", ACTION_VERIFY_ACCESS, "allow", "low"),
    (CREATOR_CALLER, "service.levi.cybrus", ACTION_RECORD_PAYOUT, "allow", "medium"),
]


def ensure_creator_routing() -> List[Dict]:
    """Install the creator service's seed-policy allow rules, idempotently.

    Adds only rules from :data:`CREATOR_POLICY_RULES` that are not already
    present (compared on the full 5-tuple). Returns the rules that were
    added — empty when everything was already in place. Safe to call
    repeatedly; never touches sibling rules.
    """
    from levi.cybrus.policy import PolicyEngine

    engine = PolicyEngine()
    present = {
        (r["subject"], r["resource"], r["action"], r["effect"], r["risk"])
        for r in engine.list_rules()
    }
    added = []
    for subject, resource, action, effect, risk in CREATOR_POLICY_RULES:
        if (subject, resource, action, effect, risk) not in present:
            added.append(engine.add_rule(subject, resource, action, effect, risk))
    return added


def route(
    action: str,
    payload_ref: Optional[str] = None,
    *,
    credential: Optional[str] = None,
    api_key: Optional[Tuple[str, str]] = None,
    gateway=None,
) -> Dict:
    """Cross the Cybrus choke point for one creator-service operation.

    Thin wrapper over :func:`levi.cybrus.enforce.route_service_call` with
    the creator caller/callee fixed: authenticate -> resolve -> rate-limit
    -> policy -> HITL when high-risk -> metadata-only audit -> ticket.

    Raises :class:`NotAuthenticated` (no/invalid credential),
    :class:`RateLimitDenied` (over quota), :class:`CallDenied` (policy
    deny — deny always wins), :class:`ApprovalRequired` (high-risk allow
    pending human approval). Returns the routing ticket on success.
    """
    from levi.cybrus.enforce import route_service_call

    return route_service_call(
        CREATOR_CALLER,
        CREATOR_CALLEE,
        action,
        payload_ref=payload_ref,
        credential=credential,
        api_key=api_key,
        gateway=gateway,
    )
