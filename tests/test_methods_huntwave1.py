"""Hermetic tests for the hunt wave-1 methods batch.

naplps, csnet, x25, cyclades, fidonet, sysop, hollerith, nomography.
No I/O, no network; lossy channels use fixed seeds (deterministic).
"""

from __future__ import annotations

import pytest

from core.levi.methods import (
    csnet,
    cyclades,
    fidonet,
    hollerith,
    naplps,
    nomography,
    sysop,
    x25,
)


# ---- naplps ---------------------------------------------------------------


class TestNaplps:
    def test_pack_unpack_roundtrip(self):
        for x, y in [(0, 0), (1, 2), (16383, 16383), (100, 9999)]:
            packed = naplps.pack_xy(x, y)
            assert len(packed) == 6
            assert all(32 <= ord(c) <= 127 for c in packed)  # 7-bit safe
            assert naplps.unpack_xy(packed) == (x, y, 6)

    def test_pack_rejects_bad_coords(self):
        with pytest.raises(ValueError):
            naplps.pack_xy(-1, 0)
        with pytest.raises(ValueError):
            naplps.pack_xy(0, 16384)
        with pytest.raises(ValueError):
            naplps.pack_xy(1.5, 0)
        with pytest.raises(ValueError):
            naplps.unpack_xy("ABC")  # truncated

    def test_draw_opcode_roundtrip(self):
        codec = naplps.NaplpsCodec()
        codec.enter_graphics()
        ops = [
            naplps.Op(opcode="P", points=((10, 20),)),
            naplps.Op(opcode="L", points=((0, 0), (16383, 16383))),
            naplps.Op(opcode="R", points=((5, 5), (50, 60))),
            naplps.Op(opcode="A", points=((1, 1), (2, 2), (3, 3))),
            naplps.Op(opcode="C", color=17),
        ]
        stream = naplps.SO + codec.encode_all(ops)
        decoded = codec.decode(stream)
        assert decoded == ops

    def test_text_mode_roundtrip(self):
        codec = naplps.NaplpsCodec()  # starts in text mode
        op = naplps.Op(opcode="T", points=((7, 9),), text="hello")
        decoded = codec.decode(codec.encode(op))
        assert decoded == [op]

    def test_mode_switching_markers(self):
        codec = naplps.NaplpsCodec()
        assert codec.enter_graphics() == naplps.SO
        assert codec.mode == naplps.GRAPHICS
        assert codec.enter_text() == naplps.SI
        assert codec.mode == naplps.TEXT

    def test_macro_define_call_expand(self):
        codec = naplps.NaplpsCodec()
        codec.enter_graphics()
        codec.define_macro("box", [naplps.Op(opcode="R", points=((0, 0), (100, 100)))])
        stream = codec.encode(naplps.Op(opcode="M", name="box"))
        decoded = codec.decode(stream)
        assert decoded == [naplps.Op(opcode="R", points=((0, 0), (100, 100)))]

    def test_drcs_glyph(self):
        codec = naplps.NaplpsCodec()
        codec.define_glyph(0x41, ["0110", "1001", "1111", "1001"])
        assert codec.glyph(0x41) == ("0110", "1001", "1111", "1001")
        assert codec.glyph(0x42) is None

    def test_naplps_denies(self):
        codec = naplps.NaplpsCodec()
        with pytest.raises(ValueError):  # unknown opcode
            codec.encode(naplps.Op(opcode="Z", points=((1, 1),)))
        with pytest.raises(ValueError):  # wrong arity
            codec.enter_graphics()
            codec.encode(naplps.Op(opcode="L", points=((1, 1),)))
        with pytest.raises(ValueError):  # draw op in text mode
            codec.enter_text()
            codec.encode(naplps.Op(opcode="P", points=((1, 1),)))
        with pytest.raises(ValueError):  # text op in graphics mode
            codec.enter_graphics()
            codec.encode(naplps.Op(opcode="T", points=((1, 1),), text="hi"))
        with pytest.raises(ValueError):  # empty text
            codec.enter_text()
            codec.encode(naplps.Op(opcode="T", points=((1, 1),), text=""))
        with pytest.raises(ValueError):  # non-ASCII text
            codec.encode(naplps.Op(opcode="T", points=((1, 1),), text="héllo"))
        with pytest.raises(ValueError):  # color out of range
            codec.encode(naplps.Op(opcode="C", color=64))
        with pytest.raises(ValueError):  # duplicate macro
            codec.enter_graphics()
            codec.define_macro("m1", [naplps.Op(opcode="P", points=((0, 0),))])
            codec.define_macro("m1", [naplps.Op(opcode="P", points=((0, 0),))])
        with pytest.raises(ValueError):  # empty macro name
            codec.define_macro("", [naplps.Op(opcode="P", points=((0, 0),))])
        with pytest.raises(ValueError):  # macro body calls undefined macro
            codec.define_macro("m2", [naplps.Op(opcode="M", name="nope")])
        with pytest.raises(ValueError):  # encode call to undefined macro
            codec.encode(naplps.Op(opcode="M", name="nope"))
        with pytest.raises(ValueError):  # bad glyph code
            codec.define_glyph(0x19, ["1"])
        with pytest.raises(ValueError):  # malformed glyph rows
            codec.define_glyph(0x43, ["10", "1"])
        with pytest.raises(ValueError):  # truncated stream
            codec.decode("P" + naplps.pack_xy(1, 2)[:3])
        with pytest.raises(ValueError):  # unknown opcode byte in stream
            codec.decode("Z")


