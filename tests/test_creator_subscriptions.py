"""Tests for the creator subscription service (L1-L5 invariant tests).

Not formal proof: each test asserts one invariant from the module's laws
(all money via Cybrus, server-side token verification, metadata-only
audit, opaque payout references, unbypassable safety gates).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import levi.cybrus.tokens as cybrus_tokens
from levi.creator import TRACK_AI, TRACK_SI
from levi.creator import content as creator_content
from levi.creator import subscriptions as subs
from levi.creator.money import MoneyApprovalRequired, MoneyAuthorization, MoneyRefused
from levi.creator.store import ai_read_all, ai_update, si_read_all
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.money import MoneyGateway
from levi.plaiground.gate import (
    CONFIRMATION_PHRASE,
    GateLockedError,
    enable_adult_mode,
    set_pin,
)


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def iso(tmp_path, monkeypatch):
    """Isolated stores: creator home, Cybrus tokens, Cybrus money."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


@pytest.fixture
def keeper():
    return MoneyAuthorization(authorized_by="chauncey", plan_id="", operation="charge")


@pytest.fixture
def mallory():
    return MoneyAuthorization(authorized_by="mallory", plan_id="", operation="charge")


@pytest.fixture
def cybrus(iso):
    """Provision the Cybrus choke point for the creator service: the
    additive seed-policy allow rules (levi.creator.router), a starter
    rate-limit tier for the ``creator`` caller, and a service token
    carrying the ``service.call`` scope. Returns the kwargs the guarded
    calls expect (``cybrus_credential=...``)."""
    from levi.creator import router as creator_router
    from levi.cybrus import rate_limits as rl
    from levi.cybrus.tokens import TokenEngine

    creator_router.ensure_creator_routing()
    rl.set_tier(creator_router.CREATOR_CALLER, "starter")
    _, token = TokenEngine().issue(
        scopes=["service.call"],
        # Long TTL: test_expired_token_rejected time-travels past the
        # *subscriber* token's TTL; the service credential must survive
        # that travel so the choke point still authenticates.
        ttl_seconds=86400,
        kind="api",
        label="creator service token",
    )
    return {"cybrus_credential": token}


def _enable(home):
    set_pin("test-pin-1234", home=home)
    return enable_adult_mode(CONFIRMATION_PHRASE, "test-pin-1234", home=home)


def _creator(track=TRACK_AI, home=None):
    return subs.create_profile(
        "creator1", "Creator One", "A creator bio", "bank-ref-8472", track, home
    )


def _tier(creator_id, name="monthly", price=400, period="month", track=TRACK_AI, home=None, rank=None):
    return subs.add_tier(creator_id, name, price, period, track, rank=rank, home=home)


def _sub(creator_id, tier_id, auth, sub="fan1", track=TRACK_AI, home=None):
    return _with_approval(
        subs.subscribe, creator_id, tier_id, sub, auth, track, home
    )


def _with_approval(fn, *args, **kwargs):
    """RIGHT approval dance for money-moving test calls.

    Run ``fn``; when it raises :class:`MoneyApprovalRequired`, approve
    the pending request as Chauncey (the test human) and retry with the
    issued ``approval_id``. Non-keeper auth still refuses on retry —
    the approval never launders a bad identity.
    """
    try:
        return fn(*args, **kwargs)
    except MoneyApprovalRequired as exc:
        ApprovalEngine().approve(exc.approval_id, by="chauncey")
        return fn(*args, approval_id=exc.approval_id, **kwargs)


# -- Profiles & tiers ---------------------------------------------------


def test_ai_create_profile_and_tiers(home, iso):
    p = _creator(home=home)
    assert p["payout_reference"] == "bank-ref-8472"
    t = _tier(p["id"], home=home)
    assert t["price_minor"] == 400 and t["period"] == "month"
    assert subs.list_tiers(p["id"], TRACK_AI, home)[0]["id"] == t["id"]


