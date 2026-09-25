"""Tier-based rate limits for the broker's automated retrieval (anti-spam).

Chauncey's standing requirement (2026-09-21): the broker's automated
retrieval — account creation, API-key fetching, OAuth flows — must be
quota-gated by tier so other users can't wield it as a spam cannon.

How it works:
  - The broker calls :func:`check` BEFORE each automated retrieval, right
    after the human-approval gate passes (so quota is only consumed by
    actions that actually proceed — approval-pending first attempts never
    reach the check).
  - Sliding-window counters per user: per-hour AND per-day quotas.
  - Burst detection: >10 retrievals in 5 minutes -> 15-minute cooldown +
    audit flag.
  - One in-flight OAuth flow per user (acquired after approval, released
    on complete/abandon). Slots carry a 24h TTL: a stale (abandoned)
    slot is reclaimed by the same user's next check/acquire, audit-logged
    as ``ratelimit.inflight_reclaimed``, and the denial names the retry
    time — no silent forever-block.
  - Every attempt — allowed AND denied — is written to the tamper-evident
    audit log. Denials carry a clean message with the reset time.
  - Chauncey (``FOUNDER_IDENTITIES`` — "I'm Cybrus") is exempt from
    quotas/burst/in-flight, but his attempts are still audit-logged.

Tier ladder (PROVISIONAL — Chauncey's to change; prices are placeholders
he sets, never this module):
  - FREE: vault + password generation only. ZERO automated retrieval.
  - STARTER ($6/mo provisional): 20 retrievals/day, 5 account creations/day.
  - PRO ($18/mo provisional): 200 retrievals/day, 50 account creations/day.
  - PLATFORM (custom): uncapped, still audited.

``SERVICE_CALL`` (the enforce choke point's action — every internal
service call and every egress request) has its own caps: FREE 0/0,
STARTER 100/hr + 1000/day, PRO 1000/hr + 10000/day, PLATFORM uncapped.
Free-tier services cannot cross the choke point at all.

Tier lookup is a stub: :func:`get_tier` reads a local ``tiers.json`` map
(default ``free``). SEAM: replace ``get_tier`` with the real billing-system
lookup when entitlements land — the broker never calls anything else.

stdlib-only. No secrets in logs: audit details carry action/tier/counts,
never key material.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

ACCOUNT_CREATE = "account_create"
API_KEY_FETCH = "api_key_fetch"
OAUTH_INITIATE = "oauth_initiate"
OAUTH_REFRESH = "oauth_refresh"
#: Choke-point action: every internal service call and every external
#: egress request that crosses ``levi.cybrus.enforce`` consumes quota
#: here, so no service can wield Cybrus as an uncapped call cannon.
SERVICE_CALL = "service_call"

ACTIONS = (ACCOUNT_CREATE, API_KEY_FETCH, OAUTH_INITIATE, OAUTH_REFRESH, SERVICE_CALL)

#: Actions counted as "retrievals" for burst detection.
RETRIEVAL_ACTIONS = (API_KEY_FETCH, OAUTH_INITIATE)

HOUR = 3600
DAY = 86400
BURST_WINDOW = 300  # 5 minutes
BURST_THRESHOLD = 10  # >10 retrievals in the burst window -> cooldown
COOLDOWN_SECONDS = 900  # 15 minutes

#: In-flight OAuth slots older than this are dead (crashed client, no
#: cleanup): the next check/acquire by the SAME user reclaims the slot,
#: audit-logged, and the denial carries a concrete retry reset. Live
#: slots still block with reset = slot start + TTL. Reclaim is per-user
#: only — a user can never touch another user's slot, so there is no
#: collision/hijack path. 24h is generous for a human-driven flow.
OAUTH_FLOW_TTL_SECONDS = 24 * 3600

# (per_hour, per_day) caps; None = uncapped (platform tier, still audited).
# Prices are PROVISIONAL placeholders for Chauncey to set.
TIERS: Dict[str, Dict[str, Optional[Tuple[int, int]]]] = {
    "free": {
        ACCOUNT_CREATE: (0, 0),
        API_KEY_FETCH: (0, 0),
        OAUTH_INITIATE: (0, 0),
        OAUTH_REFRESH: (0, 0),
        # Service calls need at least Starter — free tier is vault +
        # password generation only (the standing anti-spam doctrine).
        SERVICE_CALL: (0, 0),
    },
    "starter": {  # $6/mo provisional
        ACCOUNT_CREATE: (2, 5),
        API_KEY_FETCH: (10, 20),
        OAUTH_INITIATE: (5, 20),
        OAUTH_REFRESH: (50, 200),
        SERVICE_CALL: (100, 1000),
    },
    "pro": {  # $18/mo provisional
        ACCOUNT_CREATE: (10, 50),
        API_KEY_FETCH: (50, 200),
        OAUTH_INITIATE: (20, 200),
        OAUTH_REFRESH: (200, 2000),
        SERVICE_CALL: (1000, 10000),
    },
    "platform": {  # custom — uncapped, still audited
        ACCOUNT_CREATE: None,
        API_KEY_FETCH: None,
        OAUTH_INITIATE: None,
        OAUTH_REFRESH: None,
        SERVICE_CALL: None,
    },
}

TIER_PRICES_PROVISIONAL = {
    "free": "$0",
    "starter": "$6/mo (provisional — Chauncey's call)",
    "pro": "$18/mo (provisional — Chauncey's call)",
    "platform": "custom (provisional — Chauncey's call)",
}

DEFAULT_TIER = "free"


class RateLimitDenied(Exception):
    """A broker retrieval was denied by tier policy.

    ``reset_at`` is epoch seconds when the caller may retry, or None when
    there is no automatic reset (free tier). In-flight denials always
    carry a reset: slot start + TTL for a live flow, or "now" when a
    stale slot was reclaimed on this attempt.
    """

    def __init__(
        self,
        message: str,
        action: str,
        tier: str,
        reset_at: Optional[float] = None,
    ):
        super().__init__(message)
        self.action = action
        self.tier = tier
        self.reset_at = reset_at

    @property
    def reset_iso(self) -> Optional[str]:
        if self.reset_at is None:
            return None
        return datetime.fromtimestamp(self.reset_at, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Storage + audit plumbing
# ---------------------------------------------------------------------------

_RATE_LIMITS_STORE = "rate_limits"
_TIERS_STORE = "tiers"


def _paths():
    from levi.cybrus import _paths as p

    return p


def _load_state() -> Dict:
    p = _paths()
    data = p.load_json_store(p.store_path(_RATE_LIMITS_STORE))
    if not isinstance(data, dict):
        data = {}
    data.setdefault("events", [])
    data.setdefault("cooldowns", {})
    data.setdefault("inflight", {})
    return data


def _save_state_unlocked(path, state: Dict) -> None:
    """Persist ``state`` WITHOUT taking the store lock.

    Locking rule: the caller must already hold ``store_lock(path)``.
    ``fcntl.flock`` is non-reentrant — taking the same store's lock twice
    in one process self-deadlocks. All callers are the locked sections of
    :func:`check`, :func:`acquire_flow`, and :func:`release_flow`.
    """
    from levi.cybrus import _paths as p

    p.save_json_store(path, state)


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> None:
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(actor), dict(details or {}))


def _is_admin(user_id: str) -> bool:
    """Chauncey ("I'm Cybrus") is exempt from quotas — still audit-logged."""
    from levi.cybrus.identity import is_founder_identity

    return is_founder_identity(user_id)


# ---------------------------------------------------------------------------
# Tier lookup (STUB — seam for the real billing hookup)
# ---------------------------------------------------------------------------


def get_tier(user_id: str) -> str:
    """Return the tier for ``user_id``. Default ``free``.

    SEAM: this is the stub. When entitlements land, replace this body with
    the billing-system lookup — the broker calls nothing else for tiers.
    """
    p = _paths()
    data = p.load_json_store(p.store_path(_TIERS_STORE))
    tiers = data.get("tiers") if isinstance(data, dict) else None
    tier = tiers.get(str(user_id)) if isinstance(tiers, dict) else None
    if tier in TIERS:
        return tier
    return DEFAULT_TIER


def set_tier(user_id: str, tier: str) -> str:
    """Assign a tier (admin/testing path — not customer-facing)."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {sorted(TIERS)}")
    p = _paths()
    path = p.store_path(_TIERS_STORE)
    with p.store_lock(path):
        data = p.load_json_store(path)
        if not isinstance(data, dict):
            data = {}
        tiers = data.get("tiers")
        if not isinstance(tiers, dict):
            tiers = {}
        tiers[str(user_id)] = tier
        data["tiers"] = tiers
        p.save_json_store(path, data)
    _audit("ratelimit.tier_set", user_id, {"tier": tier})
    return tier


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