# ---- csnet -----------------------------------------------------------------


def _registry() -> csnet.AdapterRegistry:
    reg = csnet.AdapterRegistry()
    reg.register(
        csnet.Transport(
            id="dialup",
            name="Phonenet dial-up",
            setup_cost=0.05,
            cost_per_kb=0.5,
            reliability=0.9,
            max_kb=64,
        )
    )
    reg.register(
        csnet.Transport(
            id="x25",
            name="Telenet X.25",
            setup_cost=5.0,
            cost_per_kb=0.1,
            reliability=0.99,
            max_kb=1024,
        )
    )
    reg.register(
        csnet.Transport(
            id="arpanet",
            name="ARPANET",
            setup_cost=2.0,
            cost_per_kb=0.05,
            reliability=0.999,
            max_kb=10000,
        )
    )
    return reg


class TestCsnet:
    def test_cost_aware_route_selection(self):
        reg = _registry()
        # 10 KB at reliability >= 0.95: dialup excluded (0.9);
        # arpanet 2+0.5=2.5 beats x25 5+1=6
        assert reg.select_route(10, min_reliability=0.95).id == "arpanet"
        # reliability >= 0.995 leaves only arpanet
        assert reg.select_route(10, min_reliability=0.995).id == "arpanet"
        # 1 KB at floor 0.9: dialup 0.05+0.5=0.55 beats x25 5.1, arpanet 2.05
        assert reg.select_route(1, min_reliability=0.9).id == "dialup"
        # 100 KB: dialup excluded by capacity; arpanet 2+5=7 beats x25 5+10
        assert reg.select_route(100).id == "arpanet"

    def test_route_cost(self):
        reg = _registry()
        assert reg.route_cost("x25", 10) == pytest.approx(6.0)

    def test_tunnel_roundtrip(self):
        reg = _registry()
        payload = b"IP packet over X.25"
        frame = reg.tunnel(payload, "x25")
        assert frame.carrier_id == "x25"
        assert csnet.AdapterRegistry.untunnel(frame, reg) == payload

    def test_multiplex_batches(self):
        reg = _registry()
        sessions = [b"x" * 10240 for _ in range(5)]  # 5 x 10KB
        batches = reg.multiplex(sessions, "dialup")  # 64KB cap
        assert len(batches) == 1
        assert batches[0].sessions_saved == 4
        assert b"".join(batches[0].sessions) == b"".join(sessions)
        big = [b"y" * 40960, b"z" * 40960]  # 2 x 40KB -> 2 batches
        batches = reg.multiplex(big, "dialup")
        assert len(batches) == 2
        assert all(b.sessions_saved == 0 for b in batches)

    def test_csnet_denies(self):
        reg = _registry()
        with pytest.raises(ValueError):  # duplicate transport
            reg.register(csnet.Transport("dialup", "dup", 0, 0, 0.5, 10))
        with pytest.raises(ValueError):  # empty id
            reg.register(csnet.Transport("", "x", 0, 0, 0.5, 10))
        with pytest.raises(ValueError):  # negative cost
            reg.register(csnet.Transport("n1", "x", -1, 0, 0.5, 10))
        with pytest.raises(ValueError):  # bad reliability
            reg.register(csnet.Transport("n2", "x", 0, 0, 1.5, 10))
        with pytest.raises(ValueError):  # no transport meets floor
            reg.select_route(10, min_reliability=0.9999)
        with pytest.raises(ValueError):  # bad floor
            reg.select_route(10, min_reliability=2.0)
        with pytest.raises(ValueError):  # non-positive size
            reg.select_route(0)
        with pytest.raises(ValueError):  # unknown carrier
            reg.tunnel(b"data", "nope")
        with pytest.raises(ValueError):  # empty payload
            reg.tunnel(b"", "x25")
        with pytest.raises(ValueError):  # payload exceeds capacity
            reg.tunnel(b"x" * (65 * 1024), "dialup")
        with pytest.raises(ValueError):  # untunnel, carrier forgotten
            reg2 = csnet.AdapterRegistry()
            frame = reg.tunnel(b"data", "x25")
            csnet.AdapterRegistry.untunnel(frame, reg2)
        with pytest.raises(ValueError):  # empty sessions
            reg.multiplex([], "x25")
        with pytest.raises(ValueError):  # empty session bytes
            reg.multiplex([b""], "x25")
        with pytest.raises(ValueError):  # session exceeds capacity
            reg.multiplex([b"x" * (65 * 1024)], "dialup")
        with pytest.raises(ValueError):  # unknown carrier
            reg.multiplex([b"x"], "nope")


