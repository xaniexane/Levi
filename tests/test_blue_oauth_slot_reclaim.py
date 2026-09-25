"""BLUE regression for RED-1 #16 (stale OAuth in-flight slot lockout).

Proves the fix holds three ways:
  1. A stale slot is reclaimed with a concrete reset path — the user is
     never blocked forever.
  2. A live slot still blocks a second starter — no hijack/bypass of a
     legitimate flow, and slots are per-user (no cross-user effect).
  3. Every slot change (reclaim, manual release) is audit-logged.
"""

import json
import time

import pytest

from levi.cybrus import _paths
from levi.cybrus import rate_limits as rl
from levi.cybrus.audit import AuditEngine
from levi.cybrus.rate_limits import RateLimitDenied


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _store_path():
    return _paths.store_path("rate_limits")


def _backdate_inflight(user, days):
    p = _store_path()
    data = json.loads(p.read_text(encoding="utf-8"))
    data["inflight"][user]["since"] = time.time() - days * 86400
    p.write_text(json.dumps(data), encoding="utf-8")


def _audit_events():
    ok, _ = AuditEngine().verify()
    assert ok, "audit chain must verify"
    return [
        (rec["event"], rec["actor"], rec.get("details", {}))
        for rec in AuditEngine().tail(200)
    ]


def test_blue_stale_slot_reclaimed_with_concrete_reset(home):
    """A 30-day-abandoned slot is reclaimed on the next check: the denial
    names a concrete reset, the slot is gone, and the retry proceeds."""
    user = "b-oauth-stale"
    rl.set_tier(user, "starter")
    rl.acquire_flow(user)
    _backdate_inflight(user, 30)

    before = time.time()
    with pytest.raises(RateLimitDenied) as ei:
        rl.check(user, rl.OAUTH_INITIATE)
    after = time.time()

    assert "in-flight OAuth flow" in str(ei.value)
    # Concrete reset path — no more silent forever-block.
    assert ei.value.reset_at is not None
    assert before <= ei.value.reset_at <= after + 1

    # The slot was actually reclaimed: next attempt proceeds.
    assert rl.check(user, rl.OAUTH_INITIATE)["allowed"] is True
    assert rl.usage(user)["inflight_oauth"] is False

    # The reclaim went through the audit path.
    events = _audit_events()
    reclaims = [
        (ev, actor, det)
        for ev, actor, det in events
        if ev == "ratelimit.inflight_reclaimed" and actor == user
    ]
    assert len(reclaims) == 1, f"expected one reclaim audit, got: {events}"
    assert reclaims[0][2]["ttl_seconds"] == rl.OAUTH_FLOW_TTL_SECONDS


def test_blue_live_slot_still_blocks_second_starter(home):
    """A fresh (live) slot still blocks a second starter — no bypass, no
    hijack — and carries a TTL-based reset. Another user's flows are
    unaffected."""
    user = "b-oauth-live"
    other = "b-oauth-other"
    rl.set_tier(user, "starter")
    rl.set_tier(other, "starter")
    rl.acquire_flow(user)

    with pytest.raises(RateLimitDenied) as ei:
        rl.check(user, rl.OAUTH_INITIATE)
    assert "in-flight OAuth flow" in str(ei.value)
    assert ei.value.reset_at is not None
    assert ei.value.reset_at > time.time()

    # Same via the direct acquire path.
    with pytest.raises(RateLimitDenied):
        rl.acquire_flow(user)

    # No cross-user effect: another user starts flows freely.
    assert rl.check(other, rl.OAUTH_INITIATE)["allowed"] is True
    rl.acquire_flow(other)
    rl.release_flow(other)


def test_blue_release_flow_is_audited_abandon_path(home):
    """The manual reset path (release/abandon) only clears the caller's
    own slot and is audit-logged."""
    user = "b-oauth-release"
    victim = "b-oauth-victim"
    rl.set_tier(user, "starter")
    rl.set_tier(victim, "starter")
    rl.acquire_flow(user)
    rl.acquire_flow(victim)

    rl.release_flow(user)

    assert rl.check(user, rl.OAUTH_INITIATE)["allowed"] is True
    # Victim's live slot untouched by the caller's release.
    with pytest.raises(RateLimitDenied):
        rl.check(victim, rl.OAUTH_INITIATE)

    events = _audit_events()
    released = [
        (ev, actor)
        for ev, actor, _ in events
        if ev == "ratelimit.inflight_released" and actor == user
    ]
    assert len(released) == 1, f"expected one release audit, got: {events}"
