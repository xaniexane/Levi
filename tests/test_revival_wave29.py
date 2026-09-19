"""Tests for levi.revival wave 29 (protocols-a): binary command protocols,
circuits vs datagrams. Hermetic: no network, no wall clock."""

from __future__ import annotations

import pytest

from levi.revival.host_micro_iface import (
    OP_DRAW,
    OP_GET,
    OP_LIST,
    OP_RUN,
    OP_SET,
    STATUS_ERR,
    STATUS_OK,
    Command,
    HostIface,
    Response,
)
from levi.revival.coloured_books import (
    BlueBook,
    Directory,
    GreenBook,
    GreyBook,
    MailMessage,
    NRSName,
    RedBook,
    Transport,
)
from levi.revival.x25_circuit import (
    Network,
    Packet,
    X121Address,
)
from levi.revival.datagram_net import (
    Datagram,
    DatagramNet,
    ReliableEndpoint,
)
from levi.revival.oscar_presence import (
    CH_MESSAGE,
    CH_NOTIFY,
    K_MSG,
    K_PRESENCE,
    STATUS_AWAY,
    Frame,
    PresenceServer,
)
from levi.revival.ymsg_protocol import (
    STATUS_ERR as YMSG_ERR,
    STATUS_OK as YMSG_OK,
    SVC_MESSAGE,
    Packet as YPacket,
    PollingClient,
    YMsgServer,
)


# ---------------------------------------------------------------------------
# host_micro_iface
# ---------------------------------------------------------------------------


def _roundtrip(host: HostIface, opcode: int, args: list) -> Response:
    return Response.decode(host.handle(Command(opcode, args).encode()))


def test_hmi_get_set_list_roundtrip():
    host = HostIface()
    assert _roundtrip(host, OP_SET, ["greeting", "hello"]).status == STATUS_OK
    resp = _roundtrip(host, OP_GET, ["greeting"])
    assert resp.status == STATUS_OK and resp.values == ["hello"]
    listed = _roundtrip(host, OP_LIST, [])
    assert listed.values == ["greeting"]
    missing = _roundtrip(host, OP_GET, ["nope"])
    assert missing.status == STATUS_ERR


def test_hmi_run_procedure():
    host = HostIface()
    host.register("add", lambda a, b: a + b)
    resp = _roundtrip(host, OP_RUN, ["add", 20, 22])
    assert resp.status == STATUS_OK and resp.values == [42]
    unknown = _roundtrip(host, OP_RUN, ["missing"])
    assert unknown.status == STATUS_ERR


def test_hmi_draw_accumulates_vector_display():
    host = HostIface()
    r1 = _roundtrip(host, OP_DRAW, ["line", 0, 0, 256, 192])
    r2 = _roundtrip(host, OP_DRAW, ["text", 10, 10, "hi"])
    assert r1.values == [1] and r2.values == [2]
    assert host.display == [("line", (0, 0, 256, 192)), ("text", (10, 10, "hi"))]
    bad = _roundtrip(host, OP_DRAW, ["bitmap"])
    assert bad.status == STATUS_ERR


def test_hmi_frame_codec_and_unknown_opcode():
    cmd = Command(OP_SET, ["k", "v with ünicode", 7, b"\x00\xff"])
    assert Command.decode(cmd.encode()) == cmd
    resp = Response.decode(HostIface().handle(Command(0xFF, []).encode()))
    assert resp.status == STATUS_ERR
    garbled = Response.decode(HostIface().handle(b"junk"))
    assert garbled.status == STATUS_ERR


# ---------------------------------------------------------------------------
# coloured_books
# ---------------------------------------------------------------------------


def test_nrs_big_endian_names_and_directory():
    d = Directory()
    d.register("UK.AC.HATFIELD", "hatfield")
    d.register("UK.AC.OX", "oxford")
    assert d.lookup("uk.ac.hatfield") == "hatfield"
    assert d.sites() == ["UK.AC.HATFIELD", "UK.AC.OX"]  # country-first order
    assert NRSName.parse("UK.AC.HATFIELD").parent() == NRSName.parse("UK.AC")
    with pytest.raises(ValueError):
        NRSName.parse("not a name!")
    with pytest.raises(KeyError):
        d.lookup("UK.AC.NOWHERE")


