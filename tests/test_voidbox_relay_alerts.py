"""Tests for levi.voidbox.relay_alerts — Void Box as the push channel.

Hermetic: every test roots stores at tmp_path (no HOME writes). Live
tests run a real RelayServer on an ephemeral loopback port plus real
RoomStores with roomsync between keeper and phone — the full
seal -> relay -> poll -> open loop against the real interfaces. Fakes
are used only where the law under test is about isolation (relay
failure must not block SMS).

Laws under test:
  L1 fan-out complete — every alert that goes to SMS also hits the relay
  L2 relay failure never blocks SMS
  L3 unknown room = held, never misdelivered
  L4 file drops opt-in (drop roots + suffix allowlist; secrets refused)
  L5 nothing thrown away — held/failed attempts hit the relay log
"""

import json
import os

import pytest

from levi.plaiground import gate
from levi.plaiground.gate import GateLockedError
from levi.voidbox import relay_alerts
from levi.voidbox.messenger import roomsync
from levi.voidbox.relay import RelayServer
from levi.voidbox.relay_alerts import (
    FileNotAllowedError,
    UnknownRoomError,
    VoidBoxRelay,
    check_laws,
    make_relay_from_env,
)

_TEST_PIN = "424242"
_TEST_PP = "correct horse battery staple relay-alerts"


def _open_gate(home):
    gate.set_pin(_TEST_PIN, home=home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)


class FakeTransport:
    """In-memory stand-in for MessengerTransport."""

    host = "fake"
    port = 0

    def __init__(self):
        self.sent = []  # (to, packet, sender)

    def send_packet(self, to, packet, sender=None):
        self.sent.append((to, dict(packet), sender))
        return {"ok": True, "id": "fake-%d" % len(self.sent), "stored": True}

    def fetch_packets(self, recipient, limit=50):
        return []

    def ack(self, recipient, ids):
        return 0


class FailingRelay:
    def send_alert(self, room, title, body=""):
        raise RuntimeError("relay is down")


class RecordingRelay:
    def __init__(self):
        self.calls = []

    def send_alert(self, room, title, body=""):
        self.calls.append((room, title, body))
        return {"delivered_to": ["phone"]}


@pytest.fixture
def relay(tmp_path):
    _open_gate(tmp_path)
    home = tmp_path / "keeper"
    _open_gate(home)
    return VoidBoxRelay(_TEST_PP, "keeper", home=home,
                        transport=FakeTransport())


# -- laws ---------------------------------------------------------------


def test_check_laws_ok():
    report = check_laws()
    assert report["ok"], report["problems"]
    assert [lid for lid, _ in relay_alerts.LAWS] == ["L%d" % i for i in range(1, 7)]


def test_gate_locked_by_default(tmp_path):
    with pytest.raises(GateLockedError):
        VoidBoxRelay(_TEST_PP, "keeper", home=tmp_path / "h",
                     transport=FakeTransport())


def test_make_relay_from_env_none_without_passphrase(tmp_path, monkeypatch):
    _open_gate(tmp_path)
    monkeypatch.delenv("LEVI_VOIDBOX_PASSPHRASE", raising=False)
    assert make_relay_from_env(home=tmp_path) is None


# -- L3: unknown room = held --------------------------------------------


def test_unknown_room_held(relay):
    with pytest.raises(UnknownRoomError):
        relay.send_alert("no-such-room", "title", "body")
    assert relay.transport.sent == []  # nothing posted anywhere
    # L5: the hold is logged, not silently dropped
    log = (relay._state_dir / "relay_alerts.log").read_text(encoding="utf-8")
    assert "room-held" in log


def test_ensure_room_then_send(relay):
    room_id = relay.ensure_room("alerts")
    assert relay.list_rooms()["alerts"] == room_id
    report = relay.send_alert("alerts", "Hello", "world")
    assert report["title"] == "Hello"
    # keeper is the only member: nothing to fan out to, but no error
    assert report["delivered_to"] == []


