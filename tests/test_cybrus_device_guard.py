"""PROOF gate for the Cybrus LEFT-GUARD (device watchfulness).

L8 (law->guard->prove): the invariants are declared in
``levi.cybrus.device_guard``; this file machine-checks them. Nothing here
is formally proven — only tested against the laws, honestly named.

- I1: unknown device never executes a device-bound privileged call;
  first sighting enrolls untrusted AND raises the alert.
- I2: trust promotion requires a consumed, single-use human approval;
  silent promotion raises TrustGrantError and the level does not move.
- I3: approvals are single-use — replays promote nothing.
- I4: every ceremony step leaves an audit receipt; the chain verifies.
- I5: trust decays with staleness (demotions, receipts, never silent).
- I6: fingerprint mismatch demotes to untrusted + re-alerts.
- I7: demotion is never gated.
- I8: expired/denied approvals grant nothing.

Hermetic: LEVI_HOME pinned to tmp, no network.
"""

import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from levi.cybrus import device_guard as guard_mod
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.device_guard import DeviceGuard
from levi.cybrus.devices import (
    DEVICE_TRUST_GRANT_ACTION,
    DeviceTrust,
    TrustGrantError,
)
from levi.cybrus.enforce import DeviceDenied, route_service_call, cybrus_guarded
from levi.cybrus.policy import PolicyEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def guard(home):
    return DeviceGuard()


def _events(audit):
    return [r["event"] for r in audit.tail(100)]


def _approve_to(guard, device_id, level):
    """Human ceremony: raise, approve, consume -> promoted record."""
    approval_id = guard.request_trust(device_id, level)
    guard.approvals.approve(approval_id, by="chauncey")
    return guard.grant(device_id, level, approval_id)


# ---------------------------------------------------------------------------
# I1: unknown device never executes; sighting enrolls untrusted + alerts
# ---------------------------------------------------------------------------


def test_sighting_enrolls_untrusted_and_raises_alert(guard):
    record, approval_id = guard.sighting("phone-1", "Chauncey's phone")
    assert record["trust"] == "untrusted"
    assert guard.trust.is_trusted("phone-1") is False

    pending = guard.approvals.pending()
    assert len(pending) == 1
    assert pending[0]["id"] == approval_id
    assert pending[0]["action"] == DEVICE_TRUST_GRANT_ACTION
    assert pending[0]["status"] == "pending"

    events = _events(guard.audit)
    assert "device.sighted" in events
    assert "device.trust_requested" in events
    ok, bad = guard.audit.verify()
    assert ok, f"audit chain broken at {bad}"


def test_sighting_twice_reuses_pending_approval(guard):
    _, first = guard.sighting("phone-1", "Chauncey's phone")
    _, second = guard.sighting("phone-1", "Chauncey's phone")
    assert first == second
    assert len(guard.approvals.pending()) == 1


def test_unknown_device_cannot_silently_become_trusted(guard):
    # The core bypass RED tries first: promote with no approval anywhere.
    guard.sighting("phone-1", "Chauncey's phone")
    with pytest.raises(TrustGrantError):
        guard.trust.set_trust("phone-1", "trusted")
    assert guard.trust.get("phone-1")["trust"] == "untrusted"


# ---------------------------------------------------------------------------
# I2/I3: promotion consumes a single-use human approval
# ---------------------------------------------------------------------------


def test_promotion_needs_human_approval(guard):
    guard.sighting("phone-1", "Chauncey's phone")
    with pytest.raises(TrustGrantError):
        guard.trust.set_trust("phone-1", "known")
    rec = _approve_to(guard, "phone-1", "known")
    assert rec["trust"] == "known"
    assert "device.trust_granted" in _events(guard.audit)


def test_approval_is_single_use_no_replay(guard):
    guard.sighting("phone-1", "Chauncey's phone")
    approval_id = guard.request_trust("phone-1", "known")
    guard.approvals.approve(approval_id, by="chauncey")
    guard.grant("phone-1", "known", approval_id)
    # Replay the same approval id: check() still True, but the grant is
    # already consumed -> TrustGrantError, no promotion to trusted.
    with pytest.raises(TrustGrantError):
        guard.grant("phone-1", "trusted", approval_id)
    assert guard.trust.get("phone-1")["trust"] == "known"