# ---- x25 -------------------------------------------------------------------


class TestX25:
    def test_addresses(self):
        assert x25.is_x121_address("1234")
        assert x25.is_x121_address("12345678901234")
        assert not x25.is_x121_address("123")  # too short
        assert not x25.is_x121_address("123456789012345")  # too long
        assert not x25.is_x121_address("12a4")

    def test_in_order_delivery_over_lossy_channel(self):
        vc = x25.VirtualCircuit()
        cid = vc.open("1234", "5678")
        data = bytes(range(256)) * 4  # 1024 bytes -> 8 packets
        packets = vc.send(cid, data)
        assert len(packets) == 8
        assert [p.seq for p in packets] == list(range(8))

        wire = x25.LossyChannel(loss_rate=0.3, seed=42)
        delivered = wire.deliver(packets)
        vc.ingest(cid, delivered)

        # repair loop: the network retransmits what is missing
        last = len(packets) - 1
        for _ in range(50):
            missing = vc.missing(cid, last)
            if not missing:
                break
            repairs = [vc.retransmit(cid, s) for s in missing]
            vc.ingest(cid, wire.deliver(repairs))
        assert vc.missing(cid, last) == []
        assert vc.deliver(cid) == data

    def test_in_order_prefix_only(self):
        vc = x25.VirtualCircuit()
        cid = vc.open("1234", "5678")
        packets = vc.send(cid, b"A" * 300)  # 3 packets
        # deliver only packets 1 and 2: nothing is deliverable yet
        vc.ingest(cid, [packets[1], packets[2]])
        assert vc.deliver(cid) == b""
        assert vc.missing(cid, 2) == [0]
        vc.ingest(cid, [packets[0]])
        assert vc.deliver(cid) == b"A" * 300

    def test_x25_denies(self):
        vc = x25.VirtualCircuit()
        with pytest.raises(ValueError):  # bad address
            vc.open("12", "5678")
        with pytest.raises(ValueError):  # same address
            vc.open("1234", "1234")
        cid = vc.open("1234", "5678")
        with pytest.raises(ValueError):  # duplicate open
            vc.open("5678", "1234")
        with pytest.raises(ValueError):  # empty send
            vc.send(cid, b"")
        with pytest.raises(ValueError):  # unknown circuit
            vc.send("nope", b"x")
        with pytest.raises(ValueError):  # unknown seq retransmit
            vc.retransmit(cid, 99)
        vc.send(cid, b"hello")
        vc.mark_acked(cid, 0)
        with pytest.raises(ValueError):  # retransmit acked seq
            vc.retransmit(cid, 0)
        with pytest.raises(ValueError):  # negative through_seq
            vc.missing(cid, -1)
        with pytest.raises(ValueError):  # wrong-circuit packet
            vc.ingest(cid, [x25.Packet("other", 0, b"x")])
        vc.close(cid)
        with pytest.raises(ValueError):  # send on closed circuit
            vc.send(cid, b"x")


