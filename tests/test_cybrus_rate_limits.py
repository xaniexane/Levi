"""Tests for the broker's tier-based rate limits (anti-spam).

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME writes,
no network. The broker wiring test stubs the human-approval gate (the
gate itself is tested elsewhere) to prove ``check()`` runs server-side
inside the broker's retrieval paths.
"""

import time

import pytest

from levi.cybrus import rate_limits as rl
from levi.cybrus.audit import AuditEngine
from levi.cybrus.rate_limits import RateLimitDenied

TEST_MASTER = "throwaway-test-passphrase-not-a-secret"


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    home = tmp_path / "rl-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def test_free_tier_zero_retrieval(iso):
    assert rl.get_tier("newbie") == "free"
    for action in rl.ACTIONS:
        with pytest.raises(RateLimitDenied) as exc_info:
            rl.check("newbie", action)
        assert "free tier" in str(exc_info.value).lower()
        assert exc_info.value.reset_at is None


def test_unknown_action_rejected(iso):
    with pytest.raises(ValueError):
        rl.check("u", "launch_missiles")


def test_starter_daily_quota(iso):
    rl.set_tier("u-day", "starter")
    # starter account_create is 2/hr, 5/day: age events past the hourly
    # window between batches so the DAILY cap is what binds
    for allowed in (2, 2, 1):
        for _ in range(allowed):
            rl.check("u-day", rl.ACCOUNT_CREATE)
        _age_events_hours(1.5)
    with pytest.raises(RateLimitDenied) as exc_info:
        rl.check("u-day", rl.ACCOUNT_CREATE)
    assert "5 per day" in str(exc_info.value)
    assert exc_info.value.reset_at is not None
    assert exc_info.value.reset_iso is not None


def test_starter_hourly_quota(iso):
    rl.set_tier("u-hour", "starter")
    for _ in range(2):  # account_create: 2/hr on starter
        rl.check("u-hour", rl.ACCOUNT_CREATE)
    with pytest.raises(RateLimitDenied) as exc_info:
        rl.check("u-hour", rl.ACCOUNT_CREATE)
    assert "per hour" in str(exc_info.value)


def _write_state_for_tests(state) -> None:
    """Persist rate-limit state in tests (single-threaded, no lock held)."""
    rl._save_state_unlocked(
        rl._paths().store_path(rl._RATE_LIMITS_STORE), state
    )


def _age_events_hours(hours: float) -> None:
    state = rl._load_state()
    for e in state["events"]:
        e["ts"] = time.time() - hours * 3600
    _write_state_for_tests(state)


def test_window_reset_after_events_age_out(iso):
    rl.set_tier("u-reset", "starter")
    for _ in range(2):
        rl.check("u-reset", rl.ACCOUNT_CREATE)
    with pytest.raises(RateLimitDenied):
        rl.check("u-reset", rl.ACCOUNT_CREATE)
    # age the events past the hourly window
    _age_events_hours(2)
    rl.check("u-reset", rl.ACCOUNT_CREATE)  # allowed again


def test_burst_triggers_cooldown(iso):
    rl.set_tier("u-burst", "starter")
    for _ in range(rl.BURST_THRESHOLD):
        rl.check("u-burst", rl.API_KEY_FETCH)
    with pytest.raises(RateLimitDenied) as exc_info:
        rl.check("u-burst", rl.API_KEY_FETCH)
    assert "burst" in str(exc_info.value).lower()
    assert exc_info.value.reset_at is not None
    # cooldown now gates even fresh actions
    with pytest.raises(RateLimitDenied) as exc_info2:
        rl.check("u-burst", rl.OAUTH_INITIATE)
    assert "cooldown" in str(exc_info2.value).lower()


def test_denials_and_allows_are_audited(iso):
    rl.set_tier("u-audit", "starter")
    rl.check("u-audit", rl.API_KEY_FETCH)
    with pytest.raises(RateLimitDenied):
        rl.check("u-audit2", rl.API_KEY_FETCH)  # free tier -> denied
    events = [r["event"] for r in AuditEngine().tail(50)]
    assert "ratelimit.allowed" in events
    assert "ratelimit.denied" in events


