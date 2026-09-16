"""Hermetic tests for levi.presence (loopback sockets only, tmp HOME)."""

import json
import socket
import time

import pytest

from levi.presence import SHELF
from levi.presence.discovery import (
    Beacon,
    BeaconListener,
    BeaconSender,
    send_beacon,
)
from levi.presence.rooms import RoomBook, new_id
from levi.presence.server import PresenceHub


# ---------------------------------------------------------------------------
# RoomBook: pure state machine
# ---------------------------------------------------------------------------


def _book_with_two():
    book = RoomBook()
    alice = book.register("alice")
    bob = book.register("bob")
    assert book.create_room("lounge", topic="chill")[0]
    assert book.join(alice, "lounge")[0]
    assert book.join(bob, "lounge")[0]
    return book, alice, bob


def test_shelf_shape():
    assert SHELF["name"] == "presence"
    assert SHELF["summary"] and SHELF["items"]


def test_create_duplicate_and_empty():
    book = RoomBook()
    assert book.create_room("lounge")[0]
    ok, msg = book.create_room("lounge")
    assert not ok and "already exists" in msg
    ok, _ = book.create_room("   ")
    assert not ok


def test_join_unknown_room_and_client():
    book = RoomBook()
    cid = book.register("alice")
    ok, msg = book.join(cid, "nowhere")
    assert not ok and "no such room" in msg
    book.create_room("lounge")
    ok, msg = book.join("bogus-id", "lounge")
    assert not ok and "hello first" in msg


def test_join_emits_presence_event_to_others():
    book, alice, _bob = _book_with_two()
    carol = book.register("carol")
    ok, (event, recipients) = book.join(carol, "lounge")
    assert ok
    assert event["event"] == "presence" and event["state"] == "joined"
    assert event["name"] == "carol"
    assert set(recipients) == {alice, _bob}  # joiner is not notified of self


def test_post_fans_out_to_members_only():
    book, alice, bob = _book_with_two()
    ok, (message, recipients) = book.post(alice, "lounge", "hello all")
    assert ok
    assert message["event"] == "message"
    assert message["from"] == "alice" and message["text"] == "hello all"
    assert recipients == [bob]


def test_post_requires_membership():
    book = RoomBook()
    cid = book.register("mallory")
    book.create_room("lounge")
    ok, msg = book.post(cid, "lounge", "sneaky")
    assert not ok and "join" in msg


def test_post_rejects_empty_and_oversize():
    book, alice, _ = _book_with_two()
    assert not book.post(alice, "lounge", "   ")[0]
    assert not book.post(alice, "lounge", "x" * 4001)[0]


def test_leave_and_disconnect_emit_left():
    book, alice, bob = _book_with_two()
    ok, (event, recipients) = book.leave(alice, "lounge")
    assert ok and event["state"] == "left" and recipients == [bob]
    events = book.disconnect(bob)
    assert len(events) == 1
    assert events[0][0]["state"] == "left"


def test_sweep_times_out_idle_members():
    book = RoomBook()
    cid = book.register("ghost")
    book.create_room("lounge")
    book.join(cid, "lounge")
    events = book.sweep(idle_seconds=-1)  # everything is idle
    assert len(events) == 1
    event, _recipients = events[0]
    assert event["state"] == "timeout" and event["name"] == "ghost"
    ok, members = book.room_members("lounge")
    assert ok and members == []


def test_heartbeat_and_touch_keep_member_alive():
    book = RoomBook()
    cid = book.register("alice")
    book.create_room("lounge")
    book.join(cid, "lounge")
    book.heartbeat(cid)
    book.touch(cid, "lounge")
    assert book.sweep(idle_seconds=3600) == []


# ---------------------------------------------------------------------------
# PresenceHub: real sockets on loopback
# ---------------------------------------------------------------------------