def test_grant_bound_to_device_and_level(guard):
    # An approval for phone-1/known cannot promote phone-2 or skip to trusted.
    guard.sighting("phone-1", "P1")
    guard.sighting("phone-2", "P2")
    approval_id = guard.request_trust("phone-1", "known")
    guard.approvals.approve(approval_id, by="chauncey")
    with pytest.raises(TrustGrantError):
        guard.trust.set_trust("phone-2", "known")
    with pytest.raises(TrustGrantError):
        guard.trust.set_trust("phone-1", "trusted")
    assert guard.trust.get("phone-1")["trust"] == "untrusted"
    assert guard.trust.get("phone-2")["trust"] == "untrusted"


# ---------------------------------------------------------------------------
# I8: expired / denied approvals grant nothing
# ---------------------------------------------------------------------------


def test_expired_approval_grants_nothing(guard):
    guard.sighting("phone-1", "P1")
    entry = guard.approvals.request_approval(
        DEVICE_TRUST_GRANT_ACTION,
        "phone-1",
        "device:phone-1",
        "high",
        details={"device_id": "phone-1", "level": "known"},
        ttl_seconds=-1,  # already expired
    )
    with pytest.raises(TrustGrantError):
        guard.grant("phone-1", "known", entry["id"])
    with pytest.raises(TrustGrantError):
        guard.trust.set_trust("phone-1", "known")
    assert guard.trust.get("phone-1")["trust"] == "untrusted"


def test_denied_approval_grants_nothing(guard):
    guard.sighting("phone-1", "P1")
    approval_id = guard.request_trust("phone-1", "known")
    guard.deny("phone-1", approval_id, reason="not my phone")
    assert "device.trust_denied" in _events(guard.audit)
    with pytest.raises(TrustGrantError):
        guard.grant("phone-1", "known", approval_id)
    assert guard.trust.get("phone-1")["trust"] == "untrusted"


# ---------------------------------------------------------------------------
# I7: demotion is never gated
# ---------------------------------------------------------------------------


def test_demotion_needs_no_grant(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "trusted")
    rec = guard.trust.set_trust("phone-1", "untrusted")
    assert rec["trust"] == "untrusted"
    assert "device.trust_demoted" in _events(guard.audit)


def test_challenge_demotes_and_realerts(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "trusted")
    result = guard.challenge("phone-1", reason="suspicious login")
    assert result["record"]["trust"] == "untrusted"
    assert guard._pending_grant("phone-1") is not None
    assert "device.challenged" in _events(guard.audit)


# ---------------------------------------------------------------------------
# I6: fingerprint anti-spoofing
# ---------------------------------------------------------------------------


def test_fingerprint_mismatch_demotes_and_realerts(guard):
    guard.sighting("phone-1", "P1", fingerprint="fp-real")
    _approve_to(guard, "phone-1", "trusted")
    result = guard.seen("phone-1", fingerprint="fp-evil")
    assert result["status"] == "spoof_suspect"
    assert guard.trust.get("phone-1")["trust"] == "untrusted"
    assert "device.fingerprint_mismatch" in _events(guard.audit)


def test_fingerprint_match_passes_heartbeat(guard):
    guard.sighting("phone-1", "P1", fingerprint="fp-real")
    result = guard.seen("phone-1", fingerprint="fp-real")
    assert result["status"] == "seen"


def test_raw_fingerprint_never_persisted_or_audited(guard):
    guard.sighting("phone-1", "P1", fingerprint="fp-real")
    store = json.loads(
        (guard.trust._path).read_text(encoding="utf-8")
    )
    blob = json.dumps(store)
    assert "fp-real" not in blob
    audit_blob = "\n".join(json.dumps(r) for r in guard.audit.tail(50))
    assert "fp-real" not in audit_blob


# ---------------------------------------------------------------------------
# I5: trust decay
# ---------------------------------------------------------------------------


def _backdate_last_seen(guard, device_id, days):
    trust = DeviceTrust()  # fresh instance, same LEVI_HOME
    path = trust._path
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for rec in data:
        if rec["id"] == device_id:
            rec["last_seen"] = old
    path.write_text(json.dumps(data), encoding="utf-8")


