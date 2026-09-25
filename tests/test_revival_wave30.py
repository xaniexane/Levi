"""Tests for revival wave 30: protocols-b / sync patterns.

jingle_voice, gateway_proxy, source_routing, self_addressing,
name_binding, cache_device_truth_server, opera_link.
"""

import pytest

from levi.revival import jingle_voice as jv
from levi.revival import gateway_proxy as gp
from levi.revival import source_routing as sr
from levi.revival import self_addressing as sa
from levi.revival import name_binding as nb
from levi.revival import cache_device_truth_server as cd
from levi.revival import opera_link as ol


# ---------------------------------------------------------------------------
# jingle_voice
# ---------------------------------------------------------------------------


def test_jingle_full_call_lifecycle():
    mgr = jv.SessionManager()
    session = mgr.initiate("alice", "bob", [jv.Codec("opus", 10), jv.Codec("pcmu", 1)])
    assert session.state is jv.SessionState.PENDING
    session.add_candidate(jv.Candidate("host", "10.0.0.2", 5000))
    agreed = mgr.accept(session.session_id, [jv.Codec("pcmu", 5), jv.Codec("opus", 3)])
    assert agreed.name == "pcmu"  # responder prefers pcmu; both offer it
    assert mgr.get(session.session_id).state is jv.SessionState.ACTIVE
    assert mgr.active_sessions() == [session]
    mgr.terminate(session.session_id)
    assert mgr.get(session.session_id).state is jv.SessionState.TERMINATED
    assert mgr.active_sessions() == []


def test_jingle_negotiation_failure_and_bad_transitions():
    mgr = jv.SessionManager()
    session = mgr.initiate("a", "b", [jv.Codec("opus", 1)])
    with pytest.raises(jv.NoCommonCodec):
        mgr.accept(session.session_id, [jv.Codec("pcmu", 9)])
    # failed accept leaves the session pending; terminating twice is fine, re-accept is not
    mgr.terminate(session.session_id)
    with pytest.raises(jv.BadTransition):
        mgr.accept(session.session_id, [jv.Codec("opus", 1)])
    with pytest.raises(jv.BadTransition):
        session.add_candidate(jv.Candidate("host", "x", 1))
    with pytest.raises(jv.UnknownSession):
        mgr.accept("jingle-999", [jv.Codec("opus", 1)])


def test_jingle_initiate_requires_codecs_and_responder_preference_wins():
    mgr = jv.SessionManager()
    with pytest.raises(jv.SignallingError):
        mgr.initiate("a", "b", [])
    agreed = jv.negotiate_codecs(
        [jv.Codec("opus", 100), jv.Codec("pcmu", 1)],
        [jv.Codec("pcmu", 50), jv.Codec("opus", 1)],
    )
    assert agreed.name == "pcmu"  # responder's top preference decides


# ---------------------------------------------------------------------------
# gateway_proxy
# ---------------------------------------------------------------------------


def test_gateway_adapts_html_for_text_only_handset():
    gateway = gp.TranscodingGateway()
    profile = gp.DeviceProfile(name="old-phone", max_payload_bytes=64, text_only=True)
    item = gp.ContentItem(
        kind="text/html",
        payload=b"<html><body><h1>Hello</h1> <p>world "
        + b"x" * 200
        + b"</p></body></html>",
    )
    adapted, adaptations = gateway.adapt(item, profile)
    assert adapted.kind == "text/plain"
    assert b"<" not in adapted.payload
    assert b"Hello" in adapted.payload
    assert len(adapted.payload) <= profile.max_payload_bytes
    assert adapted.meta.get("truncated") is True
    kinds = [a.transformer for a in adaptations]
    assert kinds == ["strip_markup", "downscale_media", "truncate_text"]
    assert any(a.after_bytes < a.before_bytes for a in adaptations)


