"""Tests for levi.voidbox.rooms — group messaging primitive.

Hermetic: every test roots the store at tmp_path (no HOME writes, no
network). The adult gate is opened per-test at the tmp home via the one
lawful path (set_pin + enable_adult_mode); the locked-gate tests prove
operations refuse without it.

Proofs: (a) removed member cannot open post-removal messages; (b) new
member cannot open pre-join messages; (c) replayed envelope rejected;
(d) re-key actually changes the room key bytes; (e) non-member
seal/open refused; (f) gate: operations raise without adult mode.
"""

import pytest

from levi.plaiground import gate
from levi.plaiground.gate import GateLockedError
from levi.voidbox import rooms
from levi.voidbox.rooms import (
    LAWS,
    EpochError,
    NotAdminError,
    NotMemberError,
    ReplayError,
    RoomError,
    RoomNotFoundError,
    RoomStore,
    check_invariants,
)

_TEST_PIN = "424242"
_TEST_PASSPHRASE = "correct horse battery staple voidbox"


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


@pytest.fixture
def store(tmp_path):
    _open_gate(tmp_path)
    return RoomStore(_TEST_PASSPHRASE, home=tmp_path)


@pytest.fixture
def room(store):
    meta = store.create_room("war-room", "alice", device_id="alice-phone")
    return meta["room_id"]


# -- (f) the gate: operations raise without adult mode ---------------------


def test_gate_locked_by_default(tmp_path):
    with pytest.raises(GateLockedError):
        RoomStore(_TEST_PASSPHRASE, home=tmp_path)


def test_gate_closed_mid_session_locks_operations(store, room, tmp_path):
    env = store.seal_message(room, "alice", b"before")
    assert store.open_message(room, "alice", env)["plaintext"] == b"before"
    gate.disable_adult_mode(home=tmp_path)
    with pytest.raises(GateLockedError):
        store.seal_message(room, "alice", b"after")
    with pytest.raises(GateLockedError):
        store.get_room(room)
    with pytest.raises(GateLockedError):
        store.verify_laws()


def test_module_helpers_gated(tmp_path):
    with pytest.raises(GateLockedError):
        rooms.voidbox_rooms_dir(home=tmp_path)
    with pytest.raises(GateLockedError):
        check_invariants(home=tmp_path)


# -- basic roundtrip --------------------------------------------------------

def test_create_and_roundtrip(store, room):
    meta = store.get_room(room)
    assert meta["admin_id"] == "alice"
    assert meta["epoch"] == 0
    assert meta["public"] is False
    env = store.seal_message(room, "alice", b"hello room")
    out = store.open_message(room, "alice", env)
    assert out["plaintext"] == b"hello room"
    assert out["sender"] == "alice"
    assert out["key_epoch"] == 0
    assert "blob" not in store.get_room(room)  # metadata carries no key material


def test_str_plaintext_accepted(store, room):
    env = store.seal_message(room, "alice", "text works too")
    assert store.open_message(room, "alice", env)["plaintext"] == b"text works too"


def test_unknown_room(store):
    with pytest.raises(RoomNotFoundError):
        store.seal_message("room_nope", "alice", b"x")


# -- membership + re-keying --------------------------------------------------

def test_add_member_rekeys_and_new_member_reads_new(store, room):
    store.add_member(room, "bob", by_admin="alice")
    assert store.get_room(room)["epoch"] == 1
    env = store.seal_message(room, "bob", b"bob is here")
    # Each member accepts the envelope once — group delivery.
    assert store.open_message(room, "alice", env)["plaintext"] == b"bob is here"
    assert store.open_message(room, "bob", env)["plaintext"] == b"bob is here"


def test_admin_authority(store, room):
    store.add_member(room, "bob", by_admin="alice")
    with pytest.raises(NotAdminError):
        store.add_member(room, "mallory", by_admin="bob")
    with pytest.raises(NotAdminError):
        store.remove_member(room, "alice", by_admin="bob")
    with pytest.raises(NotAdminError):
        store.revoke_member_device(room, "bob", "d1", by_admin="bob")


def test_admin_cannot_remove_self(store, room):
    with pytest.raises(RoomError):
        store.remove_member(room, "alice", by_admin="alice")


