"""Creator subscription service — profiles, tiers, subscriptions, access tokens, payouts.

General-audience creator content service (OnlyFans-style): creators
publish gated content, subscribers pay per tier, payouts settle through
the Cybrus money gateway.

LAWS (invariant-first; the tests below name the proof honestly —
invariant tests, not formal proof):

- L1 — ALL money movement goes through the Cybrus
  :class:`~levi.cybrus.money.MoneyGateway`. No side ledgers, no parallel
  money path. Every charge and payout is a gateway operation with a plan
  id, a six-gate trail, and a receipt. Current rails are paper-only:
  subscriptions record as ``pending_payment`` and payouts as
  ``pending_payout`` — the record says so, plainly.
- L2 — Content access requires a Cybrus-issued, Cybrus-verified token,
  checked SERVER-SIDE on every access. The token is bearer convenience
  only: the module re-checks the subscription (active, not expired, not
  cancelled) and the content gate on each call. Never trust the client.
- L3 — Audit is metadata-only: operation, amount, identity, decision,
  plan id. No secrets, no credentials, no payout account data — ever.
- L4 — A creator's ``payout_reference`` is an OPAQUE LABEL (e.g.
  ``"bank-ref-8472"``), never a credential. Secret-looking values are
  rejected at write time and the reference never enters audit logs.
- L5 — The safety.py track gates cannot be bypassed: SI calls require
  the Plaiground adult gate + bounds-checked text; AI calls require the
  SFW rules. Publishing, subscribing, token issuance, and payouts all
  pass through the gate first, fail-closed.

Track isolation: this module is track-parameterized (``"si"`` | ``"ai"``)
and routes storage through :mod:`levi.creator.store` ``si_*`` / ``ai_*``
only. The tracks never merge — separate dirs, separate code paths, no
cross-track queries.

Choke-point wiring (Build 6): ``verify_access`` and ``record_payout``
cross the Cybrus router choke point (service ``"creator"`` ->
``"levi.cybrus"``, see :mod:`levi.creator.router`) — authenticated,
rate-limited, policy-checked, audit-logged (metadata only). The money
path is unchanged: L1 still holds, payouts still settle only through
the MoneyGateway, now with the choke-point routing ticket attached.

Honest paper state: with no registered money rail (the standing state),
``subscribe()`` charges through the gateway, gets ``NoRailConfigured``,
and records the subscription as ``pending_payment`` with ``paper=True``.
Access on a paper subscription is labeled paper. No real payment, no
real money — the receipts say exactly that.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import router as _router
from levi.creator.money import (
    MoneyAuthorization,
    MoneyRefused,
    NoRailConfigured,
    NotAuthorized,
    charge,
)
from levi.creator.pricing import (
    CREATOR_SCHEDULE,
    creator_share,
    platform_fee,
    suggested_tiers,
)
from levi.creator.store import (
    ai_read_all,
    ai_update,
    ai_write,
    si_read_all,
    si_update,
    si_write,
)
from levi.cybrus.money import (
    MoneyApprovalRequired,
    MoneyGateway,
    MoneyOperation,
)
from levi.cybrus.enforce import cybrus_guarded
from levi.cybrus.tokens import TokenEngine, TokenError

_TRACKS = (TRACK_SI, TRACK_AI)

# Access tokens are short-lived bearer credentials: 15 minutes.
ACCESS_TOKEN_TTL = 15 * 60

PERIOD_SECONDS = {"day": 24 * 3600, "week": 7 * 24 * 3600, "month": 30 * 24 * 3600}

#: Statuses a subscription can hold. "active" means money moved through a
#: real rail; "pending_payment" means the charge was blocked (no rail) and
#: the subscription exists on paper only (``paper=True`` on the record).
SUB_ACTIVE = "active"
SUB_PENDING = "pending_payment"
SUB_CANCELLED = "cancelled"

# L4: a payout reference is a label, never a credential. Reject anything
# that smells like a secret so it can never be one.
_SECRETISH = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|private[_-]?key|token|"
    r"credential|ssn|card[_-]?number|cvv|pin[_-]?code|seed[_-]?phrase)"
)


class SubscriptionError(ValueError):
    """A subscription operation was invalid."""


class AccessDeniedError(PermissionError):
    """Access was denied: no valid subscription, bad/expired token, or gate failed."""


class PayoutError(ValueError):
    """A payout could not be planned or recorded."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _check_track(track: str) -> None:
    if track not in _TRACKS:
        raise SubscriptionError("track must be one of %r" % (_TRACKS,))


