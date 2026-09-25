"""Creator service x Cybrus choke-point integration (Build 6).

The creator service is the first live consumer of the Cybrus router
choke point (Build 1): every subscription-token verification
(``verify_access``) and every payout recording (``record_payout``) crosses
``levi.cybrus.enforce`` — authenticated, rate-limited, policy-checked,
audit-logged (metadata only).

These are the PROOF gate for the wiring: invariant tests asserting the
conjunction of the creator laws (L1-L5, subscriptions.py) and the
choke-point laws (L1-L12, enforce.py). Honestly named: machine-checked
invariants, not formal proof.

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME
writes, no network.
"""

from __future__ import annotations

import pytest

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import content as creator_content
from levi.creator import router as creator_router
from levi.creator import subscriptions as subs
from levi.creator.money import MoneyApprovalRequired, MoneyAuthorization
from levi.cybrus import rate_limits as rl
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.enforce import CallDenied, NotAuthenticated
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.rate_limits import RateLimitDenied
from levi.cybrus.tokens import TokenEngine
from levi.plaiground.gate import GateLockedError


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


@pytest.fixture
def keeper():
    return MoneyAuthorization(authorized_by="chauncey", plan_id="", operation="charge")


@pytest.fixture
def cybrus(iso):
    """Provision the choke point for the creator service: the additive
    seed-policy allow rules, a starter tier, and a service token with the
    service.call scope."""
    creator_router.ensure_creator_routing()
    rl.set_tier(creator_router.CREATOR_CALLER, "starter")
    _, token = TokenEngine().issue(
        scopes=["service.call"],
        ttl_seconds=3600,
        kind="api",
        label="creator service token",
    )
    return {"cybrus_credential": token}


def _with_approval(fn, *args, **kwargs):
    """RIGHT approval dance: approve as Chauncey, retry with approval_id."""
    try:
        return fn(*args, **kwargs)
    except MoneyApprovalRequired as exc:
        ApprovalEngine().approve(exc.approval_id, by="chauncey")
        return fn(*args, approval_id=exc.approval_id, **kwargs)


def _creator(home):
    return subs.create_profile(
        "creator1", "Creator One", "A creator bio", "bank-ref-8472", TRACK_AI, home
    )


def _flow(home, keeper):
    """A subscribed fan with a live token and a tier-gated item."""
    p = _creator(home)
    t = subs.add_tier(p["id"], "monthly", 400, "month", TRACK_AI, home=home)
    _with_approval(subs.subscribe, p["id"], t["id"], "fan1", keeper, TRACK_AI, home)
    item = creator_content.publish(
        p["id"], "Episode 1", "The first episode", "post", TRACK_AI,
        home=home, tier_id=t["id"],
    )
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    return p, item, issued


def _cybrus_audit(event):
    return [r for r in AuditEngine().tail(500) if r["event"] == event]


# ---------------------------------------------------------------------------
# Choke-point refusals: the body never runs when the crossing is refused
# ---------------------------------------------------------------------------


def test_unauthenticated_gate_check_refused(home, iso, keeper):
    # No service credential: the choke point refuses before the token is
    # even looked at (fail closed). The refusal names its remedy (L6).
    _p, item, issued = _flow(home, keeper)
    with pytest.raises(NotAuthenticated) as excinfo:
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home)
    assert "credential" in str(excinfo.value).lower()
    refused = _cybrus_audit("call.refused")
    assert refused and refused[-1]["details"]["stage"] == "auth"


def test_garbage_credential_refused(home, iso, keeper):
    _p, item, issued = _flow(home, keeper)
    with pytest.raises(NotAuthenticated):
        subs.verify_access(
            issued["token"], item["id"], TRACK_AI, home,
            cybrus_credential="bogus",
        )


def test_over_rate_limit_refused(home, iso, keeper, cybrus):
    # Free-tier callers cannot cross the choke point at all (0/0 quota).
    rl.set_tier(creator_router.CREATOR_CALLER, "free")
    _p, item, issued = _flow(home, keeper)
    with pytest.raises(RateLimitDenied):
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)


def test_policy_deny_wins_over_valid_credential(home, iso, keeper, cybrus):
    # Deny always wins (L3): a deny rule beats the allow + the credential.
    PolicyEngine().add_rule(
        creator_router.CREATOR_CALLER,
        "service.levi.cybrus",
        creator_router.ACTION_VERIFY_ACCESS,
        "deny",
        "critical",
    )
    _p, item, issued = _flow(home, keeper)
    with pytest.raises(CallDenied):
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)
    refused = _cybrus_audit("call.refused")
    assert refused and refused[-1]["details"]["stage"] == "policy"