# ---- cyclades ---------------------------------------------------------------


def _transfer(data: bytes, drop_rate: float, seed: int) -> bytes:
    a = cyclades.HostStack("A", window=4, timeout=3, mtu=64)
    b = cyclades.HostStack("B", window=4, timeout=3, mtu=64)
    wire = cyclades.DatagramChannel(drop_rate=drop_rate, seed=seed)
    a.send(data, "B")
    for _ in range(400):
        a.emit(wire)
        b.emit(wire)
        arrivals = wire.pump()
        for host in (a, b):
            mine = [d for d in arrivals if d.dst == host.addr]
            for ack in host.receive(mine):
                wire.send(ack)
    return b.read("A")


class TestCyclades:
    def test_reliable_transfer_over_unreliable_channel(self):
        data = bytes((i * 7) % 256 for i in range(500))
        assert _transfer(data, drop_rate=0.0, seed=1) == data
        assert _transfer(data, drop_rate=0.25, seed=7) == data
        assert _transfer(data, drop_rate=0.4, seed=99) == data

    def test_channel_is_unreliable(self):
        wire = cyclades.DatagramChannel(drop_rate=0.5, seed=3)
        dgs = [
            cyclades.Datagram(src="A", dst="B", seq=i, payload=b"x") for i in range(20)
        ]
        for d in dgs:
            wire.send(d)
        arrivals = wire.pump()
        seqs = sorted(d.seq for d in arrivals)
        # with 50% loss over 20 datagrams, not all arrive exactly once
        assert not (len(arrivals) == 20 and seqs == list(range(20)))

    def test_cyclades_denies(self):
        with pytest.raises(ValueError):
            cyclades.HostStack("")
        with pytest.raises(ValueError):
            cyclades.HostStack("A", window=0)
        with pytest.raises(ValueError):
            cyclades.HostStack("A", timeout=0)
        with pytest.raises(ValueError):
            cyclades.HostStack("A", mtu=0)
        with pytest.raises(ValueError):
            cyclades.DatagramChannel(drop_rate=1.5)
        with pytest.raises(ValueError):
            cyclades.DatagramChannel(capacity=0)
        h = cyclades.HostStack("A")
        with pytest.raises(ValueError):
            h.send(b"", "B")
        with pytest.raises(ValueError):
            h.send(b"x", "")
        with pytest.raises(ValueError):
            h.send(b"x", "A")  # to self
        with pytest.raises(ValueError):
            h.read("nobody")  # no such flow
        with pytest.raises(ValueError):  # misdelivered datagram
            h.receive([cyclades.Datagram(src="B", dst="C", seq=0)])
        with pytest.raises(ValueError):  # unknown kind
            h.receive([cyclades.Datagram(src="B", dst="A", seq=0, kind="??")])


# ---- fidonet ----------------------------------------------------------------


def _fed() -> fidonet.EchoFederation:
    fed = fidonet.EchoFederation()
    fed.create_echo(
        "TECH",
        charter="Technical discussion. Be excellent to each other.",
        moderator="sysop1",
        banned_words=("spam", "flamewar"),
    )
    return fed