def _prune(events: List[Dict], now: float) -> List[Dict]:
    return [e for e in events if now - float(e["ts"]) < DAY]


def _count(events: List[Dict], user_id: str, action: str, window: float, now: float) -> int:
    return sum(
        1
        for e in events
        if e["user"] == user_id and e["action"] == action and now - float(e["ts"]) < window
    )


def _oldest_in_window(
    events: List[Dict], user_id: str, action: str, window: float, now: float
) -> Optional[float]:
    stamps = [
        float(e["ts"])
        for e in events
        if e["user"] == user_id and e["action"] == action and now - float(e["ts"]) < window
    ]
    return min(stamps) if stamps else None


def check(user_id: str, action: str) -> Dict:
    """Enforce tier policy for one automated-retrieval attempt.

    Call BEFORE the retrieval, after the human-approval gate passes.
    Verifies quota + burst + cooldown + in-flight, records the attempt,
    and audit-logs it. Returns a summary dict on success; raises
    :class:`RateLimitDenied` with a clean message + reset time on denial.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown rate-limit action {action!r}")
    user_id = str(user_id)
    now = time.time()
    p = _paths()
    path = p.store_path(_RATE_LIMITS_STORE)

    if _is_admin(user_id):
        _audit(
            "ratelimit.bypass",
            user_id,
            {"action": action, "reason": "founder exempt (still logged)"},
        )
        return {"allowed": True, "tier": "admin", "action": action}

    tier = get_tier(user_id)

    with p.store_lock(path):
        state = _load_state()
        events = _prune(state["events"], now)
        state["events"] = events

        def deny(message: str, reset_at: Optional[float], kind: str) -> None:
            _audit(
                "ratelimit.denied",
                user_id,
                {"action": action, "tier": tier, "kind": kind},
            )
            _save_state_unlocked(path, state)
            raise RateLimitDenied(message, action, tier, reset_at)

        # 1. active cooldown (burst or manual)
        cooldown_until = float(state["cooldowns"].get(user_id, 0))
        if now < cooldown_until:
            deny(
                f"burst cooldown active for {action}: too many retrievals in "
                f"5 minutes. Retry after "
                f"{datetime.fromtimestamp(cooldown_until, tz=timezone.utc).isoformat()}",
                cooldown_until,
                "cooldown",
            )

        # 2. burst detection across retrieval actions
        burst_count = sum(
            1
            for e in events
            if e["user"] == user_id
            and e["action"] in RETRIEVAL_ACTIONS
            and now - float(e["ts"]) < BURST_WINDOW
        )
        if burst_count >= BURST_THRESHOLD:
            until = now + COOLDOWN_SECONDS
            state["cooldowns"][user_id] = until
            _audit(
                "ratelimit.burst",
                user_id,
                {
                    "action": action,
                    "tier": tier,
                    "retrievals_in_5m": burst_count,
                    "cooldown_until": datetime.fromtimestamp(
                        until, tz=timezone.utc
                    ).isoformat(),
                },
            )
            deny(
                f"burst detected: {burst_count} retrievals in 5 minutes. "
                f"Cooling down for 15 minutes — retry after "
                f"{datetime.fromtimestamp(until, tz=timezone.utc).isoformat()}",
                until,
                "burst",
            )

        # 3. tier quota (free tier: every cap is 0 -> clean denial)
        caps = TIERS[tier][action]
        if caps is None:
            allowed_detail = {"tier": tier, "quota": "uncapped"}
        else:
            per_hour, per_day = caps
            if per_hour == 0 and per_day == 0:
                deny(
                    f"free tier covers the vault + password generation only — "
                    f"automated retrieval ({action}) needs Starter or higher. "
                    f"Pricing is Chauncey's call; ask him.",
                    None,
                    "free_tier",
                )
            for window, cap, label in ((HOUR, per_hour, "hour"), (DAY, per_day, "day")):
                used = _count(events, user_id, action, window, now)
                if used >= cap:
                    oldest = _oldest_in_window(events, user_id, action, window, now)
                    reset_at = (oldest + window) if oldest else (now + window)
                    deny(
                        f"tier {tier!r} quota exceeded for {action}: "
                        f"{cap} per {label} (used {used}). Resets at "
                        f"{datetime.fromtimestamp(reset_at, tz=timezone.utc).isoformat()}",
                        reset_at,
                        f"quota_{label}",
                    )
            allowed_detail = {"tier": tier, "quota": f"{per_hour}/hr, {per_day}/day"}

        # 4. one in-flight OAuth flow per user (initiate only).
        #    A stale slot (older than the TTL — crashed client, no cleanup)
        #    is reclaimed here by the SAME user only: removed, audit-logged,
        #    and the denial carries a concrete reset (retry now) instead of
        #    blocking forever with reset_at=None. Fail-closed: the attempt
        #    still denies this once; the next attempt proceeds.
        if action == OAUTH_INITIATE:
            slot = state["inflight"].get(user_id)
            if slot:
                since = float(slot.get("since", 0) or 0)
                if now - since >= OAUTH_FLOW_TTL_SECONDS:
                    state["inflight"].pop(user_id, None)
                    _audit(
                        "ratelimit.inflight_reclaimed",
                        user_id,
                        {
                            "since_iso": slot.get("since_iso"),
                            "stale_days": round((now - since) / DAY, 1),
                            "ttl_seconds": OAUTH_FLOW_TTL_SECONDS,
                            "via": "check",
                        },
                    )
                    deny(
                        "stale in-flight OAuth flow reclaimed (abandoned "
                        f"{(now - since) / DAY:.1f} days ago): retry now to "
                        "start a fresh flow",
                        now,
                        "inflight_stale",
                    )
                deny(
                    "one in-flight OAuth flow per user: complete or abandon the "
                    "current flow before starting another",
                    since + OAUTH_FLOW_TTL_SECONDS,
                    "inflight",
                )

        # allowed: record + audit
        events.append({"user": user_id, "action": action, "ts": now})
        state["events"] = events
        _save_state_unlocked(path, state)

    _audit(
        "ratelimit.allowed",
        user_id,
        {"action": action, **allowed_detail},
    )
    return {"allowed": True, "action": action, **allowed_detail}


def acquire_flow(user_id: str) -> None:
    """Mark one in-flight OAuth flow for ``user_id`` (call after approval).

    Stale-slot semantics match :func:`check`: a dead slot belonging to
    this same user is reclaimed (audit-logged) and the call denies once
    with a retry-now reset; the next call acquires cleanly. A live slot
    still denies with reset = slot start + TTL.
    """
    user_id = str(user_id)
    if _is_admin(user_id):
        return
    now = time.time()
    p = _paths()
    path = p.store_path(_RATE_LIMITS_STORE)
    with p.store_lock(path):
        state = _load_state()
        slot = state["inflight"].get(user_id)
        if slot:
            since = float(slot.get("since", 0) or 0)
            if now - since >= OAUTH_FLOW_TTL_SECONDS:
                state["inflight"].pop(user_id, None)
                _audit(
                    "ratelimit.inflight_reclaimed",
                    user_id,
                    {
                        "since_iso": slot.get("since_iso"),
                        "stale_days": round((now - since) / DAY, 1),
                        "ttl_seconds": OAUTH_FLOW_TTL_SECONDS,
                        "via": "acquire_flow",
                    },
                )
                _save_state_unlocked(path, state)
                raise RateLimitDenied(
                    "stale in-flight OAuth flow reclaimed (abandoned "
                    f"{(now - since) / DAY:.1f} days ago): retry now to "
                    "start a fresh flow",
                    OAUTH_INITIATE,
                    get_tier(user_id),
                    now,
                )
            raise RateLimitDenied(
                "one in-flight OAuth flow per user: complete or abandon the "
                "current flow before starting another",
                OAUTH_INITIATE,
                get_tier(user_id),
                since + OAUTH_FLOW_TTL_SECONDS,
            )
        state["inflight"][user_id] = {
            "since": time.time(),
            "since_iso": datetime.now(timezone.utc).isoformat(),
        }
        _save_state_unlocked(path, state)


def release_flow(user_id: str) -> None:
    """Release ``user_id``'s in-flight OAuth flow slot (complete/abandon).

    This is the user's manual reset path: it only ever removes the
    caller's OWN slot (per-user key) and the removal is audit-logged —
    every slot change goes through the audit path.
    """
    user_id = str(user_id)
    p = _paths()
    path = p.store_path(_RATE_LIMITS_STORE)
    with p.store_lock(path):
        state = _load_state()
        removed = state["inflight"].pop(user_id, None)
        _save_state_unlocked(path, state)
    if removed is not None:
        _audit(
            "ratelimit.inflight_released",
            user_id,
            {"since_iso": removed.get("since_iso")},
        )


def usage(user_id: str) -> Dict:
    """Current tier + window usage for ``user_id`` (status displays)."""
    user_id = str(user_id)
    now = time.time()
    tier = get_tier(user_id)
    state = _load_state()
    events = _prune(state["events"], now)
    per_action = {}
    for action in ACTIONS:
        caps = TIERS[tier][action]
        per_action[action] = {
            "used_hour": _count(events, user_id, action, HOUR, now),
            "used_day": _count(events, user_id, action, DAY, now),
            "cap": (
                "uncapped" if caps is None else {"per_hour": caps[0], "per_day": caps[1]}
            ),
        }
    cooldown_until = float(state["cooldowns"].get(user_id, 0))
    return {
        "user": user_id,
        "tier": tier,
        "admin_bypass": _is_admin(user_id),
        "cooldown_until": (
            datetime.fromtimestamp(cooldown_until, tz=timezone.utc).isoformat()
            if now < cooldown_until
            else None
        ),
        "inflight_oauth": bool(state["inflight"].get(user_id)),
        "actions": per_action,
    }


def policy_summary() -> str:
    """Human-readable policy (CLI + docs)."""
    lines = [
        "Cybrus broker rate limits (anti-spam, tier-based):",
        "",
    ]
    for tier in ("free", "starter", "pro", "platform"):
        lines.append(f"  {tier.upper():8} {TIER_PRICES_PROVISIONAL[tier]}")
        for action in ACTIONS:
            caps = TIERS[tier][action]
            cap_str = "uncapped" if caps is None else f"{caps[0]}/hr, {caps[1]}/day"
            lines.append(f"    - {action:15} {cap_str}")
    lines += [
        "",
        f"Burst rule: >{BURST_THRESHOLD} retrievals in 5 minutes -> "
        f"{COOLDOWN_SECONDS // 60}-minute cooldown + audit flag.",
        "In-flight: one OAuth flow per user at a time.",
        "Free tier: vault + password generation only, zero automated retrieval.",
        "Chauncey (founder) is exempt from quotas; every attempt is audit-logged.",
        "Tier prices are PROVISIONAL — Chauncey's call.",
    ]
    return "\n".join(lines)