def _guard(track: str, home: Optional[Path], *texts: str) -> List[str]:
    """L5: the safety.py track gates, applied here.

    Mirrors ``levi.creator.safety._guard_and_clean`` (deliberately not
    imported — the rule is the same, the module boundary stays clean):
    SI -> adult gate, then bounds-checked text; AI -> SFW rules.
    Called with no texts, the gate still fires (SI locked = fail closed).
    """
    _check_track(track)
    if track == TRACK_SI:
        from levi.plaiground.bounds import check_bounds
        from levi.plaiground.gate import require_adult

        require_adult(home)
        return [check_bounds(t or "", home) for t in texts]
    from levi.creator.ai.rules import check_sfw

    return [check_sfw(t or "", home) for t in texts]


def _read_all(track: str, home: Optional[Path], kind: str) -> List[Dict[str, Any]]:
    return si_read_all(home, kind) if track == TRACK_SI else ai_read_all(home, kind)


def _write(track: str, home: Optional[Path], kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
    return si_write(home, kind, record) if track == TRACK_SI else ai_write(home, kind, record)


def _update(
    track: str, home: Optional[Path], kind: str, record_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    return (
        si_update(home, kind, record_id, updates)
        if track == TRACK_SI
        else ai_update(home, kind, record_id, updates)
    )


def _check_payout_reference(ref: str) -> str:
    """L4: the payout reference is an opaque label — never a credential."""
    if not isinstance(ref, str) or not ref.strip():
        raise SubscriptionError("payout_reference is required (an opaque label, never a secret)")
    cleaned = ref.strip()
    if len(cleaned) > 128:
        raise SubscriptionError("payout_reference must be <= 128 chars")
    if not cleaned.isprintable():
        raise SubscriptionError("payout_reference must be printable text")
    if _SECRETISH.search(cleaned):
        raise SubscriptionError(
            "payout_reference must be an opaque label (e.g. 'bank-ref-8472'), "
            "never a credential or secret"
        )
    return cleaned


# -- Creator profiles ---------------------------------------------------


def create_profile(
    handle: str,
    display_name: str,
    bio: str,
    payout_reference: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a creator profile. ``payout_reference`` is an opaque label
    (L4) — the actual payout destination lives with the creator's money
    rail setup, never in this store. L5 gate applies."""
    _check_track(track)
    display_name, bio = _guard(track, home, display_name, bio)
    if not handle or not handle.strip():
        raise SubscriptionError("handle is required")
    handle = handle.strip()
    if any(p["handle"] == handle for p in _read_all(track, home, "creator_profiles")):
        raise SubscriptionError("handle %r already exists on this track" % handle)
    return _write(
        track,
        home,
        "creator_profiles",
        {
            "track": track,
            "handle": handle,
            "display_name": display_name,
            "bio": bio,
            "payout_reference": _check_payout_reference(payout_reference),
            "created_at": _utcnow_iso(),
        },
    )


def get_profile(creator_id: str, track: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch one creator profile. The gate still fires (L5)."""
    _guard(track, home)
    profile = next(
        (p for p in _read_all(track, home, "creator_profiles") if p["id"] == creator_id),
        None,
    )
    if profile is None:
        raise SubscriptionError("unknown creator %r" % creator_id)
    return profile


def list_profiles(track: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """All creator profiles on this track. Gate applies."""
    _guard(track, home)
    return _read_all(track, home, "creator_profiles")


# -- Tiers --------------------------------------------------------------


def creator_tier_suggestions() -> List[Dict[str, Any]]:
    """Suggested tiers from the standing creator pricing schedule
    (:mod:`levi.creator.pricing`): $1 taste / $4 monthly / $20 patron,
    ranked by price. The keeper's schedule is the spec; this reuses it."""
    out = []
    for rank, t in enumerate(suggested_tiers("creator")):
        out.append({**t, "rank": rank})
    return out


def add_tier(
    creator_id: str,
    name: str,
    price_minor: int,
    period: str,
    track: str,
    rank: Optional[int] = None,
    perks: Optional[List[str]] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Add a subscription tier for a creator. Rank orders tiers: higher
    rank unlocks everything lower ranks unlock (tier-based gating)."""
    _check_track(track)
    creator = get_profile(creator_id, track, home)  # gate + ownership anchor
    (name,) = _guard(track, home, name)
    if not isinstance(price_minor, int) or price_minor <= 0:
        raise SubscriptionError("price_minor must be a positive integer (cents)")
    if period not in PERIOD_SECONDS:
        raise SubscriptionError("period must be one of %r" % (tuple(PERIOD_SECONDS),))
    if any(
        t["creator_id"] == creator_id and t["name"] == name
        for t in _read_all(track, home, "creator_tiers")
    ):
        raise SubscriptionError("tier %r already exists for this creator" % name)
    if rank is None:
        siblings = [t for t in _read_all(track, home, "creator_tiers") if t["creator_id"] == creator_id]
        rank = max([t.get("rank", 0) for t in siblings], default=-1) + 1
    cleaned_perks = _guard(track, home, *(perks or []))
    return _write(
        track,
        home,
        "creator_tiers",
        {
            "track": track,
            "creator_id": creator["id"],
            "name": name,
            "price_minor": price_minor,
            "period": period,
            "rank": int(rank),
            "perks": cleaned_perks,
            "created_at": _utcnow_iso(),
        },
    )


def list_tiers(creator_id: str, track: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The creator's tiers, lowest rank first. Gate applies."""
    _guard(track, home)
    return sorted(
        (t for t in _read_all(track, home, "creator_tiers") if t["creator_id"] == creator_id),
        key=lambda t: (t.get("rank", 0), t["price_minor"]),
    )


def get_tier(tier_id: str, track: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch one tier. Gate applies."""
    _guard(track, home)
    tier = next(
        (t for t in _read_all(track, home, "creator_tiers") if t["id"] == tier_id),
        None,
    )
    if tier is None:
        raise SubscriptionError("unknown tier %r" % tier_id)
    return tier


# -- Subscriptions ------------------------------------------------------


def _expires_at(period: str, start: datetime) -> str:
    return (start + timedelta(seconds=PERIOD_SECONDS[period])).isoformat()


def _sub_valid(sub: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """A subscription grants access while it is inside its paid period.

    Cancellation stops renewal, not the period: a cancelled subscription
    stays valid until ``expires_at``."""
    now = now or _utcnow()
    return (
        sub["status"] in (SUB_ACTIVE, SUB_PENDING, SUB_CANCELLED)
        and datetime.fromisoformat(sub["expires_at"]) > now
    )


def subscribe(
    creator_id: str,
    tier_id: str,
    subscriber_id: str,
    authorization: MoneyAuthorization,
    track: str,
    home: Optional[Path] = None,
    currency: str = "USD",
    approval_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Subscribe to a creator's tier. The charge routes through Cybrus
    (L1) via :mod:`levi.creator.money` — fail-closed: with no rail the
    charge is blocked and the subscription records as ``pending_payment``
    with ``paper=True``. Non-keeper authorization raises MoneyRefused.

    RIGHT mandate (2026-09-22): the charge needs a human approval
    receipt. Without ``approval_id``, :func:`charge` requests the
    approval and raises :class:`MoneyApprovalRequired` carrying the
    resumable id — subscribe again with ``approval_id`` after the human
    approves.

    Period handling: ``expires_at`` = now + tier period. Unsubscribing
    cancels renewal but keeps access until the period ends.
    """
    _guard(track, home)  # L5: the gate fires even with no user text
    tier = get_tier(tier_id, track, home)
    if tier["creator_id"] != creator_id:
        raise SubscriptionError("tier %r does not belong to creator %r" % (tier_id, creator_id))
    if not subscriber_id or not subscriber_id.strip():
        raise SubscriptionError("subscriber_id is required")
    subscriber_id = subscriber_id.strip()

    existing = next(
        (
            s
            for s in _read_all(track, home, "creator_subs")
            if s["creator_id"] == creator_id
            and s["tier_id"] == tier_id
            and s["subscriber_id"] == subscriber_id
            and s["status"] != SUB_CANCELLED
            and _sub_valid(s)
        ),
        None,
    )
    if existing is not None:
        raise SubscriptionError("already subscribed to this tier (sub %s)" % existing["id"])

    # L1: the money moves through Cybrus only. Fail-closed: no rail ->
    # blocked -> recorded as pending_payment, paper=True.
    result = charge(
        amount_minor=tier["price_minor"],
        currency=currency,
        purpose="creator subscription: %s / %s" % (creator_id, tier["name"]),
        identity=subscriber_id,
        authorization=authorization,
        rail="cybrus",
        approval_id=approval_id,
    )
    if result["status"] == "refused":
        raise MoneyRefused("subscription charge refused: %s" % result.get("reason"))
    status = SUB_ACTIVE if result["status"] == "moved" else SUB_PENDING
    now = _utcnow()
    return _write(
        track,
        home,
        "creator_subs",
        {
            "track": track,
            "creator_id": creator_id,
            "tier_id": tier_id,
            "tier_name": tier["name"],
            "tier_rank": tier.get("rank", 0),
            "subscriber_id": subscriber_id,
            "price_minor": tier["price_minor"],
            "currency": currency.upper(),
            "status": status,
            "paper": status == SUB_PENDING,  # honest label: no rail, no money moved
            "charge_plan_id": result["plan_id"],
            "charge_status": result["status"],
            "started_at": now.isoformat(),
            "expires_at": _expires_at(tier["period"], now),
            "cancelled_at": None,
            "created_at": now.isoformat(),
        },
    )


def unsubscribe(
    subscription_id: str,
    subscriber_id: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Cancel a subscription. Owner only. Access continues until the paid
    period ends (``expires_at``); no new period starts."""
    _guard(track, home)
    sub = next(
        (s for s in _read_all(track, home, "creator_subs") if s["id"] == subscription_id),
        None,
    )
    if sub is None:
        raise SubscriptionError("unknown subscription %r" % subscription_id)
    if sub["subscriber_id"] != subscriber_id:
        raise AccessDeniedError("this subscription is not yours")
    if sub["status"] == SUB_CANCELLED:
        return sub
    return _update(
        track,
        home,
        "creator_subs",
        subscription_id,
        {"status": SUB_CANCELLED, "cancelled_at": _utcnow_iso()},
    )


def list_subscriptions(
    subscriber_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The subscriber's own subscriptions on this track."""
    _guard(track, home)
    return [
        s
        for s in _read_all(track, home, "creator_subs")
        if s["subscriber_id"] == subscriber_id
    ]


def list_subscribers(
    creator_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Current (period-valid, not cancelled) subscribers of a creator.
    The creator's own list."""
    _guard(track, home)
    get_profile(creator_id, track, home)
    return [
        s
        for s in _read_all(track, home, "creator_subs")
        if s["creator_id"] == creator_id and _sub_valid(s)
    ]


def access_level(
    subscriber_id: str,
    creator_id: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Server-side entitlement: the subscriber's highest valid tier rank
    for this creator, plus per-item grants from :mod:`levi.creator.content`.

    The token never carries this — it is recomputed on every access (L2).
    """
    _guard(track, home)
    rank: Optional[int] = None
    for sub in _read_all(track, home, "creator_subs"):
        if (
            sub["creator_id"] == creator_id
            and sub["subscriber_id"] == subscriber_id
            and _sub_valid(sub)
        ):
            r = int(sub.get("tier_rank", 0))
            rank = r if rank is None else max(rank, r)
    from levi.creator import content as _content  # lazy: content imports this module

    grants: Set[str] = _content.grants_for(subscriber_id, creator_id, track, home)
    return {"tier_rank": rank, "grants": grants}


# -- Access tokens (Cybrus-issued, server-side verified) -----------------


def _token_scope(track: str, creator_id: str, tier_id: str) -> str:
    return "creator:%s:%s:tier:%s" % (track, creator_id, tier_id)


def issue_access_token(
    subscriber_id: str,
    creator_id: str,
    tier_id: str,
    track: str,
    home: Optional[Path] = None,
    ttl_seconds: int = ACCESS_TOKEN_TTL,
) -> Dict[str, Any]:
    """Issue a short-lived Cybrus access token for a subscriber's tier.

    Requires a currently-valid subscription (L2). The plaintext token is
    returned exactly once; only its SHA-256 lives in the Cybrus token
    store. A server-side binding (token_id -> subscriber) is kept in the
    creator store so verification never trusts the bearer alone.
    """
    _guard(track, home)  # L5
    tier = get_tier(tier_id, track, home)
    if tier["creator_id"] != creator_id:
        raise SubscriptionError("tier %r does not belong to creator %r" % (tier_id, creator_id))
    sub = next(
        (
            s
            for s in _read_all(track, home, "creator_subs")
            if s["creator_id"] == creator_id
            and s["tier_id"] == tier_id
            and s["subscriber_id"] == subscriber_id
            and _sub_valid(s)
        ),
        None,
    )
    if sub is None:
        raise AccessDeniedError("no valid subscription to tier %r" % tier["name"])
    engine = TokenEngine()
    try:
        token_id, token = engine.issue(
            scopes=[_token_scope(track, creator_id, tier_id)],
            ttl_seconds=ttl_seconds,
            kind="api",
            label="creator-access %s/%s" % (creator_id, tier_id),
        )
    except TokenError as exc:
        raise SubscriptionError("token issuance failed: %s" % exc) from exc
    binding = _write(
        track,
        home,
        "creator_tokens",
        {
            "track": track,
            "token_id": token_id,
            "subscriber_id": subscriber_id,
            "creator_id": creator_id,
            "tier_id": tier_id,
            "tier_rank": tier.get("rank", 0),
            "paper": bool(sub.get("paper")),
            "issued_at": _utcnow_iso(),
        },
    )
    return {
        "token_id": token_id,
        "token": token,  # returned EXACTLY ONCE; never stored in plaintext
        "binding_id": binding["id"],
        "scope": _token_scope(track, creator_id, tier_id),
        "expires_in": ttl_seconds,
        "paper": bool(sub.get("paper")),
    }


def revoke_access_token(token_id: str, track: str, home: Optional[Path] = None) -> bool:
    """Revoke a token by id (e.g. on unsubscribe). Returns True if revoked."""
    _guard(track, home)
    engine = TokenEngine()
    try:
        engine.revoke(token_id)
    except TokenError:
        return False
    return True


@cybrus_guarded(service="creator", callee="levi.cybrus")
def verify_access(
    token: str, content_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Verify a bearer token against a content item — L2 enforcement.

    Choke-point wiring (Build 6): this function is the first live
    consumer of the Cybrus router choke point. The
    ``@cybrus_guarded(service="creator", callee="levi.cybrus")`` wrapper
    pops the ``cybrus_*`` kwargs (``cybrus_credential``,
    ``cybrus_api_key``, ``cybrus_gateway``, ``cybrus_payload_ref``) and
    routes the call through :func:`levi.cybrus.enforce.route_service_call`
    — authenticate the creator service, rate-limit, policy-check, audit
    (metadata only) — BEFORE the body below runs. A refused call
    (:class:`NotAuthenticated`, :class:`RateLimitDenied`,
    :class:`CallDenied`) means the token is never even looked at: fail
    closed at the choke point, then fail closed again inside.

    Every access: (1) the token is validated through Cybrus
    (:meth:`TokenEngine.validate` — unknown / revoked / expired all fail);
    (2) the server-side binding is checked; (3) the subscriber's
    subscription is re-checked for current validity (a live token on a
    lapsed subscription grants nothing); (4) the content gate is
    evaluated. Tampered tokens fail at step 1. Raises
    :class:`AccessDeniedError` on any failure; returns the access grant on
    success.
    """
    from levi.creator import content as _content  # lazy: content imports this module

    _guard(track, home)  # L5
    payload = TokenEngine().validate(token)
    if payload is None:
        raise AccessDeniedError("invalid, revoked, or expired access token")
    parts = (payload["scopes"] or [""])[0].split(":")
    if len(parts) != 5 or parts[0] != "creator" or parts[3] != "tier":
        raise AccessDeniedError("token scope is not a creator access scope")
    _, scope_track, creator_id, _, tier_id = parts
    if scope_track != track:
        raise AccessDeniedError("token is for another track")
    binding = next(
        (
            b
            for b in _read_all(track, home, "creator_tokens")
            if b["token_id"] == payload["id"]
        ),
        None,
    )
    if binding is None:
        raise AccessDeniedError("no server-side binding for this token")
    subscriber_id = binding["subscriber_id"]
    level = access_level(subscriber_id, creator_id, track, home)
    if level["tier_rank"] is None and not level["grants"]:
        # Subscription lapsed after the token was issued: the live token
        # grants nothing (L2 — never trust the client/bearer alone).
        raise AccessDeniedError("subscription is no longer valid")
    item = _content.get_item(content_id, track, home)
    if item["creator_id"] != creator_id:
        raise AccessDeniedError("content does not belong to this creator")
    granted, reason = _content.evaluate_gate(
        item,
        creator_id=creator_id,
        subscriber_id=subscriber_id,
        tier_rank=level["tier_rank"],
        track=track,
        home=home,
    )
    if not granted:
        raise AccessDeniedError("content gate denied: %s" % reason)
    return {
        "granted": True,
        "subscriber_id": subscriber_id,
        "creator_id": creator_id,
        "content_id": content_id,
        "reason": reason,
        "paper": bool(binding.get("paper")),
        "token_id": payload["id"],
    }


# -- Payouts (Cybrus only, L1) ------------------------------------------


def _payout_ledger(track: str, home: Optional[Path]) -> List[Dict[str, Any]]:
    return _read_all(track, home, "creator_payouts")


def creator_balance(
    creator_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Unsettled revenue for a creator: per unsettled subscription, the
    12% platform fee (:func:`levi.creator.pricing.platform_fee`) and the
    creator's share. Paper until a rail exists — labeled honestly."""
    _guard(track, home)
    get_profile(creator_id, track, home)
    settled: Set[str] = set()
    for entry in _payout_ledger(track, home):
        if entry["creator_id"] == creator_id:
            settled.update(entry.get("settled_sub_ids", []))
    lines = []
    total_fee = 0
    total_share = 0
    paper = False
    for sub in _read_all(track, home, "creator_subs"):
        if (
            sub["creator_id"] != creator_id
            or sub["id"] in settled
            # Paid-for periods count even after cancellation (the period
            # was bought; cancellation only stops renewal).
            or sub["status"] not in (SUB_ACTIVE, SUB_PENDING, SUB_CANCELLED)
        ):
            continue
        fee = platform_fee(sub["price_minor"])
        share = creator_share(sub["price_minor"])
        total_fee += fee
        total_share += share
        paper = paper or bool(sub.get("paper"))
        lines.append(
            {
                "subscription_id": sub["id"],
                "tier_name": sub.get("tier_name"),
                "price_minor": sub["price_minor"],
                "platform_fee_minor": fee,
                "creator_share_minor": share,
                "paper": bool(sub.get("paper")),
            }
        )
    return {
        "creator_id": creator_id,
        "unsettled_count": len(lines),
        "platform_fee_minor": total_fee,
        "creator_total_minor": total_share,
        "paper": paper,
        "lines": lines,
    }


def record_payout(
    creator_id: str,
    authorization: MoneyAuthorization,
    track: str,
    home: Optional[Path] = None,
    currency: str = "USD",
    cybrus_credential: Optional[str] = None,
    cybrus_api_key: Optional[tuple] = None,
    cybrus_gateway=None,
    approval_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a creator payout through the Cybrus MoneyGateway (L1).

    Choke-point wiring (Build 6): the payout recording crosses the
    Cybrus router choke point via :func:`levi.creator.router.route`
    (service ``"creator"`` -> callee ``"levi.cybrus"``) — authenticated,
    rate-limited, policy-checked, audited — and the returned routing
    ticket is attached to the payout record (``cybrus_ticket``). The
    money itself still moves ONLY through the Cybrus MoneyGateway; the
    choke point adds the routing/audit envelope around it.

    Plans a ``payout`` operation for the creator's unsettled balance,
    binds the keeper's authorization to that exact plan, and executes.
    With no registered rail (the standing state) execution refuses with
    ``NoRailConfigured`` and the payout is recorded as ``pending_payout``
    with the plan id, the gateway's full gate trail, and the receipt —
    full audit, no money moved. No rail is ever auto-registered here, and
    no non-keeper authorization is accepted.

    The payout_reference on the record is the creator's opaque label
    (L4) — audit stays metadata-only (L3).
    """
    _guard(track, home)  # L5: the gate fires on payouts too
    ticket = _router.route(
        "record_payout",
        payload_ref=creator_id,
        credential=cybrus_credential,
        api_key=cybrus_api_key,
        gateway=cybrus_gateway,
    )
    profile = get_profile(creator_id, track, home)
    balance = creator_balance(creator_id, track, home)
    if balance["creator_total_minor"] <= 0:
        raise PayoutError("nothing to pay out for creator %r" % creator_id)

    gw = MoneyGateway()
    purpose = "creator payout: %s (%s)" % (
        profile["handle"], profile["payout_reference"])
    if approval_id is None:
        plan = gw.plan(
            MoneyOperation.PAYOUT,
            balance["creator_total_minor"],
            currency,
            "cybrus",
            purpose,
            creator_id,
        )
        # L11 forward-motion: the payout needs a human approval receipt.
        entry = gw.request_execution_approval(plan, subject=creator_id)
        raise MoneyApprovalRequired(
            entry["id"],
            f"creator payout needs human approval: approve {entry['id'][:8]} "
            f"(levi cybrus approve {entry['id'][:8]}) then retry "
            f"record_payout() with approval_id={entry['id'][:8]}",
        )
    # Resumed after human approval: rebuild the EXACT plan the approval
    # was minted for — never a fresh plan (rebinding is refused).
    plan = gw.plan_from_approval(
        approval_id, expected_operation=MoneyOperation.PAYOUT.value
    )
    if (
        plan.amount_minor != balance["creator_total_minor"]
        or plan.currency != currency.upper()
        or plan.rail != "cybrus"
        or plan.purpose != purpose
        or plan.identity != creator_id
    ):
        raise MoneyRefused(
            "approval does not match this payout: request a fresh approval"
        )
    bound = replace(
        authorization, plan_id=plan.plan_id, approval_id=approval_id
    )
    try:
        gw.execute(plan, bound)
    except NotAuthorized as exc:
        raise MoneyRefused("payout authorization refused: %s" % exc) from exc
    except NoRailConfigured as exc:
        # Standing honest state: no rail -> nothing moves. Record the
        # payout as a gateway operation with the full audit trail.
        entry = _write(
            track,
            home,
            "creator_payouts",
            {
                "track": track,
                "creator_id": creator_id,
                "payout_reference": profile["payout_reference"],  # opaque label (L4)
                "operation": MoneyOperation.PAYOUT.value,
                "amount_minor": balance["creator_total_minor"],
                "platform_fee_minor": balance["platform_fee_minor"],
                "currency": currency.upper(),
                "status": "pending_payout",
                "paper": True,
                "plan_id": plan.plan_id,
                "cybrus_ticket": ticket["ticket"],  # choke-point routing ticket
                "settled_sub_ids": [l["subscription_id"] for l in balance["lines"]],
                "receipt": gw.receipt(plan.plan_id),
                "preview": gw.preview(plan),
                "reason": str(exc),
                "created_at": _utcnow_iso(),
            },
        )
        return entry
    # A real rail moved money: record the moved payout with the receipt.
    return _write(
        track,
        home,
        "creator_payouts",
        {
            "track": track,
            "creator_id": creator_id,
            "payout_reference": profile["payout_reference"],
            "operation": MoneyOperation.PAYOUT.value,
            "amount_minor": balance["creator_total_minor"],
            "platform_fee_minor": balance["platform_fee_minor"],
            "currency": currency.upper(),
            "status": "moved",
            "paper": False,
            "plan_id": plan.plan_id,
            "cybrus_ticket": ticket["ticket"],  # choke-point routing ticket
            "settled_sub_ids": [l["subscription_id"] for l in balance["lines"]],
            "receipt": gw.receipt(plan.plan_id),
            "created_at": _utcnow_iso(),
        },
    )


def list_payouts(
    creator_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The creator's payout records (the portable ledger). Gate applies."""
    _guard(track, home)
    get_profile(creator_id, track, home)
    return [
        p
        for p in _payout_ledger(track, home)
        if p["creator_id"] == creator_id
    ]
