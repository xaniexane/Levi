"""Tests for levi.voidbox.messenger — the standalone messenger surface.

Hermetic: every test roots keeper state at tmp homes (no HOME writes)
and runs a REAL relay server on loopback with an ephemeral port (real
sockets, real store-and-forward — no mocks).

Proofs:
(a) two keepers (separate passphrases, separate homes) complete a
    handshake and exchange DMs through the real relay;
(b) a 3-member group round-trips, a member is removed mid-conversation,
    and the removed member's reads stop while the rest continue;
(c) a replayed envelope is rejected (group envelope opened twice;
    DM envelope re-posted on the relay);
(d) the relay store is still ciphertext-only after all traffic;
(e) the adult gate: construction and every operation raise without
    adult mode; closing the gate mid-session locks the messenger;
(f) laws: LAWS is M1..M8 in order and verify_laws() holds on a live
    messenger.
"""

import base64
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from levi.plaiground import gate
from levi.plaiground.gate import GateLockedError
from levi.voidbox.messenger import LAWS, NON_CLAIMS, Messenger
from levi.voidbox.messenger.app import MessengerError
from levi.voidbox.relay import RelayServer
from levi.voidbox.rooms import ReplayError

_TEST_PIN = "424242"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


@pytest.fixture
def relay(tmp_path):
    store_dir = tmp_path / "relay-store"
    srv = RelayServer(host="127.0.0.1", port=0, store_dir=str(store_dir)).start()
    yield srv, store_dir
    srv.stop()


@pytest.fixture
def homes(tmp_path):
    out = {}
    for kid in ("alice", "bob", "carol"):
        home = tmp_path / ("home-" + kid)
        home.mkdir()
        _open_gate(home)
        out[kid] = home
    return out


def _keeper(homes, relay, kid, passphrase=None):
    srv, _ = relay
    return Messenger(
        passphrase or ("correct horse battery staple " + kid),
        kid,
        home=homes[kid],
        relay_port=srv.port,
    )


def _pubkey(m):
    return base64.b64decode(m.my_identity()["public_key"])


def _handshake(a, b):
    """Drive a full handshake over the relay: out-of-band key exchange
    (both directions — the messenger never TOFUs a stranger's key),
    then a offers, b answers on poll, a finishes on poll."""
    a.chat.add_peer(b.keeper_id, _pubkey(b))
    b.chat.add_peer(a.keeper_id, _pubkey(a))
    a.start_dm(b.keeper_id, _pubkey(b))  # re-register is idempotent
    b.poll_inbox()
    a.poll_inbox()
    assert a.dm_status(b.keeper_id)["established"]
    assert b.dm_status(a.keeper_id)["established"]


# -- (a) DM round-trip over a real relay -------------------------------------


def test_dm_roundtrip_over_real_relay(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)

    alice.send_dm("bob", "hello bob, this is alice")
    msgs = bob.read_dm()
    assert len(msgs) == 1
    assert msgs[0]["from"] == "alice"
    assert msgs[0]["text"] == "hello bob, this is alice"

    bob.send_dm("alice", "hi alice, loud and clear")
    msgs = alice.read_dm("bob")
    assert len(msgs) == 1
    assert msgs[0]["text"] == "hi alice, loud and clear"

    # Nothing left pending for either mailbox.
    assert alice.read_dm() == []
    assert bob.read_dm() == []


def test_dm_to_unknown_peer_fails_with_remedy(relay, homes):
    alice = _keeper(homes, relay, "alice")
    with pytest.raises(MessengerError) as exc:
        alice.send_dm("stranger", "hello?")
    assert "start_dm" in str(exc.value)