def test_blue_book_recovers_corrupt_blocks():
    t = Transport()
    blue = BlueBook(t)
    data = b"abcdef" * 100
    blue.send_file("site", "f.txt", data)
    # corrupt one block in flight: tamper payload, keep stale crc
    msgs = t.drain("site")
    tampered = []
    victim = None
    for m in msgs:
        if m[0] == "FILE-BLOCK" and victim is None:
            victim = m[1]
            tampered.append(("FILE-BLOCK", m[1], b"XXXXXX", m[3]))
        else:
            tampered.append(m)
    for m in tampered:
        t.send("site", m)
    assert blue.missing("site") == [victim]
    blue.request_retransmit("sender", "site", [victim], data)
    assert blue.missing("site") == []
    name, got = blue.receive_file("site")
    assert name == "f.txt" and got == data


def test_grey_book_store_and_forward():
    t = Transport()
    grey = GreyBook(t)
    grey.post(MailMessage("a@x", "bob", "hi", "hello"))
    grey.post(MailMessage("c@x", "bob", "re", "again"))
    mail = grey.collect("bob")
    assert [m.subject for m in mail] == ["hi", "re"]
    assert grey.collect("bob") == []  # collecting empties the queue


def test_green_book_terminal_and_red_book_jobs():
    t = Transport()
    green = GreenBook(t)
    green.serve("host", lambda line: line.upper())
    sess = green.open("host")
    assert sess.send_line("ping") == "PING"
    assert sess.transcript == [("ping", "PING")]
    with pytest.raises(KeyError):
        green.open("nowhere")
    red = RedBook()
    jid = red.submit({"x": 21}, lambda spec: spec["x"] * 2)
    assert red.result(jid) == 42
    with pytest.raises(KeyError):
        red.result(999)


def test_suite_demo_runs():
    from levi.revival.coloured_books import demo

    out = demo()
    assert out["file"][1] == len(b"hello janet " * 20)
    assert out["echo"] == "PING"
    assert out["job"] == 42


# ---------------------------------------------------------------------------
# x25_circuit
# ---------------------------------------------------------------------------


def _two_nets(**kw):
    a = Network(**kw)
    b = Network(**kw)
    a.attach("here", "234201234567")
    b.attach("there", "311001234567")
    return a, b


def test_x25_duplex_delivery_in_order():
    a, b = _two_nets()
    a.gateway_to(b, "3110")
    caller = a.call("here", "311001234567")
    callee = b.incoming("there")
    assert len(callee) == 1
    caller.send(b"one")
    caller.send(b"two")
    assert callee[0].recv() == b"one"
    assert callee[0].recv() == b"two"
    callee[0].send(b"back")
    assert caller.recv() == b"back"


def test_x25_recovers_from_loss():
    a = Network(loss_every=2)  # drop every 2nd data packet
    a.attach("here", "234201234567")
    a.attach("there", "234209876543")
    caller = a.call("here", "234209876543")
    callee = a.incoming("there")[0]
    for word in (b"alpha", b"beta", b"gamma", b"delta"):
        caller.send(word)
    got = []
    for _ in range(40):
        a.pump(2)
        try:
            while True:
                got.append(callee.recv())
        except ValueError:
            pass
        if len(got) == 4:
            break
    assert got == [b"alpha", b"beta", b"gamma", b"delta"]
    assert a.switch.dropped > 0  # the loss policy actually fired


def test_x25_clear_and_bad_address():
    a, b = _two_nets()
    a.gateway_to(b, "3110")
    vc = a.call("here", "311001234567")
    vc.send(b"x")
    vc.clear()
    assert vc.open is False
    with pytest.raises(ValueError):
        vc.send(b"y")
    with pytest.raises(ValueError):
        X121Address("12ab")
    with pytest.raises(KeyError):
        a.call("here", "999901234567")  # unroutable DNIC


def test_x25_packet_codec_rejects_damage():
    pkt = Packet(0x03, 7, 0, 12, b"payload")
    assert Packet.decode(pkt.encode()).payload == b"payload"
    raw = bytearray(pkt.encode())
    raw[-1] ^= 0xFF
    with pytest.raises(ValueError):
        Packet.decode(bytes(raw))


# ---------------------------------------------------------------------------
# datagram_net
# ---------------------------------------------------------------------------


def test_datagram_switch_drops_on_congestion():
    net = DatagramNet(capacity=1)
    net.attach("a")
    net.attach("b")
    net.send(Datagram("a", "b", 1, b"one"))
    net.send(Datagram("a", "b", 2, b"two"))  # over capacity: dropped
    assert net.switch.dropped == 1
    assert [d.payload for d in net.inbox("b")] == [b"one"]
    net.send(Datagram("a", "nowhere", 3, b"x"))  # unroutable: dropped
    assert net.switch.dropped == 2