def test_duplicate_handle_rejected(home, iso):
    _creator(home=home)
    with pytest.raises(subs.SubscriptionError):
        _creator(home=home)


def test_payout_reference_must_not_be_a_secret(home, iso):
    # L4: secret-looking payout references are rejected at write time.
    with pytest.raises(subs.SubscriptionError):
        subs.create_profile("c2", "C Two", "bio", "api-key-SECRET-123", TRACK_AI, home)
    with pytest.raises(subs.SubscriptionError):
        subs.create_profile("c3", "C Three", "bio", "my password is hunter2", TRACK_AI, home)


def test_tier_suggestions_come_from_pricing(home, iso):
    sug = subs.creator_tier_suggestions()
    assert [s["price_minor"] for s in sug] == [100, 400, 2000]
    assert [s["name"] for s in sug] == ["taste", "monthly", "patron"]
    assert [s["rank"] for s in sug] == [0, 1, 2]


def test_bad_track_rejected(home, iso):
    with pytest.raises(subs.SubscriptionError):
        subs.create_profile("c", "C", "bio", "ref-1", "nope", home)


# -- Subscribe / unsubscribe lifecycle ----------------------------------


def test_subscribe_records_pending_payment_paper(home, iso, keeper):
    # No rail registered: the charge is blocked, the subscription records
    # as pending_payment with paper=True — honest about no money moving.
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    s = _sub(p["id"], t["id"], keeper, home=home)
    assert s["status"] == "pending_payment"
    assert s["paper"] is True
    assert s["charge_plan_id"].startswith("mpl_")
    assert s["charge_status"] == "blocked"
    expires = datetime.fromisoformat(s["expires_at"])
    assert expires > datetime.now(timezone.utc) + timedelta(days=29)


def test_subscribe_refused_without_keeper_auth(home, iso, mallory):
    # L1: non-keeper authorization refuses before any rail is consulted,
    # and no subscription is recorded.
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    with pytest.raises(MoneyRefused):
        _sub(p["id"], t["id"], mallory, home=home)
    assert ai_read_all(home, "creator_subs") == []


def test_duplicate_active_subscription_rejected(home, iso, keeper):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    with pytest.raises(subs.SubscriptionError):
        _sub(p["id"], t["id"], keeper, home=home)


def test_unsubscribe_keeps_period_then_lapses(home, iso, keeper):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    s = _sub(p["id"], t["id"], keeper, home=home)
    out = subs.unsubscribe(s["id"], "fan1", TRACK_AI, home)
    assert out["status"] == "cancelled"
    # Still inside the paid period: access remains (cancel stops renewal).
    level = subs.access_level("fan1", p["id"], TRACK_AI, home)
    assert level["tier_rank"] == t["rank"]
    # After the period: no access.
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    ai_update(home, "creator_subs", s["id"], {"expires_at": past})
    assert subs.access_level("fan1", p["id"], TRACK_AI, home)["tier_rank"] is None


def test_unsubscribe_is_owner_only(home, iso, keeper):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    s = _sub(p["id"], t["id"], keeper, home=home)
    with pytest.raises(subs.AccessDeniedError):
        subs.unsubscribe(s["id"], "someone-else", TRACK_AI, home)


def test_subscriber_and_creator_lists(home, iso, keeper):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, sub="fan1", home=home)
    _sub(p["id"], t["id"], keeper, sub="fan2", home=home)
    assert {s["subscriber_id"] for s in subs.list_subscribers(p["id"], TRACK_AI, home)} == {
        "fan1",
        "fan2",
    }
    assert len(subs.list_subscriptions("fan1", TRACK_AI, home)) == 1


# -- Access tokens (L2: server-side verification) -----------------------


def _publish_tier_content(p, t, home):
    return creator_content.publish(
        p["id"], "Episode 1", "The first episode", "post", TRACK_AI,
        home=home, tier_id=t["id"],
    )


def test_access_denied_without_subscription(home, iso):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    # L2: no valid subscription -> no token, fail closed.
    with pytest.raises(subs.AccessDeniedError):
        subs.issue_access_token("stranger", p["id"], t["id"], TRACK_AI, home)