def test_handshake_offer_from_unregistered_peer_is_parked(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    # Bob never registers alice's key: he gets the offer but must NOT
    # TOFU the stranger's identity key (NON_CLAIMS).
    alice.start_dm("bob", _pubkey(bob))
    result = bob.poll_inbox()
    parked = [e for e in result["events"] if e["event"] == "hs-offer-parked"]
    assert len(parked) == 1
    assert not bob.dm_status("alice")["established"]


def test_parked_offer_completes_after_late_registration(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    alice.chat.add_peer("bob", _pubkey(bob))  # alice knows bob; bob not yet
    alice.start_dm("bob", _pubkey(bob))
    result = bob.poll_inbox()
    assert any(e["event"] == "hs-offer-parked" for e in result["events"])
    assert not bob.dm_status("alice")["established"]
    # Bob registers late; the next sweep answers the deferred offer —
    # no re-send needed.
    bob.register_peer("alice", _pubkey(alice))
    result = bob.poll_inbox()
    assert any(e["event"] == "hs-answered" for e in result["events"])
    alice.poll_inbox()
    assert alice.dm_status("bob")["established"]
    assert bob.dm_status("alice")["established"]


def test_start_dm_wait_completes_handshake_in_one_process(relay, homes):
    # The single-process rule: veil_chat's ephemeral handshake key is
    # memory-only, so start_dm(wait_seconds=...) sweeps the inbox here
    # until the peer's answer arrives and finishes the handshake.
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    bob.register_peer("alice", _pubkey(alice))

    def answer():
        time.sleep(1.0)
        bob.poll_inbox()

    t = threading.Thread(target=answer, daemon=True)
    t.start()
    rec = alice.start_dm("bob", _pubkey(bob), wait_seconds=20.0)
    t.join(timeout=25)
    assert rec["established"] is True
    assert alice.dm_status("bob")["established"]
    assert bob.dm_status("alice")["established"]


def test_start_dm_wait_timeout_leaves_offer_pending(relay, homes):
    # Peer never answers: start_dm returns pending, no exception — the
    # caller decides (retry later, or re-run for a fresh offer).
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    bob.register_peer("alice", _pubkey(alice))
    rec = alice.start_dm("bob", _pubkey(bob), wait_seconds=1.0)
    assert rec["established"] is False
    assert alice.dm_status("bob")["established"] is False


def test_read_dm_and_read_group_never_swallow_each_other(relay, homes):
    # Both kinds in flight; reading one kind first must HOLD (not
    # drop) the other — then the held messages come out on the next
    # matching read.
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)
    room = alice.create_group("mixed")["room_id"]
    alice.invite(room, "bob")
    bob.poll_inbox()  # applies the room sync
    alice.send_dm("bob", "a dm")
    alice.send_group(room, "a group msg")

    assert [m["text"] for m in bob.read_dm()] == ["a dm"]
    assert [m["text"] for m in bob.read_group(room)] == ["a group msg"]

    # And the reverse order.
    alice.send_dm("bob", "dm two")
    alice.send_group(room, "group two")
    assert [m["text"] for m in bob.read_group(room)] == ["group two"]
    assert [m["text"] for m in bob.read_dm()] == ["dm two"]

    # Nothing left anywhere.
    rest = bob.poll_inbox()
    assert rest["dms"] == [] and rest["groups"] == []


def test_read_dm_peer_filter_holds_other_peers_messages(relay, homes):
    # A peer_id filter is a VIEW, not a drain: messages from other
    # peers swept in the same call must be held for the next matching
    # read, never silently dropped (the sweep already acked them).
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    carol = _keeper(homes, relay, "carol")
    _handshake(alice, bob)
    _handshake(carol, bob)
    alice.send_dm("bob", "from alice")
    carol.send_dm("bob", "from carol")

    assert [m["text"] for m in bob.read_dm(peer_id="alice")] == ["from alice"]
    # carol's message survived the filter — it was held, not lost.
    assert [m["text"] for m in bob.read_dm()] == ["from carol"]
    assert bob.read_dm() == []


def test_read_group_room_filter_holds_other_rooms_messages(relay, homes):
    # Same guarantee for read_group(room_id=...): messages from other
    # rooms are held, not dropped.
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)
    room1 = alice.create_group("one")["room_id"]
    room2 = alice.create_group("two")["room_id"]
    assert alice.invite(room1, "bob")["sync_failed"] == []
    assert alice.invite(room2, "bob")["sync_failed"] == []
    bob.poll_inbox()  # applies both room syncs
    alice.send_group(room1, "in room one")
    alice.send_group(room2, "in room two")

    assert [m["text"] for m in bob.read_group(room_id=room1)] == ["in room one"]
    assert [m["text"] for m in bob.read_group()] == ["in room two"]
    assert bob.read_group() == []


# -- (b) group round-trip, removal mid-conversation ---------------------------