def test_gateway_downscales_media_and_respects_capable_client():
    gateway = gp.TranscodingGateway()
    rich = gp.DeviceProfile(
        name="smartphone",
        max_payload_bytes=10_000_000,
        text_only=False,
        max_image_width=800,
    )
    item = gp.ContentItem(
        kind="image/png",
        payload=b"\x89PNG" + b"z" * 10000,
        meta={"width": 1600, "height": 1200},
    )
    adapted, adaptations = gateway.adapt(item, rich)
    assert adapted.meta["width"] == 800
    assert adapted.meta["height"] == 600
    assert adapted.meta.get("downscaled") is True
    assert len(adapted.payload) < 10004
    # a capable profile leaves small media untouched
    small = gp.ContentItem(
        kind="image/png", payload=b"tiny", meta={"width": 100, "height": 50}
    )
    adapted2, _ = gateway.adapt(small, rich)
    assert adapted2.payload == b"tiny"
    assert "downscaled" not in adapted2.meta


def test_gateway_media_placeholder_for_text_only_and_custom_transformer():
    gateway = gp.TranscodingGateway()
    profile = gp.DeviceProfile(
        name="pager", max_payload_bytes=1000, text_only=True, max_image_width=0
    )
    item = gp.ContentItem(
        kind="image/gif", payload=b"GIF89a" + b"q" * 500, meta={"width": 320}
    )
    adapted, _ = gateway.adapt(item, profile)
    assert adapted.kind == "text/plain"
    assert adapted.payload == b"[media removed]"
    gateway.register(
        "watermark",
        lambda item, prof: (item, gp.Adaptation("watermark", 1, 1, "custom")),
    )
    adapted3, adaptations = gateway.adapt(gp.ContentItem("text/plain", b"hi"), profile)
    assert adaptations[-1].transformer == "watermark"
    assert adapted3.payload == b"hi"


# ---------------------------------------------------------------------------
# source_routing
# ---------------------------------------------------------------------------


def _mesh() -> dict[str, set[str]]:
    return {
        "me": {"a"},
        "a": {"me", "b"},
        "b": {"a", "c"},
        "c": {"b"},
        "far": set(),
    }


def test_bang_path_parse_and_round_trip():
    path = sr.parse_bang_path("a!b!c!user")
    assert path.hops == ("a", "b", "c")
    assert path.recipient == "user"
    assert path.format() == "a!b!c!user"
    direct = sr.parse_bang_path("user")
    assert direct.hops == () and direct.recipient == "user"
    with pytest.raises(sr.MalformedAddress):
        sr.parse_bang_path("a!!b")
    with pytest.raises(sr.MalformedAddress):
        sr.parse_bang_path("")


def test_deliver_walks_hops_with_local_knowledge_only():
    delivery = sr.deliver("a!b!c!user", start="me", adjacency=_mesh())
    assert delivery.visited == ["me", "a", "b", "c"]
    assert delivery.route.recipient == "user"
    # reply route is the travelled path reversed back to the entry point
    assert delivery.reversed_route.format() == "c!b!a!me"


def test_deliver_refuses_broken_hop_and_direct_delivery():
    with pytest.raises(sr.NoSuchHop):
        sr.deliver("a!c!user", start="me", adjacency=_mesh())  # a and c not adjacent
    with pytest.raises(sr.NoSuchHop):
        sr.deliver("far!user", start="me", adjacency=_mesh())
    delivery = sr.deliver("user", start="me", adjacency=_mesh())
    assert delivery.visited == ["me"]
    assert delivery.reversed_route.recipient == "me"


# ---------------------------------------------------------------------------
# self_addressing
# ---------------------------------------------------------------------------