def test_leave_room_rekeys(store, room):
    store.add_member(room, "bob", by_admin="alice")
    store.leave_room(room, "bob")
    meta = store.get_room(room)
    assert meta["epoch"] == 2
    assert meta["members"]["bob"]["active"] is False


# -- (a) removed member cannot open post-removal messages -------------------

def test_removed_member_dark_after_removal(store, room):
    store.add_member(room, "bob", by_admin="alice")
    before = store.seal_message(room, "alice", b"while bob was here")
    assert store.open_message(room, "bob", before)["plaintext"] == b"while bob was here"
    store.remove_member(room, "bob", by_admin="alice")
    after = store.seal_message(room, "alice", b"after bob left")
    with pytest.raises(EpochError):
        store.open_message(room, "bob", after)
    # History sealed while bob was a member stays readable to members.
    assert store.open_message(room, "alice", before)["plaintext"] == b"while bob was here"
    # A removed member cannot seal either.
    with pytest.raises(NotMemberError):
        store.seal_message(room, "bob", b"sneaky")


# -- (b) new member cannot open pre-join messages ----------------------------

def test_new_member_dark_before_join(store, room):
    old = store.seal_message(room, "alice", b"before carol")
    store.add_member(room, "carol", by_admin="alice")
    new = store.seal_message(room, "alice", b"after carol joined")
    with pytest.raises(EpochError):
        store.open_message(room, "carol", old)
    assert store.open_message(room, "carol", new)["plaintext"] == b"after carol joined"


# -- (c) replay rejected -----------------------------------------------------

def test_replayed_envelope_rejected(store, room):
    env = store.seal_message(room, "alice", b"once")
    assert store.open_message(room, "alice", env)["plaintext"] == b"once"
    with pytest.raises(ReplayError):
        store.open_message(room, "alice", env)


def test_tampered_envelope_fails_closed(store, room):
    env = store.seal_message(room, "alice", b"secret")
    env["blob"] = env["blob"][:-4] + ("AAAA" if not env["blob"].endswith("AAAA") else "BBBB")
    with pytest.raises(RoomError):
        store.open_message(room, "alice", env)


def test_cross_room_transplant_refused(store):
    r1 = store.create_room("one", "alice")["room_id"]
    r2 = store.create_room("two", "alice")["room_id"]
    env = store.seal_message(r1, "alice", b"room one secret")
    with pytest.raises(RoomError):
        store.open_message(r2, "alice", env)


# -- (d) re-key actually changes the room key --------------------------------

def test_rekey_changes_key_bytes(store, room):
    k0 = store._epoch_key_bytes(room, 0)
    store.add_member(room, "bob", by_admin="alice")
    k1 = store._epoch_key_bytes(room, 1)
    assert k0 != k1
    assert len(k1) == 32
    store.remove_member(room, "bob", by_admin="alice")
    k2 = store._epoch_key_bytes(room, 2)
    assert k2 not in (k0, k1)


# -- (e) non-member seal/open refused -----------------------------------------

def test_non_member_refused(store, room):
    with pytest.raises(NotMemberError):
        store.seal_message(room, "mallory", b"intruder")
    env = store.seal_message(room, "alice", b"members only")
    with pytest.raises(NotMemberError):
        store.open_message(room, "mallory", env)


# -- public rooms: join primitive ----------------------------------------------

def test_public_room_join(store):
    rid = store.create_room("lobby", "alice", public=True)["room_id"]
    assert store.get_room(rid)["public"] is True
    store.join_room(rid, "dave")
    env = store.seal_message(rid, "dave", b"hello lobby")
    assert store.open_message(rid, "alice", env)["plaintext"] == b"hello lobby"


def test_private_room_join_refused(store, room):
    with pytest.raises(NotAdminError):
        store.join_room(room, "mallory")


def test_public_flag_is_just_a_property(store):
    # Public changes nothing about the crypto: still sealed, membership
    # is still the boundary.
    rid = store.create_room("lobby", "alice", public=True)["room_id"]
    env = store.seal_message(rid, "alice", b"sealed even when public")
    with pytest.raises(NotMemberError):
        store.open_message(rid, "stranger", env)


# -- devices + revocation -------------------------------------------------------