@pytest.fixture
def trio(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    carol = _keeper(homes, relay, "carol")
    _handshake(alice, bob)
    _handshake(alice, carol)
    meta = alice.create_group("trio")
    room = meta["room_id"]
    assert alice.invite(room, "bob")["sync_failed"] == []
    assert alice.invite(room, "carol")["sync_failed"] == []
    bob.poll_inbox()
    carol.poll_inbox()
    return alice, bob, carol, room


def test_group_roundtrip_with_removal_mid_conversation(trio):
    alice, bob, carol, room = trio

    alice.send_group(room, "m1 from alice")
    assert [m["text"] for m in bob.read_group(room)] == ["m1 from alice"]
    assert [m["text"] for m in carol.read_group(room)] == ["m1 from alice"]

    bob.send_group(room, "m2 from bob")
    assert [m["text"] for m in alice.read_group(room)] == ["m2 from bob"]
    assert [m["text"] for m in carol.read_group(room)] == ["m2 from bob"]

    # Removal mid-conversation: re-keys, remaining members get fresh state.
    out = alice.remove(room, "bob")
    assert out["sync_failed"] == []
    carol.poll_inbox()

    alice.send_group(room, "m3 after removal")
    assert [m["text"] for m in carol.read_group(room)] == ["m3 after removal"]

    # The removed member's reads STOP: no key copy at the new epoch.
    got = bob.read_group(room)
    assert got == []
    # Honest stale-store semantic: bob was never sent the removal (no
    # sync goes to a removed member), so his local store still lists
    # him as active and his seal succeeds — under the OLD epoch key.
    # Recipients read such an envelope as old-epoch history (rooms L3
    # covers reads, not sends); the dumb-by-design relay cannot revoke
    # a key the removed member already holds.


def test_invite_without_dm_reports_not_silently_skips(relay, homes):
    alice = _keeper(homes, relay, "alice")
    _keeper(homes, relay, "bob")  # present on the relay; no DM with alice
    # No handshake with bob: invite must REPORT the unsynced member.
    meta = alice.create_group("duo")
    out = alice.invite(meta["room_id"], "bob")
    assert len(out["sync_failed"]) == 1
    assert out["sync_failed"][0]["member_id"] == "bob"


# -- (c) replay rejected -------------------------------------------------------


def test_replayed_group_envelope_rejected(trio):
    alice, bob, carol, room = trio
    alice.send_group(room, "once only")
    # Grab the raw sealed envelope off carol's mailbox BEFORE she opens
    # it (poll is a read, not a delete).
    packets = alice.transport.fetch_packets("carol", limit=50)
    sealed = [
        p["packet"]["envelope"]
        for p in packets
        if p["packet"].get("kind") == "room-sealed"
        and p["packet"].get("room_id") == room
    ]
    assert sealed, "expected a sealed group envelope on carol's mailbox"
    envelope = sealed[0]

    carol.rooms.open_message(room, "carol", envelope)  # first open: fine
    with pytest.raises(ReplayError):
        carol.rooms.open_message(room, "carol", envelope)  # replay: refused


def test_replayed_dm_envelope_rejected_on_the_relay(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)

    alice.send_dm("bob", "exactly once")
    packets = alice.transport.fetch_packets("bob", limit=50)
    dm_packets = [p for p in packets if p["packet"].get("kind") == "dm"]
    assert dm_packets, "expected a DM packet on bob's mailbox"

    assert [m["text"] for m in bob.read_dm()] == ["exactly once"]
    # Attacker re-posts the captured packet bytes to bob's mailbox.
    alice.transport.send_packet("bob", dm_packets[0]["packet"], sender="mallory")
    result = bob.poll_inbox()
    assert result["dms"] == []
    rejected = [e for e in result["events"] if e["event"] == "dm-rejected"]
    assert len(rejected) == 1


# -- (d) the relay store stays ciphertext-only ---------------------------------


def test_relay_store_is_ciphertext_only(relay, homes):
    srv, store_dir = relay
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)
    alice.send_dm("bob", "hello bob, this is alice")
    bob.read_dm()
    meta = alice.create_group("secret room")
    alice.invite(meta["room_id"], "bob")
    bob.poll_inbox()
    alice.send_group(meta["room_id"], "m1 from alice")
    bob.read_group()

    files = [p for p in store_dir.rglob("*") if p.is_file()]
    assert files, "expected the relay to have persisted mail"
    for path in files:
        data = path.read_bytes()
        for secret in (
            b"hello bob, this is alice",
            b"m1 from alice",
            b"secret room",
            b"correct horse battery staple",
        ):
            assert secret not in data, "%s leaked into %s" % (secret, path.name)


# -- (e) the adult gate ----------------------------------------------------------


def test_gate_locked_by_default(tmp_path, relay):
    srv, _ = relay
    with pytest.raises(GateLockedError):
        Messenger("pw", "zed", home=tmp_path, relay_port=srv.port)


def test_gate_closed_mid_session_locks_operations(relay, homes):
    alice = _keeper(homes, relay, "alice")
    bob = _keeper(homes, relay, "bob")
    _handshake(alice, bob)
    gate.disable_adult_mode(home=homes["alice"])
    with pytest.raises(GateLockedError):
        alice.send_dm("bob", "nope")
    with pytest.raises(GateLockedError):
        alice.poll_inbox()


# -- (f) laws --------------------------------------------------------------------


def test_laws_complete_and_hold(relay, homes):
    alice = _keeper(homes, relay, "alice")
    ids = [lid for lid, _ in LAWS]
    assert ids == ["M%d" % i for i in range(1, 9)]
    results = alice.verify_laws()
    failed = [(lid, detail) for lid, ok, detail in results if not ok]
    assert not failed, "laws failed: %s" % failed


def test_crypto_report_is_honest(relay, homes):
    alice = _keeper(homes, relay, "alice")
    rep = alice.crypto_report()
    assert rep["gate_open"] is True
    assert rep["surface"].startswith("voidbox-messenger")
    assert rep["laws"] == ["M%d" % i for i in range(1, 9)]
    assert len(rep["non_claims"]) == len(NON_CLAIMS) >= 5


def test_cli_identity_refused_with_gate_closed(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT / "core") + ":" + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "levi.voidbox.messenger",
         "identity", "--me", "zed", "--home", str(tmp_path),
         "--passphrase", "pw"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 2
    assert "adult gate" in proc.stderr.lower()