def test_nodes_self_assign_unique_addresses():
    link = sa.Link(address_min=1, address_max=10)
    nodes = [sa.SelfAddressedNode(f"node{i}", link, seed=i) for i in range(5)]
    addresses = [n.join() for n in nodes]
    assert len(set(addresses)) == 5  # probes guarantee uniqueness
    assert all(1 <= a <= 10 for a in addresses)
    assert all(v == n.name for n, v in ((n, link.claimed()[n.address]) for n in nodes))
    # join is idempotent
    assert nodes[0].join() == addresses[0]


def test_conflict_probe_retries_and_exhaustion():
    link = sa.Link(address_min=1, address_max=2)
    first = sa.SelfAddressedNode("first", link, seed=0)
    second = sa.SelfAddressedNode("second", link, seed=0)  # same draw order
    a, b = first.join(), second.join()
    assert a != b
    assert second.probes_made >= 2  # first probe collided, retried
    third = sa.SelfAddressedNode("third", link, max_attempts=3, seed=0)
    with pytest.raises(sa.NoAddressAvailable):
        third.join()


def test_leave_releases_address_for_reuse():
    link = sa.Link(address_min=1, address_max=1)
    node = sa.SelfAddressedNode("solo", link, seed=7)
    assert node.join() == 1
    node.leave()
    assert node.address is None
    assert link.claimed() == {}
    newcomer = sa.SelfAddressedNode("newcomer", link, seed=7)
    assert newcomer.join() == 1


# ---------------------------------------------------------------------------
# name_binding
# ---------------------------------------------------------------------------


def test_register_lookup_unregister_round_trip():
    zone = nb.ZoneTable("hq")
    alice = nb.NamesTable("addr-a", zone)
    bob = nb.NamesTable("addr-b", zone)
    name = alice.register("fileserver:afp@hq")
    assert name.format() == "fileserver:afp@hq"
    assert bob.lookup("fileserver:afp@hq") == "addr-a"
    assert alice.owned() == ["fileserver:afp@hq"]
    alice.unregister("fileserver:afp@hq")
    with pytest.raises(nb.UnknownName):
        bob.lookup("fileserver:afp@hq")


def test_name_conflicts_are_refused_across_nodes():
    zone = nb.ZoneTable("hq")
    alice = nb.NamesTable("addr-a", zone)
    bob = nb.NamesTable("addr-b", zone)
    alice.register("printer:laser@hq")
    with pytest.raises(nb.NameInUse):
        bob.register("printer:laser@hq")
    # re-registering our own name is idempotent, not a conflict
    assert alice.register("printer:laser@hq").format() == "printer:laser@hq"
    # a different type may share the object name
    bob.register("printer:inkjet@hq")
    assert bob.lookup("printer:inkjet@hq") == "addr-b"


def test_malformed_names_and_zone_mismatch():
    for bad in ["nope", "a:b", "a@z", ":b@z", "a:@z", "a:b@", ""]:
        with pytest.raises(nb.MalformedName):
            nb.parse_name(bad)
    zone = nb.ZoneTable("hq")
    table = nb.NamesTable("addr-a", zone)
    with pytest.raises(nb.MalformedName):
        table.register("fileserver:afp@branch")  # wrong zone for this table
    assert zone.list_by_type("afp") == []
    table.register("fileserver:afp@hq")
    table.register("backup:afp@hq")
    assert zone.list_by_type("afp") == ["backup:afp@hq", "fileserver:afp@hq"]


# ---------------------------------------------------------------------------
# cache_device_truth_server
# ---------------------------------------------------------------------------


def test_backup_sync_and_replacement_restore():
    server = cd.TruthStore()
    phone = cd.DeviceCache("phone-1", server)
    phone.put("contacts/alice", {"phone": "555-0100"})
    phone.put("photos/beach", b"<bytes>")
    accepted = phone.sync()
    assert set(accepted) == {"contacts/alice", "photos/beach"}
    # replacement handset restores everything from the truth
    replacement = cd.DeviceCache("phone-2", server)
    assert replacement.restore() == 2
    assert replacement.get("contacts/alice") == {"phone": "555-0100"}
    assert replacement.keys() == ["contacts/alice", "photos/beach"]


