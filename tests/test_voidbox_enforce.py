"""Tests for levi.voidbox.enforce — Cybrus thrown on top of Void Box.

Hermetic: cybrus stores root at $LEVI_HOME, money at $LEVI_CYBRUS_DIR,
rooms + gate at tmp_path. The adult gate opens per-test via the one
lawful path (set_pin + enable_adult_mode).

Proofs: (a) gate locked -> every entry point raises before anything
else; (b) no approval -> fail-closed, nothing half-applied; (c) RED-1:
mismatched/tampered consume details refused; (d) tampered approval
refused at the guarded layer; (e) policy default-deny refuses, and a
policy deny never consumes the approval; (f) money without approval
raises; the full money ceremony still fails closed (no rail); tampered
money approval refused; (g) one audit record per action; (h) read-only
actions unenforced but gated; (i) verify_laws passes.
"""

import pytest

from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.money import MoneyApprovalRequired, NoRailConfigured
from levi.cybrus.policy import PolicyEngine
from levi.plaiground import gate
from levi.plaiground.gate import GateLockedError
from levi.voidbox import enforce
from levi.voidbox.enforce import (
    ACTION_ROOM_CREATE,
    ApprovalNeeded,
    EnforcementError,
    PolicyRefused,
    _approval_details,
    check_invariants,
    grant_owner_rules,
    verify_laws,
)
from levi.voidbox.relay import MailboxStore
from levi.voidbox.rooms import RoomStore