def test_issue_verify_access_lifecycle(home, iso, keeper, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    item = _publish_tier_content(p, t, home)
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    assert issued["token"] and issued["expires_in"] == subs.ACCESS_TOKEN_TTL
    grant = subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)
    assert grant["granted"] is True
    assert grant["subscriber_id"] == "fan1"
    assert grant["paper"] is True  # honest: no rail, paper access


def test_expired_token_rejected(home, iso, keeper, monkeypatch, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    item = _publish_tier_content(p, t, home)
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    # Travel past the token's TTL: Cybrus validation fails closed.
    real_now = cybrus_tokens._now()
    monkeypatch.setattr(cybrus_tokens, "_now", lambda: real_now + 3600)
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)


def test_tampered_token_rejected(home, iso, keeper, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    item = _publish_tier_content(p, t, home)
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    bad = issued["token"][:-2] + ("AA" if not issued["token"].endswith("AA") else "BB")
    assert bad != issued["token"]
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(bad, item["id"], TRACK_AI, home, **cybrus)


def test_live_token_denied_after_subscription_lapses(home, iso, keeper, cybrus):
    # L2: the bearer alone grants nothing — the subscription is re-checked
    # server-side on every access.
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    s = _sub(p["id"], t["id"], keeper, home=home)
    item = _publish_tier_content(p, t, home)
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    ai_update(home, "creator_subs", s["id"], {"expires_at": past})
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)


def test_tier_rank_gating(home, iso, keeper, cybrus):
    p = _creator(home=home)
    low = _tier(p["id"], name="taste", price=100, period="day", home=home, rank=0)
    high = _tier(p["id"], name="patron", price=2000, period="month", home=home, rank=1)
    _sub(p["id"], low["id"], keeper, home=home)
    low_item = creator_content.publish(
        p["id"], "Low", "low tier", "post", TRACK_AI, home=home, tier_id=low["id"]
    )
    high_item = creator_content.publish(
        p["id"], "High", "high tier", "post", TRACK_AI, home=home, tier_id=high["id"]
    )
    tok = subs.issue_access_token("fan1", p["id"], low["id"], TRACK_AI, home)
    assert subs.verify_access(tok["token"], low_item["id"], TRACK_AI, home, **cybrus)["granted"]
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(tok["token"], high_item["id"], TRACK_AI, home, **cybrus)


def test_revoke_token_stops_access(home, iso, keeper, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    item = _publish_tier_content(p, t, home)
    issued = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_AI, home)
    assert subs.revoke_access_token(issued["token_id"], TRACK_AI, home) is True
    with pytest.raises(subs.AccessDeniedError):
        subs.verify_access(issued["token"], item["id"], TRACK_AI, home, **cybrus)


# -- Payouts (L1: Cybrus only) -------------------------------------------


def test_payout_recorded_as_pending_via_gateway(home, iso, keeper, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], price=400, home=home)
    s = _sub(p["id"], t["id"], keeper, home=home)
    entry = _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)
    assert entry["status"] == "pending_payout"  # no rail: nothing moved, honestly
    assert entry["paper"] is True
    assert entry["plan_id"].startswith("mpl_")
    assert entry["cybrus_ticket"]  # choke-point routing ticket attached
    assert entry["settled_sub_ids"] == [s["id"]]
    # 12% platform cut: 400 -> fee 48, creator keeps 352.
    assert entry["platform_fee_minor"] == 48
    assert entry["amount_minor"] == 352
    assert entry["payout_reference"] == "bank-ref-8472"  # opaque label, L4
    assert entry["receipt"]["law"] == "Cybrus alone handles money."
    # Full gateway audit trail for the plan.
    gw = MoneyGateway()
    audit = gw.audit_log(limit=50)
    plan_events = [e["event"] for e in audit if e.get("plan_id") == entry["plan_id"]]
    assert "planned" in plan_events
    assert "execute_refused" in plan_events