def test_admin_bypass_still_audited(iso):
    # Chauncey ("I'm Cybrus") is exempt from quotas...
    for _ in range(25):  # past every starter cap
        result = rl.check("chauncey", rl.API_KEY_FETCH)
        assert result["allowed"] is True
        assert result["tier"] == "admin"
    # ...but every attempt is still audit-logged
    events = [r["event"] for r in AuditEngine().tail(60)]
    assert "ratelimit.bypass" in events


def test_inflight_oauth_one_at_a_time(iso):
    rl.set_tier("u-flow", "starter")
    rl.check("u-flow", rl.OAUTH_INITIATE)
    rl.acquire_flow("u-flow")
    with pytest.raises(RateLimitDenied) as exc_info:
        rl.check("u-flow", rl.OAUTH_INITIATE)
    assert "in-flight" in str(exc_info.value)
    rl.release_flow("u-flow")
    rl.check("u-flow", rl.OAUTH_INITIATE)  # allowed again


def test_set_tier_rejects_unknown(iso):
    with pytest.raises(ValueError):
        rl.set_tier("u", "ultra")


def test_usage_report(iso):
    rl.set_tier("u-use", "pro")
    rl.check("u-use", rl.API_KEY_FETCH)
    report = rl.usage("u-use")
    assert report["tier"] == "pro"
    assert report["actions"][rl.API_KEY_FETCH]["used_day"] == 1
    assert report["inflight_oauth"] is False


def test_policy_summary_names_provisional_pricing():
    summary = rl.policy_summary()
    assert "Chauncey" in summary
    assert "FREE" in summary and "PLATFORM" in summary


# ---------------------------------------------------------------------------
# Broker wiring: check() runs server-side inside the retrieval paths
# ---------------------------------------------------------------------------


@pytest.fixture()
def no_approval_gate(monkeypatch):
    """Stub the human-approval gate (tested elsewhere) to reach the quota gate."""
    import levi.cybrus.broker as broker_mod

    monkeypatch.setattr(
        broker_mod, "_require_approval", lambda *a, **k: {"id": "test", "status": "x"}
    )
    return broker_mod


def test_broker_provision_enforces_tier(iso, no_approval_gate):
    from levi.cybrus.broker import CredentialBroker

    broker = CredentialBroker(TEST_MASTER, identity="wired")
    # free tier: zero automated retrieval, even past the approval gate
    with pytest.raises(RateLimitDenied):
        broker.provision("example.com", "https://example.com/signup")
    # starter tier: proceeds and consumes quota
    rl.set_tier("wired", "starter")
    record, password = broker.provision("example.com", "https://example.com/signup")
    assert record["status"] == "provisioned"
    assert len(password) > 0
    assert rl.usage("wired")["actions"][rl.ACCOUNT_CREATE]["used_day"] == 1


def test_broker_oauth_inflight_wiring(iso, no_approval_gate):
    from levi.cybrus.broker import CredentialBroker

    rl.set_tier("flowuser", "starter")
    broker = CredentialBroker(TEST_MASTER, identity="flowuser")
    flow = broker.oauth_start(
        "example-idp",
        "client-1",
        "https://idp.example.com/authorize",
        "https://app.example.com/callback",
    )
    assert flow["authorization_url"].startswith("https://idp.example.com/authorize")
    # second initiation while one is in flight -> denied
    with pytest.raises(RateLimitDenied) as exc_info:
        broker.oauth_start(
            "example-idp",
            "client-1",
            "https://idp.example.com/authorize",
            "https://app.example.com/callback",
        )
    assert "in-flight" in str(exc_info.value)
    # abandon releases the slot
    broker.oauth_abandon(flow["flow_id"])
    broker.oauth_start(
        "example-idp",
        "client-1",
        "https://idp.example.com/authorize",
        "https://app.example.com/callback",
    )
