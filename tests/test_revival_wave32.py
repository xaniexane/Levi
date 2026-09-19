"""Tests for revival wave 32 — federation patterns."""

import pytest

from levi.revival import tosser_scanner as ts
from levi.revival import relay_chat as rc
from levi.revival import csnet
from levi.revival import decnet
from levi.revival import xmpp_federation as xf
from levi.revival import wave_federation as wf
from levi.revival import nodediff_gossip as ng


# --- tosser/scanner -------------------------------------------------------


def _two_nodes():
    a = ts.EchoNode("1:100/1")
    b = ts.EchoNode("1:100/2")
    for node in (a, b):
        node.create_area("LEVI")
    return a, b


def test_scan_toss_end_to_end():
    a, b = _two_nodes()
    a.post_local("LEVI", "chauncey", "hello", "first post", msgid="m1")
    scanner, tosser = ts.Scanner(), ts.Tosser()
    bundle = scanner.scan(a, uplink=b.address)
    assert len(bundle.messages) == 1
    filed, dupes, loops = tosser.toss(b, bundle)
    assert (filed, dupes, loops) == (1, 0, 0)
    assert b.areas["LEVI"].messages[0].body == "first post"
    assert a.address in b.areas["LEVI"].messages[0].seen_by


def test_scan_watermark_only_sends_new():
    a, b = _two_nodes()
    scanner = ts.Scanner()
    a.post_local("LEVI", "u", "s", "one", msgid="m1")
    assert len(scanner.scan(a, uplink=b.address).messages) == 1
    assert len(scanner.scan(a, uplink=b.address).messages) == 0
    a.post_local("LEVI", "u", "s", "two", msgid="m2")
    assert len(scanner.scan(a, uplink=b.address).messages) == 1


def test_toss_drops_duplicates_and_loops():
    a, b = _two_nodes()
    scanner, tosser = ts.Scanner(), ts.Tosser()
    a.post_local("LEVI", "u", "s", "body", msgid="m1")
    bundle = scanner.scan(a, uplink=b.address)
    assert tosser.toss(b, bundle)[0] == 1
    filed, dupes, loops = tosser.toss(b, bundle)  # re-delivery
    assert (filed, dupes, loops) == (0, 1, 0)
    # A message that already passed through b is a routing loop.
    looping = ts.Bundle(
        sender=a.address,
        recipient=b.address,
        messages=[
            ts.EchoMessage(
                msgid="m9",
                area="LEVI",
                from_user="u",
                subject="s",
                body="x",
                seen_by={b.address},
            )
        ],
    )
    filed, dupes, loops = tosser.toss(b, looping)
    assert (filed, dupes, loops) == (0, 0, 1)


# --- relay chat ------------------------------------------------------------


def _relay_net():
    net = rc.RelayNet()
    net.add_node("backbone")
    net.add_node("east", parent="backbone")
    net.add_node("west", parent="backbone")
    net.add_node("east-1", parent="east")
    for name, user in [
        ("backbone", "op"),
        ("east", "ann"),
        ("west", "bob"),
        ("east-1", "zed"),
    ]:
        net.nodes[name].add_user(user)
    return net


def test_broadcast_reaches_everyone_exactly_once():
    net = _relay_net()
    net.broadcast("east-1", "zed", "hello all")
    for name, user in [
        ("backbone", "op"),
        ("east", "ann"),
        ("west", "bob"),
        ("east-1", "zed"),
    ]:
        inbox = net.inbox_of(name, user)
        assert len(inbox) == 1
        assert inbox[0].text == "hello all"
    # Every node delivered it exactly once.
    assert sum(n.delivered for n in net.nodes.values()) == 4


def test_relay_aggregates_upstream_into_batches():
    net = _relay_net()
    leaf = net.nodes["east-1"]
    for i in range(5):
        msg = rc.RelayMessage(mid=f"x{i}", origin="east-1", user="zed", text=f"m{i}")
        leaf.upstream.enqueue(msg)
    assert leaf.upstream.pending() == 5
    batch = leaf.upstream.flush()
    assert len(batch) == 5
    assert leaf.upstream.frames_flushed == 1
    assert leaf.upstream.messages_carried == 5


def test_relay_link_accounting_scales_with_tree_not_mesh():
    net = _relay_net()
    net.broadcast("west", "bob", "ping")
    # One aggregated upstream flush per hop climbed (west->backbone),
    # not one message per destination pair.
    assert net.link_traversals == 1


# --- csnet -----------------------------------------------------------------


def _gateway():
    directory = csnet.WhitePages()
    directory.register("alice", "+15551234567", "dialup")
    directory.register("bob", "310099887766", "x25")
    directory.register("carol", "carol@mit", "arpanet")
    gw = csnet.Gateway(directory)
    gw.attach_transport(csnet.DialupTransport())
    gw.attach_transport(csnet.X25Transport())
    gw.attach_transport(csnet.ArpanetTransport())
    return gw