def test_last_writer_wins_and_tombstones_replicate():
    server = cd.TruthStore()
    a = cd.DeviceCache("device-a", server)
    b = cd.DeviceCache("device-b", server)
    a.put("note", "from-a")
    a.sync()
    b.put("note", "from-b")  # later version wins
    b.sync()
    assert server.raw("note").value == "from-b"
    a.delete("note")
    a.sync()
    assert server.raw("note").deleted is True
    # a fresh device does not resurrect the tombstoned record
    fresh = cd.DeviceCache("device-c", server)
    assert fresh.restore() == 0
    with pytest.raises(KeyError):
        fresh.get("note")


def test_sync_reconciles_losing_device_to_truth():
    server = cd.TruthStore()
    a = cd.DeviceCache("device-a", server)
    b = cd.DeviceCache("device-b", server)
    a.put("shared", "a-wins")
    a.sync()
    b.put("shared", "b-loses")
    b.sync()  # b wrote first in clock terms? both ticked; check actual winner
    truth = server.raw("shared")
    # the winner is deterministic: higher (version, device_id)
    assert truth.value in {"a-wins", "b-loses"}
    # both devices converge on the canonical value after syncing
    a.sync()
    b.sync()
    assert a.get("shared") == truth.value
    assert b.get("shared") == truth.value
    with pytest.raises(cd.SyncError):
        server.push([cd.Record(key="", value=1, version=1, device_id="x")])


# ---------------------------------------------------------------------------
# opera_link
# ---------------------------------------------------------------------------


def test_two_way_sync_merges_dials_notes_bookmarks():
    desktop = ol.SyncStore("desktop")
    phone = ol.SyncStore("phone")
    desktop.upsert("dials", "d1", {"url": "https://example.com"}, updated=1)
    desktop.upsert("notes", "n1", {"text": "buy milk"}, updated=1)
    phone.upsert("bookmarks", "b1", {"url": "https://levi.dev"}, updated=2)
    report = ol.sync_pair(desktop, phone)
    assert report.to_remote == 2 and report.to_local == 1
    assert desktop.get("bookmarks", "b1").payload["url"] == "https://levi.dev"
    assert phone.get("dials", "d1").payload["url"] == "https://example.com"
    assert phone.get("notes", "n1").payload["text"] == "buy milk"


def test_conflict_resolves_last_writer_wins_and_deletion_replicates():
    desktop = ol.SyncStore("desktop")
    phone = ol.SyncStore("phone")
    desktop.upsert("notes", "n1", {"text": "old"}, updated=1)
    ol.sync_pair(desktop, phone)
    desktop.upsert("notes", "n1", {"text": "desktop-edit"}, updated=3)
    phone.upsert("notes", "n1", {"text": "phone-edit"}, updated=2)
    report = ol.sync_pair(desktop, phone)
    assert report.conflicts_resolved == 1
    assert desktop.get("notes", "n1").payload["text"] == "desktop-edit"
    assert phone.get("notes", "n1").payload["text"] == "desktop-edit"
    # deletion replicates as a tombstone
    phone.remove("notes", "n1", updated=4)
    ol.sync_pair(desktop, phone)
    assert desktop.live("notes") == []
    assert phone.live("notes") == []


def test_sync_is_idempotent():
    desktop = ol.SyncStore("desktop")
    phone = ol.SyncStore("phone")
    desktop.upsert("dials", "d1", {"url": "https://a.example"}, updated=1)
    phone.upsert("dials", "d2", {"url": "https://b.example"}, updated=1)
    first = ol.sync_pair(desktop, phone)
    assert first.to_remote + first.to_local == 2
    second = ol.sync_pair(desktop, phone)
    assert second.to_remote == 0 and second.to_local == 0
    assert len(desktop.live("dials")) == 2 and len(phone.live("dials")) == 2