def test_payout_settles_each_subscription_once(home, iso, keeper, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, sub="fan1", home=home)
    _sub(p["id"], t["id"], keeper, sub="fan2", home=home)
    first = _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)
    assert len(first["settled_sub_ids"]) == 2
    with pytest.raises(subs.PayoutError):
        _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)


def test_payout_refused_without_keeper_auth(home, iso, keeper, mallory, cybrus):
    p = _creator(home=home)
    t = _tier(p["id"], home=home)
    _sub(p["id"], t["id"], keeper, home=home)
    with pytest.raises(MoneyRefused):
        subs.record_payout(p["id"], mallory, TRACK_AI, home, **cybrus)
    # L1: a refused payout leaves no payout record behind.
    assert subs.list_payouts(p["id"], TRACK_AI, home) == []


def test_payout_with_no_balance_refused(home, iso, keeper, cybrus):
    p = _creator(home=home)
    with pytest.raises(subs.PayoutError):
        _with_approval(subs.record_payout, p["id"], keeper, TRACK_AI, home, **cybrus)


def test_creator_balance_math(home, iso, keeper):
    p = _creator(home=home)
    t = _tier(p["id"], price=2000, home=home)  # patron: 2000 -> fee 240, keep 1760
    _sub(p["id"], t["id"], keeper, home=home)
    bal = subs.creator_balance(p["id"], TRACK_AI, home)
    assert bal["unsettled_count"] == 1
    assert bal["platform_fee_minor"] == 240
    assert bal["creator_total_minor"] == 1760
    assert bal["paper"] is True


# -- L5: the safety gates cannot be bypassed -----------------------------


def test_si_locked_without_gate(home, iso, keeper):
    with pytest.raises(GateLockedError):
        _creator(track=TRACK_SI, home=home)
    p_ai = _creator(home=home)
    with pytest.raises(GateLockedError):
        subs.add_tier(p_ai["id"], "t", 100, "day", TRACK_SI, home=home)
    with pytest.raises(GateLockedError):
        subs.subscribe("c", "t", "fan", keeper, TRACK_SI, home)
    with pytest.raises(GateLockedError):
        subs.record_payout("c", keeper, TRACK_SI, home)


def test_si_full_flow_behind_gate(home, iso, keeper, cybrus):
    _enable(home)
    p = _creator(track=TRACK_SI, home=home)
    t = _tier(p["id"], track=TRACK_SI, home=home)
    s = _with_approval(subs.subscribe, p["id"], t["id"], "fan1", keeper, TRACK_SI, home)
    assert s["status"] == "pending_payment"
    tok = subs.issue_access_token("fan1", p["id"], t["id"], TRACK_SI, home)
    item = creator_content.publish(
        p["id"], "Gated drop", "adult description", "post", TRACK_SI,
        home=home, tier_id=t["id"],
    )
    assert subs.verify_access(tok["token"], item["id"], TRACK_SI, home, **cybrus)["granted"]
    # Tracks never merge: the SI store holds no AI-track records.
    assert si_read_all(home, "creator_profiles")[0]["id"] == p["id"]
    assert all(r["track"] == TRACK_SI for r in si_read_all(home, "creator_subs"))


def test_tracks_never_merge(home, iso):
    _enable(home)
    p_ai = _creator(track=TRACK_AI, home=home)
    p_si = _creator(track=TRACK_SI, home=home)
    assert p_ai["handle"] == p_si["handle"]  # same handle, separate tracks
    ai_ids = {r["id"] for r in ai_read_all(home, "creator_profiles")}
    si_ids = {r["id"] for r in si_read_all(home, "creator_profiles")}
    assert ai_ids.isdisjoint(si_ids)
    assert subs.get_profile(p_ai["id"], TRACK_AI, home)["id"] == p_ai["id"]
    with pytest.raises(subs.SubscriptionError):
        subs.get_profile(p_ai["id"], TRACK_SI, home)  # not on this track
