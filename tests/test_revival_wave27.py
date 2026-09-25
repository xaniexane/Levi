"""Tests for revival wave 27: offline-networks-a."""

import pytest

from core.levi.revival import batch_pull_reader as bpr
from core.levi.revival import dead_air_channel as dac
from core.levi.revival import fidonet_spool as fido
from core.levi.revival import narrowband_mailbox as nbm
from core.levi.revival import parasitic_overlay as pov
from core.levi.revival import store_forward_net as sfn


# --- dead_air_channel -------------------------------------------------------


def test_frame_encode_decode_roundtrip():
    f = dac.Frame(
        channel="ch", payload_id="p1", seq=0, total=2, data=b"hello", priority=3
    )
    g = dac.Frame.decode(f.encode())
    assert g.payload_id == "p1" and g.data == b"hello" and g.priority == 3


def test_frame_decode_rejects_tampered():
    f = dac.Frame(channel="ch", payload_id="p1", seq=0, total=1, data=b"abc")
    raw = bytearray(f.encode())
    raw[-3] ^= 0xFF
    with pytest.raises(ValueError):
        dac.Frame.decode(bytes(raw))


def test_carousel_priority_ordering():
    s = dac.DeadAirScheduler()
    s.add_window(dac.DeadAirWindow("tv", 60, 300, frames_per_minute=10))
    s.submit(dac.Payload("low", b"x" * 300, priority=0))
    s.submit(dac.Payload("high", b"y" * 300, priority=9))
    order = s.carousel()
    assert order[0].payload_id == "high"


def test_listener_reassembles_full_window_and_reports_missing():
    s = dac.DeadAirScheduler()
    s.add_window(dac.DeadAirWindow("tv", 0, 60, frames_per_minute=100))
    s.submit(dac.Payload("news", b"n" * 500, frame_size=100))  # 5 frames
    full, missing = s.listen("tv", 0, 60)
    assert full["news"] == b"n" * 500
    assert missing["news"] == 0
    partial, missing2 = s.listen("tv", 0, 0)  # listened to nothing
    assert "news" not in partial and missing2["news"] == 5


def test_window_rejects_bad_hours():
    with pytest.raises(ValueError):
        dac.DeadAirWindow("tv", 300, 60)


# --- batch_pull_reader ------------------------------------------------------


def _reader():
    r = bpr.BatchPullReader(baud=300, page_chars=50)
    r.register(bpr.Topic("weather", lambda: "sunny " * 40, max_chars=500))
    r.register(bpr.Topic("news", lambda: "headline " * 40, max_chars=500))
    return r


def test_pull_compiles_queued_topics_and_drains():
    r = _reader()
    r.request("weather")
    r.request("news")
    r.request("weather")  # duplicate ignored
    b = r.pull()
    assert b.request_id == "pull-0001"
    assert {p.topic for p in b.pages} == {"weather", "news"}
    assert r.queued == []


def test_baud_estimate_math():
    r = _reader()
    r.request("weather")
    b = r.pull()
    assert b.estimate_seconds() == pytest.approx(b.chars * 10 / 300)


def test_stream_replays_all_page_text():
    r = _reader()
    r.request("news")
    b = r.pull()
    text = "".join(b.stream(chunk_chars=37))
    assert "headline" in text and "--- p1 [news] ---" in text


def test_unknown_topic_rejected():
    r = _reader()
    with pytest.raises(KeyError):
        r.request("sports")


# --- store_forward_net ------------------------------------------------------


def _tree():
    n = sfn.TreeNetwork()
    n.add_node("root")
    n.add_node("a", parent="root")
    n.add_node("b", parent="root")
    n.add_node("a1", parent="a")
    return n


def test_single_path_routing_next_hop():
    n = _tree()
    assert n.next_hop("a1", "b") == "a"
    assert n.next_hop("root", "a1") == "a"
    assert n.next_hop("a", "a1") == "a1"


def test_store_and_forward_delivery_with_trace():
    n = _tree()
    n.send(sfn.Message("m1", "a1", "b", "hello"))
    ticks = n.drain()
    inbox = n.collect("b")
    assert len(inbox) == 1 and inbox[0].body == "hello"
    assert inbox[0].trace == ["a1", "a", "root", "b"]
    assert ticks == 3


def test_hop_limit_drops_and_records():
    n = _tree()
    n.send(sfn.Message("m2", "a1", "b", "x", hops_left=1))
    n.drain()
    assert n.collect("b") == []
    assert len(n.dropped) == 1 and n.dropped[0][1] == "hop limit exhausted"


def test_trickle_gateway_respects_byte_budget():
    g = sfn.TrickleGateway(bytes_per_tick=10)
    g.submit(sfn.Message("g1", "x", "y", "12345"))
    g.submit(sfn.Message("g2", "x", "y", "123456789012345"))
    first = g.tick()
    assert [m.msg_id for m in first] == ["g1"]  # g2 (15B) doesn't fit the budget
    second = g.tick()
    assert [m.msg_id for m in second] == ["g2"]