class TestFidonet:
    def test_post_and_list(self):
        fed = _fed()
        m = fed.post("TECH", "alice", "hello echo")
        assert m.echo == "TECH" and m.author == "alice" and m.seq == 0
        assert fed.echoes() == ["TECH"]

    def test_charter_enforcement(self):
        fed = _fed()
        with pytest.raises(ValueError):
            fed.post("TECH", "mallory", "this is SPAM, buy now")

    def test_bundle_unbundle_roundtrip(self):
        fed = _fed()
        fed.post("TECH", "alice", "message one")
        fed.post("TECH", "bob", "message two")
        bundle = fed.bundle("TECH")
        fed2 = fidonet.EchoFederation()
        fed2.create_echo("TECH", charter="x", moderator="sysop1")
        assert fed2.unbundle(bundle, "TECH") == 2
        bodies = [m.body for m in fed2._echoes["TECH"].messages]
        assert bodies == ["message one", "message two"]
        # re-unbundle dedupes
        assert fed2.unbundle(bundle, "TECH") == 0

    def test_moderation_escalation(self):
        fed = _fed()
        assert fed.status("TECH", "mallory") == fidonet.MEMBER
        assert fed.warn("TECH", "mallory") == fidonet.WARNED
        assert fed.shun("TECH", "mallory") == fidonet.SHUNNED
        assert fed.delink("TECH", "mallory") == fidonet.DELINKED
        with pytest.raises(ValueError):  # shunned/delinked cannot post
            fed.post("TECH", "mallory", "let me back in")
        # pardon steps back one rung
        assert fed.pardon("TECH", "mallory") == fidonet.SHUNNED
        assert fed.pardon("TECH", "mallory") == fidonet.WARNED
        assert fed.pardon("TECH", "mallory") == fidonet.MEMBER
        fed.post("TECH", "mallory", "i am reformed")

    def test_fidonet_denies(self):
        fed = _fed()
        with pytest.raises(ValueError):  # duplicate echo
            fed.create_echo("TECH", charter="x", moderator="y")
        with pytest.raises(ValueError):  # empty name
            fed.create_echo("", charter="x", moderator="y")
        with pytest.raises(ValueError):  # empty charter
            fed.create_echo("NEW", charter="  ", moderator="y")
        with pytest.raises(ValueError):  # empty moderator
            fed.create_echo("NEW", charter="x", moderator="")
        with pytest.raises(ValueError):  # unknown echo post
            fed.post("NOPE", "a", "hi")
        with pytest.raises(ValueError):  # empty body
            fed.post("TECH", "a", "   ")
        with pytest.raises(ValueError):  # shun without warn (skip)
            fed.shun("TECH", "mallory")
        with pytest.raises(ValueError):  # delink without shun (skip)
            fed.delink("TECH", "mallory")
        fed.warn("TECH", "mallory")
        with pytest.raises(ValueError):  # double warn
            fed.warn("TECH", "mallory")
        with pytest.raises(ValueError):  # pardon of member
            fed.pardon("TECH", "alice")
        with pytest.raises(ValueError):  # malformed bundle
            fed.unbundle("not json", "TECH")
        with pytest.raises(ValueError):  # bundle for wrong echo
            fed.create_echo("OTHER", charter="x", moderator="y")
            fed.unbundle(fed.bundle("TECH"), "OTHER")
        with pytest.raises(ValueError):  # negative since
            fed.bundle("TECH", since=-1)


# ---- sysop ------------------------------------------------------------------


def _board() -> sysop.Board:
    b = sysop.Board(
        name="The Lodge",
        steward="martha",
        norms="Be kind. No warez. Upload before you leech.",
        required_ratio=0.5,
    )
    b.set_questionnaire(
        ["Why do you want to join?", "What will you contribute?"],
        min_answer_len=10,
    )
    return b