def test_register_room_rejects_unknown(relay):
    with pytest.raises(relay_alerts.RelayAlertsError):
        relay.register_room("x", "room_doesnotexist")


# -- L4: file drops opt-in ----------------------------------------------


def test_file_outside_drop_root_refused(relay, tmp_path):
    relay.ensure_room("alerts")
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"0123456789")
    with pytest.raises(FileNotAllowedError):
        relay.send_file("alerts", str(outside))


def test_secret_file_refused_inside_root(relay, tmp_path):
    relay.ensure_room("alerts")
    root = tmp_path / "drops"
    root.mkdir()
    relay.register_drop_root(str(root))
    secret = root / "backup.env"
    secret.write_bytes(b"PASSWORD=hunter2")
    with pytest.raises(FileNotAllowedError):
        relay.send_file("alerts", str(secret))


def test_disallowed_suffix_refused(relay, tmp_path):
    relay.ensure_room("alerts")
    root = tmp_path / "drops"
    root.mkdir()
    relay.register_drop_root(str(root))
    exe = root / "setup.exe"
    exe.write_bytes(b"MZ...")
    with pytest.raises(FileNotAllowedError):
        relay.send_file("alerts", str(exe))


def test_allowed_file_sent(relay, tmp_path):
    room_id = relay.ensure_room("alerts")
    relay.rooms.add_member(room_id, "phone", by_admin="keeper")
    root = tmp_path / "drops"
    root.mkdir()
    relay.register_drop_root(str(root))
    blob = root / "build-1.zip"
    blob.write_bytes(os.urandom(1000))
    manifest = relay.send_file("alerts", str(blob), caption="nightly")
    assert manifest["name"] == "build-1.zip"
    assert manifest["size"] == 1000
    assert manifest["chunks"] == 1
    assert manifest["delivered_to"] == ["phone"]
    # the sealed chunk went through the (fake) transport
    assert relay.transport.sent, "chunk envelope was never posted"
    to, packet, sender = relay.transport.sent[0]
    assert to == "phone" and packet["kind"] == "room-sealed"


# -- live end-to-end: real relay + real stores + roomsync ----------------


@pytest.fixture
def live_pair(tmp_path):
    """(keeper_relay, phone_relay, server): the keeper posts, the phone
    collects — over a real RelayServer with roomsync'd room state."""
    home_a = tmp_path / "keeper"
    home_b = tmp_path / "phone"
    _open_gate(home_a)
    _open_gate(home_b)
    server = RelayServer(port=0)
    server.start()
    try:
        keeper = VoidBoxRelay(_TEST_PP, "keeper", home=home_a,
                              relay_port=server.port)
        room_id = keeper.ensure_room("alerts")
        keeper.rooms.add_member(room_id, "phone", by_admin="keeper")
        phone = VoidBoxRelay(_TEST_PP, "phone", home=home_b,
                             relay_port=server.port)
        payload = roomsync.export_room_state(keeper.rooms, room_id, "phone",
                                             home=home_a)
        roomsync.apply_room_state(phone.rooms, payload, "phone", home=home_b)
        yield keeper, phone, server
    finally:
        server.stop()


def test_live_alert_roundtrip(live_pair):
    keeper, phone, server = live_pair
    report = keeper.send_alert("alerts", "Build done", "voidbox relay is live")
    assert report["delivered_to"] == ["phone"]
    items = phone.collect("phone")
    alerts = [i for i in items if i["kind"] == "alert"]
    assert len(alerts) == 1
    assert alerts[0]["title"] == "Build done"
    assert alerts[0]["body"] == "voidbox relay is live"
    assert alerts[0]["sender"] == "keeper"
    # acked -> relay mailbox drained
    assert server.store.pending_count("phone") == 0