_TEST_PIN = "424242"
_TEST_PASSPHRASE = "correct horse battery staple voidbox enforce"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """All cybrus state (approvals/policy/audit/money) roots at tmp."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "levi-home" / "cybrus"))


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


@pytest.fixture
def home(tmp_path):
    _open_gate(tmp_path)
    return tmp_path


@pytest.fixture
def store(home):
    return RoomStore(_TEST_PASSPHRASE, home=home)


@pytest.fixture
def rules(home):
    return grant_owner_rules("alice")


def _audit_events():
    return [rec.get("event") for rec in AuditEngine().tail(100)]


def _run_with_approval(fn, *args, **kw):
    """The human ceremony: first call raises ApprovalNeeded, the human
    approves, the retry consumes and executes."""
    try:
        return fn(*args, **kw)
    except ApprovalNeeded as need:
        ApprovalEngine().approve(need.approval_id, by="chauncey")
        return fn(*args, **kw)


def _create_room(store, home, **kw):
    kw.setdefault("actor", "alice")
    kw.setdefault("gate_home", home)
    return _run_with_approval(
        enforce.create_room_guarded, store, "war-room", "alice", **kw
    )


# -- (a) the SI gate fires first, on every entry point ----------------------


def test_gate_locked_by_default(store, tmp_path):
    locked = tmp_path / "locked"  # gate never opened here
    with pytest.raises(GateLockedError):
        enforce.create_room_guarded(
            store, "x", "alice", actor="alice", gate_home=locked
        )
    with pytest.raises(GateLockedError):
        enforce.charge_guarded(
            operation="charge", amount_minor=100, currency="USD",
            rail="r", purpose="p", identity="alice", actor="alice",
            gate_home=locked,
        )
    with pytest.raises(GateLockedError):
        enforce.open_message_gated(store, "room_x", "alice", {}, gate_home=locked)
    with pytest.raises(GateLockedError):
        enforce.poll_gated(MailboxStore(store_dir=str(tmp_path / "mb")), "alice",
                           gate_home=locked)


# -- (b) no approval: fail-closed, nothing half-applied ----------------------


def test_no_approval_refuses_and_applies_nothing(store, home, rules):
    from levi.voidbox.rooms import voidbox_rooms_dir

    before = set(p.name for p in voidbox_rooms_dir(home).iterdir())
    with pytest.raises(ApprovalNeeded) as exc:
        enforce.create_room_guarded(store, "war-room", "alice",
                                    actor="alice", gate_home=home)
    approval_id = exc.value.approval_id
    after = set(p.name for p in voidbox_rooms_dir(home).iterdir())
    assert before == after  # no room file written: fail-closed
    assert "voidbox.enforce.approval_needed" in _audit_events()

    # A second attempt reuses the SAME pending approval (no double mint).
    with pytest.raises(ApprovalNeeded) as exc2:
        enforce.create_room_guarded(store, "war-room", "alice",
                                    actor="alice", gate_home=home)
    assert exc2.value.approval_id == approval_id


# -- full ceremony: request -> approve -> consume -> execute -----------------


def test_create_room_full_ceremony(store, home, rules):
    meta = _create_room(store, home)
    assert meta["name"] == "war-room"
    assert meta["admin_id"] == "alice"
    events = _audit_events()
    assert "voidbox.enforce.executed" in events
    # The executed record names the exact approval action.
    recs = [r for r in AuditEngine().tail(20)
            if r.get("event") == "voidbox.enforce.executed"]
    assert recs and recs[-1]["details"]["voidbox_action"] == ACTION_ROOM_CREATE


def test_single_use_replay_refused(store, home, rules):
    _create_room(store, home)
    # The consumed approval cannot be replayed: a fresh approval is needed.
    with pytest.raises(ApprovalNeeded) as exc1:
        enforce.create_room_guarded(store, "second", "alice",
                                    actor="alice", gate_home=home)
    first_id = exc1.value.approval_id
    ApprovalEngine().approve(first_id, by="chauncey")
    enforce.create_room_guarded(store, "second", "alice",
                                actor="alice", gate_home=home)
    with pytest.raises(ApprovalNeeded) as exc2:
        enforce.create_room_guarded(store, "third", "alice",
                                    actor="alice", gate_home=home)
    assert exc2.value.approval_id != first_id  # single-use: fresh ceremony


def test_add_remove_member_guarded(store, home, rules):
    room_id = _create_room(store, home)["room_id"]
    meta = _run_with_approval(
        enforce.add_member_guarded, store, room_id, "bob", "alice",
        actor="alice", gate_home=home,
    )
    assert "bob" in meta["members"]
    meta = _run_with_approval(
        enforce.remove_member_guarded, store, room_id, "bob", "alice",
        actor="alice", gate_home=home,
    )
    assert meta["members"]["bob"]["removed_epoch"] is not None


def test_leave_room_guarded(store, home, rules):
    grant_owner_rules("bob")  # the leaver is the policy subject of their leave
    room_id = _create_room(store, home)["room_id"]
    _run_with_approval(enforce.add_member_guarded, store, room_id, "bob",
                       "alice", actor="alice", gate_home=home)
    meta = _run_with_approval(enforce.leave_room_guarded, store, room_id,
                              "bob", actor="bob", gate_home=home)
    assert meta["members"]["bob"]["removed_epoch"] is not None


def test_revoke_device_guarded(store, home, rules):
    room_id = _create_room(store, home, device_id="alice-phone")["room_id"]
    meta = _run_with_approval(
        enforce.revoke_device_guarded, store, room_id, "alice",
        "alice-phone", "alice", actor="alice", gate_home=home,
    )
    assert meta["members"]["alice"]["devices"]["alice-phone"]["revoked"] is True


def test_publish_listing_guarded(store, home, rules):
    room_id = _create_room(store, home, public=True)["room_id"]
    listing = _run_with_approval(
        enforce.publish_listing_guarded, store, room_id,
        actor="alice", blurb="open study group", gate_home=home,
    )
    assert listing["room_id"] == room_id
    assert listing["name"] == "war-room"
    assert listing["public"] is True
    # A listing advertises existence only: no keys, no members, no content.
    assert set(listing) <= {"room_id", "name", "public", "listed_by",
                            "blurb", "listed_at"}
    listed = enforce.list_listings(gate_home=home)
    assert any(l["room_id"] == room_id for l in listed)


# -- (c) RED-1: exact-match consume ------------------------------------------


def test_red1_mismatched_consume_details_refused(home):
    eng = ApprovalEngine()
    exact = _approval_details(ACTION_ROOM_CREATE, "alice", name="x",
                              creator_id="alice", public=False, device_id=None)
    entry = eng.request_approval(ACTION_ROOM_CREATE, "alice",
                                 "voidbox.room", "high", details=dict(exact))
    eng.approve(entry["id"], by="chauncey")
    # A plainer consume must not silently drop fields the approver saw.
    tampered = dict(exact)
    tampered["public"] = True  # flip one bound field
    assert eng.consume_approved(ACTION_ROOM_CREATE, tampered) is None
    assert eng.consume_approved(ACTION_ROOM_CREATE, dict(exact)) is not None


def test_red1_extra_field_consume_refused(home):
    eng = ApprovalEngine()
    exact = _approval_details(ACTION_ROOM_CREATE, "alice", name="x",
                              creator_id="alice", public=False, device_id=None)
    entry = eng.request_approval(ACTION_ROOM_CREATE, "alice",
                                 "voidbox.room", "high", details=dict(exact))
    eng.approve(entry["id"], by="chauncey")
    extra = dict(exact)
    extra["injected"] = "evil"
    assert eng.consume_approved(ACTION_ROOM_CREATE, extra) is None


# -- (d) tampered approval refused at the guarded layer ----------------------


def test_tampered_approval_refused_fail_closed(store, home, rules):
    from levi.voidbox.rooms import voidbox_rooms_dir

    details = _approval_details(ACTION_ROOM_CREATE, "alice", name="war-room",
                                creator_id="alice", public=False, device_id=None)
    entry = enforce.request_enforcement_approval(
        "room.create", ACTION_ROOM_CREATE, "alice", details
    )
    ApprovalEngine().approve(entry["id"], by="chauncey")
    # Attacker annotates the approved entry: details no longer exact.
    ApprovalEngine().annotate(entry["id"], injected="evil")
    before = set(p.name for p in voidbox_rooms_dir(home).iterdir())
    with pytest.raises(ApprovalNeeded):
        enforce.create_room_guarded(store, "war-room", "alice",
                                    actor="alice", gate_home=home)
    after = set(p.name for p in voidbox_rooms_dir(home).iterdir())
    assert before == after  # tampered grant buys nothing


# -- (e) policy: default-deny, and deny never consumes -----------------------


def test_policy_default_deny_refuses(store, home):
    # No grant_owner_rules: the policy engine default-denies (fail closed).
    with pytest.raises(PolicyRefused):
        enforce.create_room_guarded(store, "war-room", "alice",
                                    actor="alice", gate_home=home)
    assert "voidbox.enforce.policy_refused" in _audit_events()


def test_policy_deny_does_not_consume_approval(store, home, rules):
    details = _approval_details(ACTION_ROOM_CREATE, "alice", name="war-room",
                                creator_id="alice", public=False, device_id=None)
    entry = enforce.request_enforcement_approval(
        "room.create", ACTION_ROOM_CREATE, "alice", details
    )
    ApprovalEngine().approve(entry["id"], by="chauncey")
    # A deny registered AFTER the approval still wins (deny > approval).
    engine = PolicyEngine()
    deny = engine.add_rule("alice", "voidbox.room", "create", "deny", "critical")
    with pytest.raises(PolicyRefused):
        enforce.create_room_guarded(store, "war-room", "alice",
                                    actor="alice", gate_home=home)
    kept = ApprovalEngine().get_entry(entry["id"])
    assert kept["status"] == "approved"  # never consumed by the denied action
    assert "consumed_at" not in kept["details"]
    # Remove the deny; the untouched approval now spends cleanly.
    idx = next(i for i, r in enumerate(engine.list_rules()) if r == deny)
    engine.remove_rule(idx)
    meta = enforce.create_room_guarded(store, "war-room", "alice",
                                       actor="alice", gate_home=home)
    assert meta["name"] == "war-room"


# -- (f) money: the ONLY path, fail-closed -----------------------------------


def _charge_kw(home, **kw):
    base = dict(operation="charge", amount_minor=500, currency="USD",
                rail="test-rail", purpose="voidbox premium",
                identity="alice", actor="alice", gate_home=home)
    base.update(kw)
    return base


def test_charge_without_approval_raises(store, home, rules):
    with pytest.raises(MoneyApprovalRequired) as exc:
        enforce.charge_guarded(**_charge_kw(home))
    assert exc.value.approval_id  # the remedy rides on the exception
    assert "voidbox.enforce.charge.approval_needed" in _audit_events()


def test_charge_full_ceremony_still_fail_closed_no_rail(store, home, rules):
    # First call raises with the pending approval id (nothing moves).
    with pytest.raises(MoneyApprovalRequired) as exc:
        enforce.charge_guarded(**_charge_kw(home))
    approval_id = exc.value.approval_id
    ApprovalEngine().approve(approval_id, by="chauncey")
    # Full ceremony completes, but with no registered rail the gateway
    # refuses: money never moves (fail-closed is the honest posture).
    with pytest.raises(NoRailConfigured):
        enforce.charge_guarded(approval_id=approval_id, **_charge_kw(home))
    # The approval was consumed atomically (single-use) even though the
    # movement refused.
    kept = ApprovalEngine().get_entry(approval_id)
    assert "consumed_at" in kept["details"]
    assert "voidbox.enforce.charge.refused" in _audit_events()


def test_charge_tampered_approval_refused(store, home, rules):
    with pytest.raises(MoneyApprovalRequired) as exc:
        enforce.charge_guarded(**_charge_kw(home))
    approval_id = exc.value.approval_id
    ApprovalEngine().approve(approval_id, by="chauncey")
    ApprovalEngine().annotate(approval_id, injected="evil")
    # The gateway's RED-1 consume sees the mismatch and refuses the replay.
    from levi.cybrus.money import ApprovalReplayRefused

    with pytest.raises(ApprovalReplayRefused):
        enforce.charge_guarded(approval_id=approval_id, **_charge_kw(home))


def test_charge_policy_deny_refuses(store, home):
    # No owner rules: money is default-denied before the gateway runs.
    with pytest.raises(PolicyRefused):
        enforce.charge_guarded(**_charge_kw(home))
    assert "voidbox.enforce.charge.policy_refused" in _audit_events()


def test_charge_rejects_float_and_bad_operation(store, home, rules):
    with pytest.raises(EnforcementError):
        enforce.charge_guarded(**_charge_kw(home, amount_minor=19.99))
    with pytest.raises(EnforcementError):
        enforce.charge_guarded(**_charge_kw(home, operation="mint"))


# -- (g) every action writes one tamper-evident audit record -----------------


def test_audit_record_per_action(store, home, rules):
    room_id = _create_room(store, home)["room_id"]
    _run_with_approval(enforce.add_member_guarded, store, room_id, "bob",
                       "alice", actor="alice", gate_home=home)
    executed = [r for r in AuditEngine().tail(50)
                if r.get("event") == "voidbox.enforce.executed"]
    actions = [r["details"]["voidbox_action"] for r in executed]
    assert "voidbox.room.create" in actions
    assert "voidbox.room.member_add" in actions
    # The chain itself verifies (tamper-evident).
    ok, bad = AuditEngine().verify()
    assert ok, "audit chain broken at %r" % (bad,)


def test_operation_failure_audited_and_fail_closed(store, home, rules):
    grant_owner_rules("mallory")  # policy allows; the PRODUCT layer refuses
    room_id = _create_room(store, home)["room_id"]
    # mallory is not the admin: the product layer refuses AFTER the
    # approval is legitimately consumed.
    with pytest.raises(Exception):
        _run_with_approval(enforce.add_member_guarded, store, room_id,
                           "mallory", "mallory", actor="mallory",
                           gate_home=home)
    assert "voidbox.enforce.operation_failed" in _audit_events()


# -- (h) read-only: unenforced, still gated ----------------------------------


def test_read_only_actions_need_no_approval_or_policy(store, home, rules):
    # Setup uses the ceremony; the READS below need no approval and no
    # policy interaction of their own.
    room_id = _create_room(store, home)["room_id"]
    env = store.seal_message(room_id, "alice", b"hello")
    opened = enforce.open_message_gated(store, room_id, "alice", env,
                                        gate_home=home)
    assert opened["plaintext"] == b"hello"
    assert enforce.get_room_gated(store, room_id, gate_home=home)["room_id"] == room_id


def test_read_only_still_gate_checked(store, home, tmp_path):
    locked = tmp_path / "locked"
    with pytest.raises(GateLockedError):
        enforce.get_room_gated(store, "room_x", gate_home=locked)


def test_relay_poll_gated_not_enforced(tmp_path, home):
    mb = MailboxStore(store_dir=str(tmp_path / "mailbox"))
    assert enforce.poll_gated(mb, "alice", gate_home=home) == []


# -- (i) laws ----------------------------------------------------------------


def test_verify_laws_all_pass(home):
    results = verify_laws()
    assert results, "no laws registered"
    failed = [(law, detail) for law, ok, detail in results if not ok]
    assert not failed, "law failures: %r" % (failed,)
    assert check_invariants() == results


def test_laws_registry_well_formed():
    ids = [law_id for law_id, _ in enforce.LAWS]
    assert len(ids) >= 10
    assert len(set(ids)) == len(ids)