class TestSysop:
    def test_admission_rite(self):
        b = _board()
        admitted, score = b.apply(
            "alice", ["I love old machines!!", "I will upload manuals!!"]
        )
        assert admitted and score == 2
        assert b.members() == ["alice"]
        # thin answers fail the rite
        admitted, score = b.apply("bob", ["meh", "stuff"])
        assert not admitted and score == 0
        assert "bob" not in b.members()

    def test_ratio_ledger_enforcement(self):
        b = _board()
        b.apply("alice", ["I love old machines!!", "I will upload manuals!!"])
        with pytest.raises(ValueError):  # leeching before contributing
            b.record_download("alice", 10.0)
        b.record_upload("alice", 100.0)
        b.record_download("alice", 50.0)  # ratio 2.0 >= 0.5
        assert b.ratio("alice") == pytest.approx(2.0)
        with pytest.raises(ValueError):  # would drop below 0.5
            b.record_download("alice", 160.0)

    def test_sanction_ladder(self):
        b = _board()
        b.apply("mallory", ["I love old machines!!", "I will upload manuals!!"])
        assert b.sanction("mallory", sysop.WARNED) == sysop.WARNED
        assert b.sanction("mallory", sysop.SUSPENDED) == sysop.SUSPENDED
        assert b.sanction("mallory", sysop.BANNED) == sysop.BANNED
        with pytest.raises(ValueError):  # banned: no uploads
            b.record_upload("mallory", 10.0)
        assert b.pardon("mallory") == sysop.SUSPENDED
        assert b.pardon("mallory") == sysop.WARNED
        assert b.pardon("mallory") == "member"

    def test_sysop_denies(self):
        with pytest.raises(ValueError):
            sysop.Board("", "s", "norms")
        with pytest.raises(ValueError):
            sysop.Board("b", "", "norms")
        with pytest.raises(ValueError):
            sysop.Board("b", "s", "   ")
        with pytest.raises(ValueError):
            sysop.Board("b", "s", "norms", required_ratio=0)
        b = sysop.Board("b", "s", "norms")
        with pytest.raises(ValueError):  # apply before questionnaire
            b.apply("u", ["answer"])
        with pytest.raises(ValueError):  # empty questionnaire
            b.set_questionnaire([])
        with pytest.raises(ValueError):  # blank question
            b.set_questionnaire(["ok?", "  "])
        with pytest.raises(ValueError):  # bad threshold
            b.set_questionnaire(["ok?"], min_answer_len=0)
        b.set_questionnaire(["Why join?"], min_answer_len=5)
        with pytest.raises(ValueError):  # wrong answer count
            b.apply("u", ["a", "b"])
        with pytest.raises(ValueError):  # empty answer
            b.apply("u", ["   "])
        with pytest.raises(ValueError):  # empty user
            b.apply("", ["an answer"])
        b.apply("u", ["a good answer"])
        with pytest.raises(ValueError):  # double application
            b.apply("u", ["a good answer"])
        with pytest.raises(ValueError):  # negative upload
            b.record_upload("u", -1.0)
        with pytest.raises(ValueError):  # transfer by non-member
            b.record_upload("stranger", 1.0)
        with pytest.raises(ValueError):  # unknown sanction
            b.sanction("u", "exiled")
        with pytest.raises(ValueError):  # skip rungs
            b.sanction("u", sysop.BANNED)
        with pytest.raises(ValueError):  # pardon of member in good standing
            b.pardon("u")


# ---- hollerith ---------------------------------------------------------------


def _schema() -> hollerith.CardSchema:
    return hollerith.CardSchema(
        "census1890",
        [
            hollerith.Field("age", 7),  # 0..127
            hollerith.Field("sex", 1),  # 0/1
            hollerith.Field("married", 1),  # 0/1
        ],
    )


class TestHollerith:
    def test_encode_decode_roundtrip(self):
        s = _schema()
        card = s.encode({"age": 34, "sex": 1, "married": 0})
        assert s.decode(card) == {"age": 34, "sex": 1, "married": 0}
        assert card.bits < (1 << 9)

    def test_tabulate_sort_verify_pipeline(self):
        s = _schema()
        people = [
            {"age": 34, "sex": 1, "married": 1},
            {"age": 7, "sex": 0, "married": 0},
            {"age": 34, "sex": 0, "married": 0},
            {"age": 61, "sex": 1, "married": 1},
        ]
        deck = [s.encode(p) for p in people]
        counts = hollerith.tabulate(s, deck, "age")
        assert counts == {34: 2, 7: 1, 61: 1}
        by_age = hollerith.sort_pass(s, deck, "age")
        assert [s.decode(c)["age"] for c in by_age] == [7, 34, 34, 61]
        assert hollerith.verify(s, deck, "age", {34: 2, 7: 1, 61: 1}) is True
        with pytest.raises(ValueError):  # recount must match exactly
            hollerith.verify(s, deck, "age", {34: 3, 7: 1, 61: 1})

    def test_hollerith_denies(self):
        with pytest.raises(ValueError):
            hollerith.CardSchema("", [hollerith.Field("a", 1)])
        with pytest.raises(ValueError):
            hollerith.CardSchema("s", [])
        with pytest.raises(ValueError):  # duplicate field
            hollerith.CardSchema(
                "s", [hollerith.Field("a", 1), hollerith.Field("a", 1)]
            )
        with pytest.raises(ValueError):  # bad width
            hollerith.CardSchema("s", [hollerith.Field("a", 0)])
        with pytest.raises(ValueError):  # blank field name
            hollerith.CardSchema("s", [hollerith.Field("  ", 1)])
        s = _schema()
        with pytest.raises(ValueError):  # missing field
            s.encode({"age": 1, "sex": 1})
        with pytest.raises(ValueError):  # extra field
            s.encode({"age": 1, "sex": 1, "married": 0, "nope": 2})
        with pytest.raises(ValueError):  # value doesn't fit
            s.encode({"age": 200, "sex": 1, "married": 0})
        with pytest.raises(ValueError):  # negative value
            s.encode({"age": -1, "sex": 1, "married": 0})
        with pytest.raises(ValueError):  # non-int value
            s.encode({"age": "34", "sex": 1, "married": 0})
        with pytest.raises(ValueError):  # unknown field tabulate
            hollerith.tabulate(
                s, [s.encode({"age": 1, "sex": 0, "married": 0})], "nope"
            )
        with pytest.raises(ValueError):  # empty deck tabulate
            hollerith.tabulate(s, [], "age")
        with pytest.raises(ValueError):  # empty deck sort
            hollerith.sort_pass(s, [], "age")
        with pytest.raises(ValueError):  # empty deck verify
            hollerith.verify(s, [], "age", {})
        other = hollerith.CardSchema("other", [hollerith.Field("a", 2)])
        with pytest.raises(ValueError):  # card from another schema
            s.decode(other.encode({"a": 1}))