def test_gateway_bridges_heterogeneous_transports():
    gw = _gateway()
    d = gw.send("alice", "bob", "hello from dialup")
    assert d.body == "hello from dialup"
    assert d.via == ("dialup", "x25")
    assert gw.mailbox("bob")[0].sender == "alice"


def test_all_transport_pairs_round_trip():
    gw = _gateway()
    pairs = [("alice", "bob"), ("bob", "carol"), ("carol", "alice"), ("bob", "alice")]
    for src, dst in pairs:
        d = gw.send(src, dst, f"{src}->{dst}")
        assert d.body == f"{src}->{dst}", (src, dst)


def test_white_pages_rejects_unknown_names_and_bad_addresses():
    gw = _gateway()
    with pytest.raises(KeyError):
        gw.send("alice", "mallory", "hi")
    gw._directory.register("badline", "not-a-number", "dialup")
    with pytest.raises(ValueError):
        gw.send("badline", "bob", "x")


# --- decnet -----------------------------------------------------------------


def _mesh():
    topo = decnet.Topology()
    topo.add_link("a", "b", 1.0)
    topo.add_link("b", "c", 1.0)
    topo.add_link("a", "c", 5.0)
    net = decnet.Decnet(topo)
    for name in "abc":
        net.add_node(name)
    return net


def test_symmetric_shortest_path_routing():
    net = _mesh()
    out = net.nodes["a"].route("c", "payload")
    assert out.path == ["a", "b", "c"]  # 2.0 beats the direct 5.0 link
    back = net.nodes["c"].route("a", "reply")
    assert back.path == ["c", "b", "a"]  # symmetric: no master direction
    assert net.nodes["c"].deliveries[0].payload == "payload"
    assert net.nodes["a"].deliveries[0].payload == "reply"


def test_learning_bridge_directs_after_learning():
    bridge = decnet.LearningBridge()
    # Unknown destination floods.
    assert bridge.switch("hostA", "hostB", in_port=1, now=0.0) == []
    assert bridge.floods == 1
    # hostB answers from port 2 — bridge learns it, and hostA is already
    # known, so the reply is directed too.
    bridge.switch("hostB", "hostA", in_port=2, now=1.0)
    assert bridge.directs == 1
    # Now traffic to hostB is directed, not flooded.
    assert bridge.switch("hostA", "hostB", in_port=1, now=2.0) == [2]
    assert bridge.directs == 2
    assert bridge.floods == 1
    assert bridge.table() == {"hostA": 1, "hostB": 2}


def test_bridge_ages_stale_entries():
    bridge = decnet.LearningBridge(max_age=10.0)
    bridge.observe("hostA", 1, now=0.0)
    assert bridge.age(now=5.0) == 0
    assert bridge.age(now=11.0) == 1
    assert bridge.table() == {}


# --- xmpp federation --------------------------------------------------------


def _federated():
    directory = xf.FederationDirectory()
    a = xf.XmppServer("alpha.example", directory)
    b = xf.XmppServer("beta.example", directory)
    alice = a.add_user("alice")
    bob = b.add_user("bob")
    a.allow(alice, bob)
    b.allow(bob, alice)
    a.federate("beta.example")
    b.federate("alpha.example")
    return a, b, alice, bob


def test_open_federation_cross_server_message():
    a, b, alice, bob = _federated()
    a.send_message(alice, bob, "hello across the federation")
    msgs = b.messages_for(bob)
    assert len(msgs) == 1
    assert msgs[0].body == "hello across the federation"
    assert msgs[0].from_jid == alice


def test_federation_needs_no_prior_agreement_but_verifies_identity():
    directory = xf.FederationDirectory()
    xf.XmppServer("alpha.example", directory)
    # Any registered server can initiate: no handshake, no contract.
    c = xf.XmppServer("gamma.example", directory)
    c.federate("alpha.example")  # succeeds without alpha's involvement
    assert "alpha.example" in c.peers
    # Unknown domain cannot be federated with.
    with pytest.raises(xf.FederationError):
        c.federate("nowhere.example")


def test_spoofed_sender_domain_is_refused():
    a, b, alice, bob = _federated()
    evil_dir_holder = xf.FederationDirectory()
    evil = xf.XmppServer("evil.example", evil_dir_holder)
    # Evil crafts a stanza claiming to be from alpha.example.
    forged = xf.Stanza(kind="message", from_jid=alice, to_jid=bob, body="forged")
    with pytest.raises(xf.FederationError):
        b._receive_remote(forged, claiming_server=evil)
    assert b.refused == 1
    assert b.messages_for(bob) == []


def test_presence_propagates_across_federation():
    a, b, alice, bob = _federated()
    a.set_presence(alice, "available")
    notes = b.presence_notes_for(bob)
    assert len(notes) == 1
    assert notes[0].from_jid == alice
    assert notes[0].body == "available"


# --- wave federation --------------------------------------------------------