def test_device_revocation(store, room):
    store.register_device(room, "alice", "alice-laptop", by="alice")
    env = store.seal_message(room, "alice", b"from laptop", device_id="alice-laptop")
    assert store.open_message(room, "alice", env)["device_id"] == "alice-laptop"
    epoch_before = store.get_room(room)["epoch"]
    store.revoke_member_device(room, "alice", "alice-laptop", by_admin="alice")
    assert store.get_room(room)["epoch"] == epoch_before + 1  # revocation re-keys
    with pytest.raises(RoomError):
        store.seal_message(room, "alice", b"pwned?", device_id="alice-laptop")
    # The pre-revocation envelope sealed from that device still opens
    # (history), but a forged post-revocation envelope from it is refused.
    late = store.seal_message(room, "alice", b"after revoke", device_id="alice-phone")
    late["device_id"] = "alice-laptop"  # transplant onto the revoked device
    with pytest.raises(RoomError):
        store.open_message(room, "alice", late)


def test_unregistered_device_refused(store, room):
    with pytest.raises(RoomError):
        store.seal_message(room, "alice", b"x", device_id="ghost-device")


# -- persistence ---------------------------------------------------------------

def test_state_persists_across_instances(tmp_path):
    _open_gate(tmp_path)
    s1 = RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    rid = s1.create_room("durable", "alice")["room_id"]
    s1.add_member(rid, "bob", by_admin="alice")
    env = s1.seal_message(rid, "bob", b"persist me")
    s2 = RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    assert s2.get_room(rid)["epoch"] == 1
    assert s2.open_message(rid, "alice", env)["plaintext"] == b"persist me"


def test_wrong_passphrase_refused(tmp_path):
    _open_gate(tmp_path)
    RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    with pytest.raises(RoomError):
        RoomStore("wrong passphrase", home=tmp_path)


def test_lock_unlock(tmp_path):
    _open_gate(tmp_path)
    s = RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    rid = s.create_room("lockable", "alice")["room_id"]
    s.lock()
    assert s.is_locked
    with pytest.raises(RoomError):
        s.seal_message(rid, "alice", b"x")
    s.unlock(_TEST_PASSPHRASE)
    assert not s.is_locked
    env = s.seal_message(rid, "alice", b"back")
    assert s.open_message(rid, "alice", env)["plaintext"] == b"back"


def test_owner_only_permissions(tmp_path):
    _open_gate(tmp_path)
    s = RoomStore(_TEST_PASSPHRASE, home=tmp_path)
    rid = s.create_room("perms", "alice")["room_id"]
    import os as _os
    import stat as _stat
    rooms_dir = tmp_path / ".levi" / "voidbox" / "rooms"
    assert _stat.S_IMODE(_os.stat(rooms_dir).st_mode) == 0o700
    assert _stat.S_IMODE(_os.stat(rooms_dir / (rid + ".json")).st_mode) == 0o600


# -- laws -----------------------------------------------------------------------

def test_laws_structure():
    ids = [lid for lid, _ in LAWS]
    assert ids == ["L%d" % i for i in range(1, 11)]


def test_verify_laws_all_hold(store, room):
    store.add_member(room, "bob", by_admin="alice")
    store.register_device(room, "bob", "bob-phone", by="bob")
    store.seal_message(room, "alice", b"traffic")
    store.revoke_member_device(room, "bob", "bob-phone", by_admin="alice")
    store.remove_member(room, "bob", by_admin="alice")
    results = store.verify_laws()
    assert len(results) == 10
    failed = [(lid, detail) for lid, ok, detail in results if not ok]
    assert not failed, failed


def test_check_invariants(tmp_path):
    _open_gate(tmp_path)
    results = check_invariants(home=tmp_path)
    failed = [(name, detail) for name, ok, detail in results if not ok]
    assert not failed, failed


def test_crypto_report_names_backend(store):
    rep = store.crypto_report()
    assert rep["envelope_aead"] in ("aes-256-gcm", "stdlib-fallback")
    assert rep["protocol_version"] == 1
    assert len(rep["laws"]) == 10


def test_rejoin_keeps_old_copies_and_laws_hold(store, room):
    store.add_member(room, "bob", by_admin="alice")
    store.remove_member(room, "bob", by_admin="alice")
    store.add_member(room, "bob", by_admin="alice")  # rejoin
    env = store.seal_message(room, "alice", b"welcome back")
    assert store.open_message(room, "bob", env)["plaintext"] == b"welcome back"
    failed = [(lid, d) for lid, ok, d in store.verify_laws() if not ok]
    assert not failed, failed