def test_live_file_drop_roundtrip(live_pair, tmp_path):
    keeper, phone, server = live_pair
    root = tmp_path / "drops"
    root.mkdir()
    keeper.register_drop_root(str(root))
    data = os.urandom(relay_alerts.CHUNK_BYTES * 2 + 123)
    target = root / "nightly-build.zip"
    target.write_bytes(data)
    manifest = keeper.send_file("alerts", str(target), caption="nightly")
    assert manifest["chunks"] == 3
    items = phone.collect("phone")
    chunks = [i for i in items if i["kind"] == "file-chunk"]
    assert len(chunks) == 3
    drops = phone.pending_drops()
    assert len(drops) == 1 and drops[0]["complete"]
    raw = phone.reassemble_drop(manifest["drop_id"])
    assert raw == data
    import hashlib
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]


def test_live_reassemble_incomplete_raises(live_pair):
    keeper, phone, server = live_pair
    phone._chunks["drop_x"] = {
        "manifest": {"drop_id": "drop_x", "name": "a.zip", "size": 10,
                     "sha256": "0" * 64, "caption": "", "total": 2},
        "parts": {0: b"half"},
    }
    with pytest.raises(relay_alerts.RelayAlertsError):
        phone.reassemble_drop("drop_x")


# -- alerter fan-out: L1 + L2 --------------------------------------------

from levi.device import alerter  # noqa: E402


def _drain_with(items, relay, tmp_path, monkeypatch):
    monkeypatch.setattr(alerter, "collect_new", lambda: [dict(i) for i in items])
    monkeypatch.setattr(alerter, "mark_sent", lambda uid: None)
    monkeypatch.setattr(alerter, "in_quiet_hours", lambda now=None: False)
    sms_out = []
    result = alerter.drain(
        number="15550001111",
        sms_sender=lambda number, text: sms_out.append((number, text)),
        binary_present=True,
        relay=relay,
    )
    return result, sms_out


def test_fanout_completeness_every_sms_also_relayed(tmp_path, monkeypatch):
    items = [
        {"uid": "demandpulse:k1", "source": "demandpulse",
         "title": "Opportunity", "body": "crossed threshold"},
        {"uid": "neighbor:n1", "source": "neighbor",
         "title": "Nudge", "body": "say hi"},
    ]
    rec = RecordingRelay()
    result, sms_out = _drain_with(items, rec, tmp_path, monkeypatch)
    assert [u for u in result.sent] == ["demandpulse:k1", "neighbor:n1"]
    assert [u for u in result.relayed] == ["demandpulse:k1", "neighbor:n1"]
    assert len(sms_out) == 2
    # L1: the relay saw every alert that went to SMS
    assert len(rec.calls) == 2
    assert rec.calls[0][0] == "alerts"  # default room


def test_relay_failure_never_blocks_sms(tmp_path, monkeypatch):
    items = [
        {"uid": "demandpulse:k1", "source": "demandpulse",
         "title": "Opportunity", "body": "crossed threshold"},
    ]
    result, sms_out = _drain_with(items, FailingRelay(), tmp_path, monkeypatch)
    assert result.sent == ["demandpulse:k1"]  # SMS still went out
    assert result.relayed == []
    assert len(result.relay_errors) == 1
    assert len(sms_out) == 1  # L2: degraded, logged, SMS still sends


def test_drain_without_relay_is_sms_only(tmp_path, monkeypatch):
    items = [{"uid": "x:1", "source": "x", "title": "T", "body": "B"}]
    result, sms_out = _drain_with(items, None, tmp_path, monkeypatch)
    assert result.sent == ["x:1"]
    assert result.relayed == [] and result.relay_errors == []
    assert len(sms_out) == 1


def test_relay_room_env_override(tmp_path, monkeypatch):
    items = [{"uid": "x:1", "source": "x", "title": "T", "body": "B"}]
    monkeypatch.setenv("LEVI_VOIDBOX_ALERT_ROOM", "ops")
    rec = RecordingRelay()
    _drain_with(items, rec, tmp_path, monkeypatch)
    assert rec.calls[0][0] == "ops"