def test_decay_demotes_stale_trusted_device(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "trusted")
    _backdate_last_seen(guard, "phone-1", 40)
    receipts = guard.sweep_decay()
    assert receipts and receipts[0]["from"] == "trusted"
    assert receipts[0]["to"] == "known"
    assert DeviceGuard().trust.get("phone-1")["trust"] == "known"
    assert "device.trust_decayed" in _events(guard.audit)


def test_decay_second_tier_drops_to_untrusted(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "known")
    _backdate_last_seen(guard, "phone-1", 70)
    receipts = guard.sweep_decay()
    assert receipts and receipts[0]["to"] == "untrusted"
    assert DeviceGuard().trust.get("phone-1")["trust"] == "untrusted"


def test_decay_leaves_fresh_devices_alone(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "trusted")
    assert guard.sweep_decay() == []
    assert DeviceGuard().trust.get("phone-1")["trust"] == "trusted"


# ---------------------------------------------------------------------------
# I4: revocation + full lifecycle audit chain
# ---------------------------------------------------------------------------


def test_revoke_is_audited(guard):
    guard.sighting("phone-1", "P1")
    assert guard.revoke("phone-1", reason="lost") is True
    assert guard.trust.get("phone-1") is None
    assert "device.revoked" in _events(guard.audit)
    ok, bad = guard.audit.verify()
    assert ok, f"audit chain broken at {bad}"


def test_full_lifecycle_audit_chain_verifies(guard):
    guard.sighting("phone-1", "P1", fingerprint="fp-1")
    _approve_to(guard, "phone-1", "known")
    guard.seen("phone-1", fingerprint="fp-1")
    guard.challenge("phone-1", reason="test")
    events = _events(guard.audit)
    for expected in (
        "device.sighted",
        "device.trust_requested",
        "device.trust_granted",
        "device.challenged",
    ):
        assert expected in events
    ok, bad = guard.audit.verify()
    assert ok, f"audit chain broken at {bad}"


# ---------------------------------------------------------------------------
# Consistency: registry vs audit receipts (RED-5: file-level poisoning)
# ---------------------------------------------------------------------------


def test_verify_consistency_clean(guard):
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "trusted")
    assert guard.verify_consistency() == []


def test_verify_consistency_detects_file_level_poisoning(guard):
    guard.sighting("phone-1", "P1")
    # RED-5: attacker with disk write flips the trust bit directly.
    path = guard.trust._path
    data = json.loads(path.read_text(encoding="utf-8"))
    data[0]["trust"] = "trusted"
    path.write_text(json.dumps(data), encoding="utf-8")

    bad = guard.verify_consistency()
    assert len(bad) == 1
    assert bad[0]["device_id"] == "phone-1"
    assert bad[0]["trust"] == "trusted"
    assert "device.registry_inconsistent" in _events(guard.audit)


def _account(home):
    from levi.cybrus import rate_limits as rl
    from levi.cybrus.factory import AccountFactory
    from levi.cybrus.gateway import CybrusGateway

    record, password = AccountFactory().generate("svc-user", tier="starter")
    rl.set_tier("svc-user", "starter")
    _, token = CybrusGateway().auth("svc-user", password)
    return token


def _allow(name, resource, action, risk="low"):
    PolicyEngine().add_rule(name, resource, action, "allow", risk)


def test_unknown_device_call_refused_and_sighted(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="low")
    with pytest.raises(DeviceDenied):
        route_service_call(
            "svc-user", "levi.knowledge", "search",
            credential=token, device_id="mystery-phone",
        )
    # I1: sighted untrusted + alert raised, never executed.
    guard.trust.refresh()
    assert guard.trust.get("mystery-phone")["trust"] == "untrusted"
    assert guard._pending_grant("mystery-phone") is not None
    events = _events(guard.audit)
    assert "device.sighted" in events
    assert "call.device_refused" in events


def test_untrusted_device_call_refused(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="low")
    guard.sighting("phone-1", "P1")
    with pytest.raises(DeviceDenied):
        route_service_call(
            "svc-user", "levi.knowledge", "search",
            credential=token, device_id="phone-1",
        )


def test_known_device_low_risk_call_passes(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="low")
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "known")
    ticket = route_service_call(
        "svc-user", "levi.knowledge", "search",
        credential=token, device_id="phone-1",
    )
    assert ticket["allowed"] is True