def test_file_server_answers_get_by_mail():
    fs = sfn.FileServer("fs", {"readme.txt": "hello file"})
    reply = fs.handle(sfn.Message("q1", "a1", "fs", "GET readme.txt"))
    assert reply is not None and reply.body == "hello file"
    assert fs.handle(sfn.Message("q2", "a1", "fs", "HELLO")) is None


# --- narrowband_mailbox -----------------------------------------------------


def _net():
    net = nbm.MailboxNetwork(packet_size=10)
    net.create_mailbox("alice")
    net.create_mailbox("bob")
    return net


def test_send_fragments_and_login_reassembles():
    net = _net()
    text = "this is a long message over narrowband"
    net.send("alice", "bob", text)
    assert net.pending("bob") == 1
    got = net.login("bob")
    assert len(got) == 1
    assert got[0].reassemble() == text
    assert len(got[0].packets) == 4  # 38 chars / 10 per packet
    assert net.pending("bob") == 0  # drained on login


def test_login_priority_order():
    net = _net()
    net.send("alice", "bob", "low", priority=0)
    net.send("alice", "bob", "urgent", priority=9)
    got = net.login("bob")
    assert [m.reassemble() for m in got] == ["urgent", "low"]


def test_push_notifies_on_arrival():
    net = _net()
    seen = []
    net.on_push("bob", lambda m: seen.append(m.msg_id))
    mid = net.send("alice", "bob", "ping")
    assert seen == [mid]


def test_purge_read_frees_storage():
    net = _net()
    net.send("alice", "bob", "a")
    net.send("alice", "bob", "b")
    net.login("bob")
    assert net.purge_read("bob") == 2
    assert net.purge_read("bob") == 0


# --- parasitic_overlay ------------------------------------------------------


def test_overlay_sends_when_channels_idle():
    o = pov.ParasiticOverlay(channel_count=2, slot_capacity=4, hold_ticks=1)
    o.enqueue(pov.Packet("p1", 8))
    o.enqueue(pov.Packet("p2", 4))
    for _ in range(3):
        o.tick([False, False])
    assert o.packets_sent == 2
    assert o.pending() == 0


def test_voice_preempts_and_packet_returns_to_head():
    o = pov.ParasiticOverlay(channel_count=1, slot_capacity=4, hold_ticks=1)
    o.enqueue(pov.Packet("big", 100))
    o.enqueue(pov.Packet("small", 4))
    o.tick([False])  # big starts on the channel
    assert o.pending() == 2  # small queued + big in flight
    o.tick([True])  # landlord takes the channel: preemption
    assert o.packets_preempted == 1
    assert o.queue[0].packet_id == "big"  # yielded packet returns to head
    assert o.pending() == 2
    rep = o.report()
    assert rep["packets_preempted"] == 1.0


def test_hold_threshold_ignores_flapping_idle():
    o = pov.ParasiticOverlay(channel_count=1, slot_capacity=100, hold_ticks=3)
    o.enqueue(pov.Packet("p1", 10))
    o.tick([False])
    o.tick([False])
    assert o.packets_sent == 0  # only 2 idle ticks, needs 3
    o.tick([False])
    assert o.packets_sent == 1


def test_voice_trace_length_must_match():
    o = pov.ParasiticOverlay(channel_count=2)
    with pytest.raises(ValueError):
        o.tick([False])


# --- fidonet_spool ----------------------------------------------------------


def _pair():
    a = fido.FidoNode("1:1/1")
    b = fido.FidoNode("1:1/2")
    a.add_nodelist(fido.NodeEntry("1:1/2", dial="555-0101", name="peer-b"))
    b.add_nodelist(fido.NodeEntry("1:1/1", dial="555-0102", name="peer-a"))
    return a, b


def test_netmail_spooled_then_exchanged_in_mail_hour():
    a, b = _pair()
    a.write_netmail("1:1/2", "hi", "hello b")
    assert a.spool_depth() == {"1:1/2": 1}
    events = a.mail_hour(b)
    assert any("dial 1:1/2 via 555-0101" in e for e in events)
    assert a.spool_depth() == {}
    assert len(b.inbox) == 1 and b.inbox[0].body == "hello b"


def test_mail_hour_requires_nodelist_entry():
    a, b = _pair()
    c = fido.FidoNode("1:1/3")
    with pytest.raises(KeyError):
        a.mail_hour(c)


def test_echomail_fans_out_to_carrier():
    a, b = _pair()
    a.carry("LEVI")
    b.carry("LEVI")
    a.write_echomail("LEVI", "announce", "echo hello")
    assert a.spool_depth().get("1:1/2") == 1
    a.mail_hour(b)
    assert any(m.subject == "announce" for m in b.echo_areas["LEVI"])


def test_misaddressed_netmail_held_for_onward_routing():
    a, b = _pair()
    b.add_nodelist(fido.NodeEntry("1:1/3", dial="555-0103"))
    a.write_netmail("1:1/3", "fwd", "for c")
    # force it into b's hands as if dialed there
    pkt = a.bundle_for("1:1/3")
    b.receive(
        fido.BundlePacket(sender_node="1:1/1", dest_node="1:1/2", mails=pkt.mails)
    )
    assert b.inbox == []
    assert b.spool_depth().get("1:1/3") == 1