class _Client:
    """Minimal JSON-lines client for hub tests."""

    def __init__(self, hub: PresenceHub, name: str):
        host, port = hub.address
        self.sock = socket.create_connection((host, port), timeout=5.0)
        self.sock.settimeout(5.0)
        self._buf = b""
        self.id = self._req({"op": "hello", "name": name})["client_id"]

    def _req(self, obj):
        self.sock.sendall((json.dumps(obj) + "\n").encode())
        return self._read_one()

    def _read_one(self):
        while b"\n" not in self._buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise AssertionError("connection closed")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode())

    def op(self, obj):
        return self._req(obj)

    def read_event(self):
        """Read the next server push (skips nothing; caller owns framing)."""
        return self._read_one()

    def close(self):
        self.sock.close()


@pytest.fixture()
def hub():
    h = PresenceHub("127.0.0.1", 0).start()
    yield h
    h.stop()


def test_hub_two_clients_exchange_messages(hub):
    alice = _Client(hub, "alice")
    bob = _Client(hub, "bob")
    assert alice.op({"op": "create", "room": "lounge"})["ok"]
    assert alice.op({"op": "join", "room": "lounge"})["ok"]
    assert bob.op({"op": "join", "room": "lounge"})["ok"]
    # bob's join produced a presence push to alice; drain it.
    evt = alice.read_event()
    assert evt["event"] == "presence" and evt["state"] == "joined"
    assert alice.op({"op": "say", "room": "lounge", "text": "hi bob"})["ok"]
    got = bob.read_event()
    assert got["event"] == "message"
    assert got["from"] == "alice" and got["text"] == "hi bob"
    alice.close()
    bob.close()


def test_hub_presence_join_and_disconnect(hub):
    alice = _Client(hub, "alice")
    bob = _Client(hub, "bob")
    alice.op({"op": "create", "room": "lounge"})
    alice.op({"op": "join", "room": "lounge"})
    bob.op({"op": "join", "room": "lounge"})
    evt = alice.read_event()
    assert evt["event"] == "presence" and evt["name"] == "bob"
    bob.close()
    time.sleep(0.5)  # let the server notice the closed socket
    evt = alice.read_event()
    assert evt["event"] == "presence" and evt["state"] == "left"
    alice.close()


def test_hub_rejects_say_before_join(hub):
    alice = _Client(hub, "alice")
    alice.op({"op": "create", "room": "lounge"})
    resp = alice.op({"op": "say", "room": "lounge", "text": "nope"})
    assert resp["ok"] is False and "join" in resp["error"]
    resp = alice.op({"op": "frobnicate"})
    assert resp["ok"] is False
    alice.close()


def test_hub_who_lists_members(hub):
    alice = _Client(hub, "alice")
    alice.op({"op": "create", "room": "lounge", "topic": "t"})
    alice.op({"op": "join", "room": "lounge"})
    resp = alice.op({"op": "who", "room": "lounge"})
    assert resp["ok"] and [m["name"] for m in resp["members"]] == ["alice"]
    alice.close()


# ---------------------------------------------------------------------------
# Discovery: beacons over loopback UDP
# ---------------------------------------------------------------------------


def _free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_beacon_roundtrip_and_expiry():
    port = _free_udp_port()
    listener = BeaconListener(bind=("127.0.0.1", port), ttl=0.4).start()
    try:
        beacon = Beacon(
            hub_id=new_id("hub"),
            name="test-hub",
            host="127.0.0.1",
            port=1234,
            rooms=["lounge"],
        )
        send_beacon(beacon, targets=[("127.0.0.1", port)])
        deadline = time.time() + 3
        peers = []
        while time.time() < deadline and not peers:
            time.sleep(0.05)
            peers = listener.peers()
        assert len(peers) == 1
        assert peers[0].name == "test-hub" and peers[0].rooms == ["lounge"]
        time.sleep(0.6)  # past the 0.4s TTL
        assert listener.peers() == []
    finally:
        listener.stop()