# ---- nomography ---------------------------------------------------------------


class TestNomography:
    def test_precompute_then_evaluate(self):
        table = nomography.CompiledTable(lambda x: x * x, 0.0, 10.0, n=1001)
        assert table.evaluate(3.5) == pytest.approx(12.25, abs=1e-3)
        assert table.evaluate(0.0) == pytest.approx(0.0)
        assert table.evaluate(10.0) == pytest.approx(100.0)
        # the parallel-resistor chart: 1/R = 1/R1 + 1/R2 at fixed R2
        r2 = 100.0
        chart = nomography.CompiledTable(
            lambda r1: (r1 * r2) / (r1 + r2), 1.0, 1000.0, n=2001
        )
        assert chart.evaluate(100.0) == pytest.approx(50.0, abs=0.05)

    def test_chain_concatenated_charts(self):
        inner = nomography.CompiledTable(lambda x: x**0.5, 0.0, 100.0, n=1001)
        outer = nomography.CompiledTable(lambda y: y * y, 0.0, 10.0, n=1001)
        f = nomography.chain(inner, outer)
        assert f(49.0) == pytest.approx(49.0, abs=0.05)
        assert f(2.25) == pytest.approx(2.25, abs=0.05)

    def test_two_variable_chart(self):
        table = nomography.CompiledTable2D(
            lambda x, y: x * y, 0.0, 2.0, 21, 0.0, 3.0, 21
        )
        assert table.evaluate(1.5, 2.0) == pytest.approx(3.0, abs=1e-9)
        assert table.evaluate(0.0, 0.0) == pytest.approx(0.0)
        assert table.evaluate(2.0, 3.0) == pytest.approx(6.0)

    def test_nomography_denies(self):
        with pytest.raises(ValueError):
            nomography.CompiledTable(None, 0.0, 1.0)  # not callable
        with pytest.raises(ValueError):
            nomography.CompiledTable(lambda x: x, 0.0, 1.0, n=1)
        with pytest.raises(ValueError):
            nomography.CompiledTable(lambda x: x, 5.0, 1.0)  # inverted
        with pytest.raises(ValueError):  # non-finite during compile
            nomography.CompiledTable(lambda x: float("inf"), 0.0, 1.0, n=5)
        with pytest.raises(ValueError):  # func explodes during compile
            nomography.CompiledTable(lambda x: 1 / (x - 0.5), 0.0, 1.0, n=5)
        t = nomography.CompiledTable(lambda x: x, 0.0, 1.0, n=11)
        with pytest.raises(ValueError):  # outside compiled range
            t.evaluate(1.5)
        with pytest.raises(ValueError):  # outside compiled range
            t.evaluate(-0.1)
        with pytest.raises(ValueError):
            nomography.chain(t, "not a table")
        t2 = nomography.CompiledTable2D(lambda x, y: x + y, 0.0, 1.0, 5, 0.0, 1.0, 5)
        with pytest.raises(ValueError):
            t2.evaluate(2.0, 0.5)
        with pytest.raises(ValueError):
            nomography.CompiledTable2D(lambda x, y: x, 0.0, 1.0, 1, 0.0, 1.0, 5)