def test_concurrent_inserts_converge():
    d1 = wf.WaveDoc(site="a", text="hello")
    d2 = wf.WaveDoc(site="a", text="hello")
    op1 = d1.apply_local(wf.Op(kind="insert", pos=5, text=" X"))
    op2 = wf.Op(kind="insert", pos=5, text=" Y", site="b", base_version=0)
    op2r = wf.Op(kind="insert", pos=5, text=" Y", site="b", base_version=0)
    d1.integrate(op2)
    d2.apply_local(op2r)
    d2.integrate(op1)
    assert d1.text == d2.text
    assert set(d1.text.split()) >= {"hello", "X", "Y"}


def test_insert_delete_converge():
    d1 = wf.WaveDoc(site="a", text="abcdef")
    d2 = wf.WaveDoc(site="a", text="abcdef")
    ins = d1.apply_local(wf.Op(kind="insert", pos=0, text=">>"))
    dele = wf.Op(kind="delete", pos=2, length=2, site="b", base_version=0)
    dele2 = wf.Op(kind="delete", pos=2, length=2, site="b", base_version=0)
    d1.integrate(dele)
    d2.apply_local(dele2)
    d2.integrate(ins)
    assert d1.text == d2.text


def test_ops_serialize_for_the_wire():
    op = wf.Op(kind="insert", pos=3, text="hi", site="a", base_version=7)
    clone = wf.Op.from_dict(op.to_dict())
    assert clone == op


def test_wave_is_document_and_conversation():
    wave = wf.Wave("wave-1")
    root = wave.add_root("b1", "alice", text="proposal")
    r1 = wave.add_reply("b1", "b2", "bob", text="looks good")
    r2 = wave.add_reply("b2", "b3", "alice", text="shipping it")
    assert wave.thread("b3") == ["b1", "b2", "b3"]
    assert root.doc.text == "proposal"
    assert r1.replies[0] is r2
    with pytest.raises(ValueError):
        wave.add_reply("b1", "b2", "mallory")  # duplicate blip id


# --- nodediff gossip --------------------------------------------------------


def test_nodediff_computes_and_applies():
    old = ng.Nodelist(version=41)
    old.upsert(ng.NodeEntry("1:100/1", "alpha"))
    new = ng.Nodelist(version=42)
    new.upsert(ng.NodeEntry("1:100/1", "alpha-renamed"))
    new.upsert(ng.NodeEntry("1:100/2", "beta"))
    diff = ng.nodediff(old, new)
    assert len(diff.added) == 1 and len(diff.changed) == 1 and not diff.removed
    result = ng.apply_nodediff(old, diff)
    assert result.version == 42
    assert result.entries["1:100/1"].name == "alpha-renamed"
    assert "1:100/2" in result.entries


def test_identical_lists_produce_empty_diff():
    n1 = ng.Nodelist(version=5)
    n1.upsert(ng.NodeEntry("1:1/1", "x"))
    n2 = ng.Nodelist(version=6)
    n2.upsert(ng.NodeEntry("1:1/1", "x"))
    assert ng.nodediff(n1, n2).is_empty()


def test_apply_rejects_version_gap():
    n = ng.Nodelist(version=10)
    diff = ng.Nodediff(
        base_version=12, new_version=13, added=[ng.NodeEntry("9:9/9", "late")]
    )
    with pytest.raises(ValueError, match="version gap"):
        ng.apply_nodediff(n, diff)


def test_gossip_converges_along_distribution_tree():
    root_list = ng.Nodelist(version=100)
    root_list.upsert(ng.NodeEntry("1:100/0", "hub"))
    hub = ng.GossipPeer("hub", root_list)
    mid = ng.GossipPeer("mid", ng.Nodelist(version=100))
    leaf = ng.GossipPeer("leaf", ng.Nodelist(version=100))
    hub.link(mid)
    mid.link(leaf)
    hub.update(ng.NodeEntry("1:100/9", "newnode"))
    assert hub.gossip() == 1
    assert "1:100/9" in mid.known_addrs()
    assert mid.gossip() == 1
    assert "1:100/9" in leaf.known_addrs()
    # Second round sends nothing — everyone is current.
    assert hub.gossip() == 0
    assert mid.gossip() == 0


def test_origins():
    import levi.revival.tosser_scanner as m1
    import levi.revival.relay_chat as m2
    import levi.revival.csnet as m3
    import levi.revival.decnet as m4
    import levi.revival.xmpp_federation as m5
    import levi.revival.wave_federation as m6
    import levi.revival.nodediff_gossip as m7

    for m, slug in [
        (m1, "tosser-scanner"),
        (m2, "relay-chat"),
        (m3, "csnet"),
        (m4, "decnet"),
        (m5, "xmpp-federation"),
        (m6, "wave-federation"),
        (m7, "nodediff-gossip"),
    ]:
        assert m.ORIGIN == f"levi-revival/{slug}"
        assert "Studied from:" in m.__doc__