def test_datagram_codec_roundtrip():
    d = Datagram("src", "dst", 99, b"\x00\xff binary")
    assert Datagram.decode(d.encode()) == d


def test_reliable_endpoint_recovers_despite_drops():
    net = DatagramNet(capacity=1)  # hostile: drops constantly
    net.attach("a")
    net.attach("b")
    a = ReliableEndpoint(net, "a", "b")
    b = ReliableEndpoint(net, "b", "a")
    message = b"hosts do the work. " * 10
    a.send(message)
    for _ in range(400):
        a.pump(1)
        b.pump(1)
        if not a.pending:
            break
    assert b.receive() == message
    assert a.retransmits > 0  # the host layer did the recovering
    assert net.switch.dropped > 0


def test_reliable_endpoint_suppresses_duplicates_and_orders():
    net = DatagramNet()
    net.attach("a")
    net.attach("b")
    a = ReliableEndpoint(net, "a", "b")
    b = ReliableEndpoint(net, "b", "a")
    a.send(b"hello")
    b.pump(3)
    first = b.receive()
    # duplicate datagram arrives late: must not duplicate bytes
    dup = Datagram("a", "b", 999, __import__("struct").pack(">I", 0) + b"hello")
    net.send(dup)
    b.pump(1)
    assert first == b"hello"
    assert b.receive() == b""


# ---------------------------------------------------------------------------
# oscar_presence
# ---------------------------------------------------------------------------


def test_oscar_presence_fanout_to_watchers():
    srv = PresenceServer()
    srv.logon("alice")
    srv.logon("bob")
    srv.watch("alice", "bob")  # snapshot first
    frames = srv.inbox("alice")
    assert frames[0].kind == K_PRESENCE and frames[0].fields[1] == "online"
    srv.set_status("bob", STATUS_AWAY, "lunch")
    note = srv.inbox("alice")[0]
    assert (note.channel, note.kind) == (CH_NOTIFY, K_PRESENCE)
    assert note.fields == ["bob", "away", "lunch"]
    srv.logoff("bob")
    gone = srv.inbox("alice")[0]
    assert gone.fields[1] == "offline"


def test_oscar_message_with_away_note():
    srv = PresenceServer()
    srv.logon("alice")
    srv.logon("bob")
    srv.set_status("bob", STATUS_AWAY, "in a meeting")
    srv.send_message("alice", "bob", "call me")
    (msg,) = [f for f in srv.inbox("bob") if f.kind == K_MSG]
    assert msg.channel == CH_MESSAGE
    assert msg.fields[0] == "alice" and msg.fields[1] == "call me"
    assert "in a meeting" in msg.fields[2]
    with pytest.raises(KeyError):
        srv.send_message("alice", "carol", "hi")  # offline: refused, not queued


def test_oscar_frame_codec():
    f = Frame(CH_MESSAGE, 7, K_MSG, ["alice", "héllo"])
    assert Frame.decode(f.encode()) == f
    with pytest.raises(ValueError):
        Frame.decode(b"bogus")


# ---------------------------------------------------------------------------
# ymsg_protocol
# ---------------------------------------------------------------------------


def test_ymsg_packet_codec():
    p = YPacket(SVC_MESSAGE, YMSG_OK, 4242, [("from", "alice"), ("text", "hi ✓")])
    q = YPacket.decode(p.encode())
    assert (q.service, q.status, q.session_id) == (SVC_MESSAGE, YMSG_OK, 4242)
    assert q.get("text") == "hi ✓"
    with pytest.raises(ValueError):
        YPacket.decode(b"bogus")


def test_ymsg_login_message_flow():
    srv = YMsgServer()
    alice = PollingClient(srv)
    bob = PollingClient(srv)
    alice.login("alice")
    bob.login("bob")
    resp = alice.send("bob", "hello")
    assert resp.status == YMSG_OK
    bob.tick()
    assert bob.messages == [("alice", "hello")]
    missing = alice.send("carol", "hi")
    assert missing.status == YMSG_ERR  # offline: honest error, not silent drop


def test_ymsg_degraded_presence_is_approximate():
    srv = YMsgServer()
    alice = PollingClient(srv, stale_after=2)
    bob = PollingClient(srv)
    alice.login("alice")
    bob.login("bob")
    srv.set_presence(bob.session_id, "online")
    alice.tick()
    assert alice.presence() == {"bob": "online"}
    # bob goes silent: after enough empty polls he becomes suspect, not offline
    alice.tick()
    alice.tick()
    alice.tick()
    assert alice.presence() == {"bob": "suspect"}