# ---------------------------------------------------------------------------
# Crossings: audit records, metadata only
# ---------------------------------------------------------------------------


def test_token_verification_writes_audit_record(home, iso, keeper, cybrus):
    _p, item, issued = _flow(home, keeper)
    grant = subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)
    assert grant["granted"] is True
    routed = _cybrus_audit("call.routed")
    assert routed
    details = routed[-1]["details"]
    assert details["action"] == "verify_access"
    assert details["callee"] == "levi.cybrus"
    # L4 (both modules): metadata only. The subscriber's bearer token and
    # the service credential never enter the audit record.
    blob = str(details)
    assert issued["token"] not in blob
    assert cybrus["cybrus_credential"] not in blob


def test_payout_recording_crosses_choke_point(home, iso, keeper, cybrus):
    p, _item, _issued = _flow(home, keeper)
    entry = _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)
    assert entry["cybrus_ticket"]  # the routing ticket rides the record
    routed = _cybrus_audit("call.routed")
    payout_calls = [r for r in routed if r["details"].get("action") == "record_payout"]
    assert payout_calls
    assert payout_calls[-1]["details"]["payload_ref"] == p["id"]
    # The audit record carries no payout account data (L3/L4).
    assert "bank-ref-8472" not in str(payout_calls[-1]["details"])


def test_payout_still_settles_via_money_gateway(home, iso, keeper, cybrus):
    # L1: the money path is unchanged — the charge/payout still moves only
    # through the Cybrus MoneyGateway; the choke point only adds the
    # routing/audit envelope.
    from levi.cybrus.money import MoneyGateway

    p, _item, _issued = _flow(home, keeper)
    entry = _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)
    assert entry["status"] == "pending_payout"  # no rail: honest paper
    assert entry["plan_id"].startswith("mpl_")
    assert entry["receipt"]["law"] == "Cybrus alone handles money."
    gw = MoneyGateway()
    plan_events = [
        e["event"]
        for e in gw.audit_log(limit=50)
        if e.get("plan_id") == entry["plan_id"]
    ]
    assert "planned" in plan_events
    assert "execute_refused" in plan_events


# ---------------------------------------------------------------------------
# The seed-policy addition: additive only, idempotent
# ---------------------------------------------------------------------------


def test_seed_policy_addition_is_idempotent(home, iso):
    first = creator_router.ensure_creator_routing()
    assert len(first) == len(creator_router.CREATOR_POLICY_RULES)
    assert creator_router.ensure_creator_routing() == []  # no duplicates


def test_seed_policy_addition_touches_nothing_else(home, iso):
    before = PolicyEngine().list_rules()
    creator_router.ensure_creator_routing()
    after = PolicyEngine().list_rules()
    # Additive only: every pre-existing rule is still present, untouched,
    # in order (no-cancellation, L9).
    assert after[: len(before)] == before


# ---------------------------------------------------------------------------
# Law conjunction: creator L1-L5 x choke-point L1-L12, at the wiring
# ---------------------------------------------------------------------------


def test_law_conjunction_at_the_wiring(home, iso, keeper, cybrus):
    p, item, issued = _flow(home, keeper)

    # L2 (creator): even with a VALID service credential crossing the
    # choke point, a tampered subscriber token still fails closed inside.
    bad = issued["token"][:-2] + ("AA" if not issued["token"].endswith("AA") else "BB")
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(bad, item["id"], TRACK_AI, home, **cybrus)

    # L1 (creator): payout money moves only via the gateway, with the
    # choke-point ticket attached.
    entry = _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)
    assert entry["plan_id"].startswith("mpl_")
    assert entry["cybrus_ticket"]

    # L4 (creator): the opaque payout reference is still enforced at
    # write time, behind the choke point.
    with pytest.raises(subs.SubscriptionError):
        subs.create_profile("c2", "C Two", "bio", "api-key-SECRET-1", TRACK_AI, home)

    # L5 (creator): the SI safety gate still fires fail-closed — here the
    # choke point passes (valid credential) and the gate refuses inside.
    with pytest.raises(GateLockedError):
        subs.verify_access(issued["token"], item["id"], TRACK_SI, home, **cybrus)

    # L4 (choke point): no audit record anywhere carries the subscriber
    # bearer token or the service credential.
    for event in ("call.routed", "call.refused"):
        for record in _cybrus_audit(event):
            blob = str(record["details"])
            assert issued["token"] not in blob
            assert cybrus["cybrus_credential"] not in blob