def test_beacon_ignores_garbage_and_wrong_magic():
    port = _free_udp_port()
    listener = BeaconListener(bind=("127.0.0.1", port), ttl=5.0).start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("127.0.0.1", port))
        s.send(b"not json at all")
        s.send(json.dumps({"magic": "nope"}).encode())
        s.close()
        time.sleep(0.3)
        assert listener.peers() == []
    finally:
        listener.stop()


def test_beacon_sender_thread_announces(hub):
    port = _free_udp_port()
    listener = BeaconListener(bind=("127.0.0.1", port), ttl=5.0).start()
    host, hub_port = hub.address
    sender = BeaconSender(
        Beacon(
            hub_id=new_id("hub"), name="sender-hub", host="127.0.0.1", port=hub_port
        ),
        targets=[("127.0.0.1", port)],
        interval=0.1,
    )
    try:
        sender.start()
        deadline = time.time() + 3
        peers = []
        while time.time() < deadline and not peers:
            time.sleep(0.05)
            peers = listener.peers()
        assert [p.name for p in peers] == ["sender-hub"]
    finally:
        sender.stop()
        listener.stop()


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero(capsys):
    from levi.presence.__main__ import main

    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_cli_default_name_from_tmp_home(monkeypatch, tmp_path):
    import levi.presence.__main__ as cli

    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".levi" / "presence"
    cfg.mkdir(parents=True)
    (cfg / "config.json").write_text(json.dumps({"display_name": "TestUser"}))
    assert cli.default_name() == "TestUser"


def test_cli_rooms_and_create_and_say(hub, capsys):
    from levi.presence.__main__ import main

    host, port = hub.address
    h, p = str(host), str(port)
    assert (
        main(
            ["create", "--host", h, "--port", p, "--room", "lounge", "--topic", "chill"]
        )
        == 0
    )
    assert main(["rooms", "--host", h, "--port", p]) == 0
    out = capsys.readouterr().out
    assert "lounge" in out
    assert (
        main(
            [
                "say",
                "--host",
                h,
                "--port",
                p,
                "--room",
                "lounge",
                "--name",
                "cli-tester",
                "hello",
                "world",
            ]
        )
        == 0
    )
    assert "sent to #lounge" in capsys.readouterr().out
    # say to a missing room fails honestly
    assert main(["say", "--host", h, "--port", p, "--room", "nowhere", "x"]) == 1


class _FakeHandler:
    """Minimal handler double: dispatch paths only need _send."""

    def __init__(self):
        self.sent = []

    def _send(self, obj):
        self.sent.append(obj)


def test_stale_close_does_not_evict_reattached_client(hub):
    """Regression: the CLI hello handshake uses two connections (one-shot
    hello, then a persistent socket re-sending hello with the client_id).
    If the first connection's teardown runs AFTER the second hello
    re-registered the client, the client must survive — previously the late
    teardown deleted it and the next op failed 'unknown client'."""
    old, new = _FakeHandler(), _FakeHandler()
    cid = hub.dispatch(old, None, {"op": "hello", "name": "alice"})
    assert (
        hub.dispatch(new, None, {"op": "hello", "name": "alice", "client_id": cid})
        == cid
    )
    hub.client_gone(old, cid)  # stale first connection tears down late
    hub.dispatch(new, cid, {"op": "create", "room": "lounge"})
    hub.dispatch(new, cid, {"op": "join", "room": "lounge"})
    hub.dispatch(new, cid, {"op": "say", "room": "lounge", "text": "hi"})
    assert new.sent[-1]["ok"] is True


def test_genuine_close_still_disconnects(hub):
    old = _FakeHandler()
    cid = hub.dispatch(old, None, {"op": "hello", "name": "bob"})
    hub.dispatch(old, cid, {"op": "create", "room": "lounge"})
    hub.client_gone(old, cid)  # the attached connection really went away
    ok, err = hub.book.post(cid, "lounge", "hi")
    assert ok is False and "unknown client" in err