def test_high_risk_call_requires_trusted_device(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="high")
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "known")
    # known is not enough for high-risk: refused at the device stage,
    # before the human-approval gate is even reached.
    with pytest.raises(DeviceDenied):
        route_service_call(
            "svc-user", "levi.knowledge", "search",
            credential=token, device_id="phone-1",
        )
    # trusted advances past the device stage (into the approval gate).
    _approve_to(guard, "phone-1", "trusted")
    from levi.cybrus.gateway import ApprovalRequired

    with pytest.raises(ApprovalRequired):
        route_service_call(
            "svc-user", "levi.knowledge", "search",
            credential=token, device_id="phone-1",
        )


def test_spoofed_fingerprint_call_refused(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="low")
    guard.sighting("phone-1", "P1", fingerprint="fp-real")
    _approve_to(guard, "phone-1", "known")
    with pytest.raises(DeviceDenied):
        route_service_call(
            "svc-user", "levi.knowledge", "search",
            credential=token, device_id="phone-1",
            device_fingerprint="fp-clone",
        )
    guard.trust.refresh()
    assert guard.trust.get("phone-1")["trust"] == "untrusted"


def test_calls_without_device_id_keep_working(guard, home):
    # Backward compatibility: no device binding, no behavior change.
    token = _account(home)
    _allow("svc-user", "service.levi.knowledge", "search", risk="low")
    ticket = route_service_call(
        "svc-user", "levi.knowledge", "search", credential=token
    )
    assert ticket["allowed"] is True


def test_cybrus_guarded_threads_device_kwargs(guard, home):
    token = _account(home)
    _allow("svc-user", "service.levi.jobs", "run", risk="low")

    @cybrus_guarded(service="svc-user", callee="levi.jobs", action="run")
    def run_jobs(query, *, cybrus_device_id=None):
        return "ran"

    with pytest.raises(DeviceDenied):
        run_jobs("q", cybrus_credential=token, cybrus_device_id="ghost")
    guard.sighting("phone-1", "P1")
    _approve_to(guard, "phone-1", "known")
    assert run_jobs("q", cybrus_credential=token, cybrus_device_id="phone-1") == "ran"


# ---------------------------------------------------------------------------
# I2/I5 global: seeded fuzz — trust never rises without a consumed grant
# ---------------------------------------------------------------------------


def test_fuzz_trust_never_rises_without_consumed_grant(home):
    rng = random.Random(0xC0FFEE)
    guard = DeviceGuard()
    granted_receipts = 0

    def grant_count():
        return sum(
            1 for r in guard.audit.tail(10000) if r["event"] == "device.trust_granted"
        )

    for step in range(300):
        op = rng.choice(
            ["sight", "approve_pending", "grant_direct", "challenge", "decay", "demote"]
        )
        dev = f"dev-{rng.randrange(6)}"
        if op == "sight":
            guard.sighting(dev, f"Device {dev}")
        elif op == "approve_pending":
            for entry in guard.approvals.pending():
                guard.approvals.approve(entry["id"], by="fuzz")
        elif op == "grant_direct":
            # RED's favorite: direct promotion with no ceremony.
            try:
                guard.trust.set_trust(dev, rng.choice(["known", "trusted"]))
            except (TrustGrantError, KeyError, ValueError):
                pass
        elif op == "challenge":
            try:
                guard.challenge(dev, reason="fuzz")
            except KeyError:
                pass
        elif op == "decay":
            _backdate_last_seen(guard, dev, rng.randrange(0, 100))
            guard.sweep_decay()
        elif op == "demote":
            try:
                guard.trust.set_trust(dev, "untrusted")
            except (KeyError, ValueError):
                pass

        # INVARIANT: every observed promotion has a consumed-grant receipt,
        # and no device sits above untrusted without one.
        for rec in guard.trust.list():
            if rec["trust"] != "untrusted":
                assert grant_count() > 0
        assert grant_count() >= granted_receipts
        granted_receipts = grant_count()

    ok, bad = guard.audit.verify()
    assert ok, f"audit chain broken at {bad}"
    # And the only writer of device.trust_granted is the consume path.
    for r in guard.audit.tail(10000):
        if r["event"] == "device.trust_granted":
            assert r["actor"] == "cybrus.devices"
            assert r["details"]["approval_id"]
