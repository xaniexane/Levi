"""Tests for revival wave 40 — worlds & presence (8 modules)."""

import pytest

from levi.revival import activity_presence as ap
from levi.revival import buddy_list as bl
from levi.revival import delta_world as dw
from levi.revival import live_builder as lb
from levi.revival import major_mud as mm
from levi.revival import online_messages as om
from levi.revival import pin_push as pp
from levi.revival import text_world_db as tw


# ---------------------------------------------------------------- major_mud
def _host():
    host = mm.DoorHost()
    host.register(mm.SimpleTavern())
    return host


def test_host_routes_input_to_active_addon():
    host = _host()
    player = host.login("mara")
    assert "tavern" in host.launch("tavern", player).lower()
    assert "smoky tavern" in host.handle(player, "look")
    assert "shouts: hello all" in host.handle(player, "shout hello all")


def test_addon_state_shared_between_players():
    host = _host()
    mara = host.login("mara")
    theo = host.login("theo")
    host.launch("tavern", mara)
    host.launch("tavern", theo)
    host.handle(mara, "note meet at dusk")
    assert "meet at dusk" in host.handle(theo, "read")
    assert "theo" in host.handle(mara, "look")  # shared patron list


def test_player_state_survives_relogin():
    host = _host()
    player = host.login("mara")
    host.launch("tavern", player)
    player.set("gold", 42)
    blob = host.save_player(player)
    host2 = mm.DoorHost()
    restored = host2.load_player(blob)
    assert restored.name == "mara"
    assert restored.bag["gold"] == 42


def test_host_rejects_bad_rules():
    host = _host()
    player = host.login("mara")
    with pytest.raises(mm.HostError):
        host.launch("nope", player)
    host.launch("tavern", player)
    with pytest.raises(mm.HostError):
        host.launch("tavern", player)  # double launch
    host.quit(player)
    with pytest.raises(mm.HostError):
        host.quit(player)  # not inside anything


# --------------------------------------------------------------- delta_world
def _world_with_avatar():
    catalog = dw.AssetCatalog()
    catalog.add("avatar/knight", b"\x89PNG" + b"\x00" * 100)
    world = dw.WorldState(catalog)
    world.spawn("mara", "avatar/knight", x=10, y=20, hp=100)
    return catalog, world


def test_quiet_client_gets_empty_diff():
    catalog, world = _world_with_avatar()
    link = dw.DeltaLink(world)
    client = link.new_client()
    assert link.diff(client) == []  # nothing changed since baseline


def test_diff_carries_only_changes_then_reconverges():
    catalog, world = _world_with_avatar()
    link = dw.DeltaLink(world)
    client = link.new_client()
    world.set("mara", "x", 11)
    ops = link.diff(client)
    assert ops == [dw.DeltaOp("mara", "x", 11)]
    assert link.diff(client) == []  # baseline advanced
    # remote side applies the op and converges
    remote_catalog = dw.AssetCatalog()
    remote_catalog.add("avatar/knight", b"local-copy")
    remote = dw.WorldState(remote_catalog)
    dw.DeltaLink.apply(
        remote,
        [
            dw.DeltaOp("mara", "_asset", "avatar/knight"),
            dw.DeltaOp("mara", "x", 10),
            dw.DeltaOp("mara", "y", 20),
            dw.DeltaOp("mara", "hp", 100),
        ],
    )
    dw.DeltaLink.apply(remote, ops)
    assert remote.state_of("mara")["x"] == 11


def test_despawn_tombstone_propagates():
    catalog, world = _world_with_avatar()
    link = dw.DeltaLink(world)
    client = link.new_client()
    world.despawn("mara")
    ops = link.diff(client)
    assert ops == [dw.DeltaOp("mara", None, None)]
    remote_catalog = dw.AssetCatalog()
    remote_catalog.add("avatar/knight", b"x")
    remote = dw.WorldState(remote_catalog)
    remote.spawn("mara", "avatar/knight", x=1)
    dw.DeltaLink.apply(remote, ops)
    assert remote.entities() == []


def test_assets_never_cross_the_link():
    catalog = dw.AssetCatalog()
    catalog.add("art/room", b"\x00" * 5000)
    world = dw.WorldState(catalog)
    world.spawn("room1", "art/room", name="hall")
    link = dw.DeltaLink(world)
    client = link.new_client()
    ops = link.diff(client)
    wire = link.diff_bytes(ops)
    assert wire < catalog.total_bytes()  # deltas stay tiny vs local assets


# -------------------------------------------------------------- live_builder
def test_ladder_promotion_needs_points_and_wizard():
    world = lb.BuilderWorld(founder="root")
    world.join("mara")
    world.earn("mara", 100)
    assert world.promote("mara", by="root") == "mara is now a builder."
    assert world.rank_of("mara") == "builder"


def test_build_verbs_gated_by_rank():
    world = lb.BuilderWorld(founder="root")
    world.join("mara")
    with pytest.raises(lb.BuilderError):
        world.dig("mara", "hall")  # player cannot dig
    world.earn("mara", 100)
    world.promote("mara", by="root")
    world.dig("mara", "hall", "A grand hall.")
    world.make("mara", "lamp", "hall", "A brass lamp.")
    assert world.rooms() == ["hall"]
    assert world.room_info("hall")["built_by"] == "mara"
    with pytest.raises(lb.BuilderError):
        world.script("mara", "q1", ["step"])  # builder cannot script quests
    assert "1 steps" in world.script("root", "q1", ["find the lamp"])


def test_everything_lands_in_audit_log():
    world = lb.BuilderWorld(founder="root")
    world.join("mara")
    world.earn("mara", 100)
    world.promote("mara", by="root")
    world.dig("mara", "hall")
    audit = world.audit()
    actions = [r.action for r in audit]
    assert actions == ["seed", "promote", "dig"]
    assert all(r.seq == i + 1 for i, r in enumerate(audit))
    assert audit[-1].author == "mara" and audit[-1].author_rank == "builder"


def test_demote_and_nonwizard_promote_rejected():
    world = lb.BuilderWorld(founder="root")
    world.join("mara")
    world.join("theo")
    world.earn("mara", 100)
    world.promote("mara", by="root")
    with pytest.raises(lb.BuilderError):
        world.promote("theo", by="mara")  # only wizards promote
    assert "player" in world.demote("mara", by="root")
    assert world.rank_of("mara") == "player"


# ------------------------------------------------------------- text_world_db
SCRIPT = """
# a tiny starting area
room hall "The Grand Hall"
room court "The Courtyard"
exit hall north to court
object lamp in hall name "Brass Lamp" desc "It glows faintly."
attr lamp fuel = 7
spawn mara in hall
"""


def test_script_builds_world_and_reports_per_line():
    db = tw.WorldDB()
    results = db.apply(SCRIPT)
    assert all(r.ok for r in results), [r for r in results if not r.ok]
    assert db.rooms() == ["court", "hall"]
    assert db.objects_in("hall") == ["lamp"]
    assert db.get_attr("lamp", "fuel") == 7
    assert db.where("mara") == "hall"


def test_bad_lines_reported_without_aborting_script():
    db = tw.WorldDB()
    results = db.apply("room hall\nbogus verb here\nexit hall north to nowhere\n")
    ok = [r.ok for r in results]
    assert ok == [True, False, False]
    assert "unknown directive" in results[1].message
    assert "nowhere" in results[2].message


def test_movement_take_drop_cycle():
    db = tw.WorldDB()
    db.apply(SCRIPT)
    assert db.move_player("mara", "north") == "court"
    assert "Courtyard" in db.look("court")
    db.add_exit("court", "south", "hall")
    assert db.move_player("mara", "south") == "hall"
    db.take("mara", "lamp")
    assert db.inventory("mara") == ["lamp"]
    assert db.objects_in("hall") == []
    db.drop("mara", "lamp")
    assert db.objects_in("hall") == ["lamp"]


def test_save_and_load_roundtrip(tmp_path):
    db = tw.WorldDB()
    db.apply(SCRIPT)
    path = str(tmp_path / "world.json")
    db.save(path)
    db2 = tw.WorldDB.load(path)
    assert db2.rooms() == ["court", "hall"]
    assert db2.get_attr("lamp", "fuel") == 7
    assert db2.where("mara") == "hall"


# ---------------------------------------------------------- online_messages
def test_online_delivery_and_offline_queue():
    bus = om.PresenceBus()
    bus.sign_on("mara")
    bus.sign_on("theo")
    msg = bus.send("mara", "theo", "hello")
    assert msg.delivered_now is True
    bus.sign_off("theo")
    queued = bus.send("mara", "theo", "are you there?")
    assert queued.delivered_now is False
    assert bus.pending_count("theo") == 1
    missed = bus.sign_on("theo")  # inbox handed over on sign-on
    assert [m.text for m in missed] == ["are you there?"]
    assert bus.pending_count("theo") == 0


def test_away_note_visible_to_sender():
    bus = om.PresenceBus()
    bus.sign_on("mara")
    bus.sign_on("theo")
    bus.set_away("theo", "grabbing coffee")
    assert bus.presence_of("theo") == "away"
    assert bus.away_note("theo") == "grabbing coffee"
    msg = bus.send("mara", "theo", "ping")
    assert msg.delivered_now is True  # away still receives
    bus.back("theo")
    assert bus.presence_of("theo") == "online"


def test_send_rules_rejected():
    bus = om.PresenceBus()
    bus.sign_on("mara")
    with pytest.raises(om.OlmError):
        bus.send("mara", "mara", "self")  # no self-send
    with pytest.raises(om.OlmError):
        bus.send("mara", "theo", "   ")  # empty text
    with pytest.raises(om.OlmError):
        bus.send("ghost", "mara", "hi")  # offline sender
    with pytest.raises(om.OlmError):
        bus.set_away("ghost")


# ---------------------------------------------------------------- buddy_list
def test_grouped_roster_with_presence():
    roster = bl.BuddyList("chauncey")
    roster.add_buddy("mara")
    roster.add_buddy("theo", group="Work")
    roster.set_presence("mara", "online")
    roster.set_presence("theo", "away")
    grouped = roster.roster()
    assert grouped["Buddies"][0] == {"name": "mara", "presence": "online", "away": None}
    assert grouped["Work"][0]["presence"] == "away"
    assert roster.groups() == ["Buddies", "Work"]


def test_away_message_history_is_status_ancestry():
    roster = bl.BuddyList("chauncey")
    roster.add_buddy("mara")
    roster.set_away_message("mara", "out to lunch")
    roster.set_away_message("mara", "back in 5")
    assert roster.away_message("mara") == "back in 5"
    history = roster.status_history("mara")
    assert [u.text for u in history] == ["out to lunch", "back in 5"]
    assert roster.presence_of("mara") == "away"
    with pytest.raises(bl.BuddyError):
        roster.set_away_message("mara", "x" * 281)


def test_block_hides_everywhere():
    roster = bl.BuddyList("chauncey")
    roster.add_buddy("mara")
    roster.add_buddy("spam")
    roster.set_presence("spam", "online")
    roster.block("spam")
    assert roster.is_blocked("spam")
    assert "spam" not in str(roster.roster())
    assert roster.blocked() == ["spam"]
    with pytest.raises(bl.BuddyError):
        roster.add_buddy("spam")  # must unblock first
    roster.unblock("spam")
    roster.add_buddy("spam")
    assert roster.presence_of("spam") == "offline"


def test_presence_events_record_transitions():
    roster = bl.BuddyList("chauncey")
    roster.add_buddy("mara")
    e1 = roster.set_presence("mara", "online")
    e2 = roster.set_presence("mara", "idle")
    assert (e1.old, e1.new) == ("offline", "online")
    assert (e2.old, e2.new) == ("online", "idle")
    assert [e.seq for e in roster.events()] == [1, 2]
    with pytest.raises(bl.BuddyError):
        roster.set_presence("mara", "invisible")


# -------------------------------------------------------- activity_presence
def test_activity_metadata_snapshot():
    p = ap.RichPresence("mara")
    p.set_state("online")
    p.set_activity("music", "Kind of Blue", "Miles Davis")
    snap = p.snapshot()
    assert snap["state"] == "online"
    assert snap["activity_kind"] == "music"
    assert snap["activity_title"] == "Kind of Blue"
    p.clear_activity()
    assert p.snapshot()["activity_kind"] is None
    with pytest.raises(ap.PresenceError):
        p.set_state("vibing")


def test_emoticon_render_with_escapes():
    pack = ap.EmoticonPack()
    pack.add(":)", "\U0001f642")
    pack.add(":-)", "\U0001f642")
    assert pack.render("hi :)") == "hi \U0001f642"
    assert pack.render("hi \\:)") == "hi :)"  # escaped stays literal
    assert pack.render("hi :-)") == "hi \U0001f642"  # longest match wins
    pack.remove(":)")
    assert pack.render("hi :)") == "hi :)"


def _clock(times):
    it = iter(times)
    return lambda: next(it)


def test_nudge_cooldown_blocks_spam():
    bus = ap.AttentionBus(clock=_clock([100.0, 105.0, 140.0]))
    assert bus.nudge("mara", "theo") is True
    assert bus.nudge("mara", "theo") is False  # 5s later: cooldown
    assert bus.nudge("mara", "theo") is True  # 40s later: allowed
    assert bus.nudges_received("theo") == 2
    with pytest.raises(ap.PresenceError):
        bus.nudge("mara", "mara")


# ------------------------------------------------------------------ pin_push
def test_pin_is_stable_pseudonymous_and_short():
    pin = pp.pin_from("device-secret-xyz")
    assert pin == pp.pin_from("device-secret-xyz")  # stable
    assert len(pin) == 8
    assert pin != pp.pin_from("other-secret")  # distinct
    assert "device-secret" not in pin  # reveals nothing


def test_push_compresses_and_delivers_with_receipts():
    channel = pp.PushChannel()
    pin = pp.pin_from("secret")
    channel.register(pin)
    payload = b"hello world " * 1000  # highly redundant -> compresses well
    msg_id = channel.enqueue(pin, payload)
    assert channel.pending_count(pin) == 1
    assert channel.compression_ratio(pin, msg_id) < 1.0
    drained = channel.drain(pin)
    assert drained[pin] == [payload]  # lossless round-trip
    assert channel.pending_count(pin) == 0
    receipts = channel.receipts(pin)
    assert receipts[0].state == "delivered"  # D receipt
    assert receipts[0].raw_bytes == len(payload)
    channel.mark_read(pin, msg_id)
    assert channel.receipts(pin)[0].state == "read"  # R receipt


def test_single_connection_sweeps_all_pins():
    channel = pp.PushChannel()
    pins = [pp.pin_from(f"s{i}") for i in range(3)]
    for pin in pins:
        channel.register(pin)
        channel.enqueue(pin, f"msg for {pin}".encode())
    swept = channel.drain()  # one call, every PIN
    assert set(swept) == set(pins)
    assert all(len(v) == 1 for v in swept.values())


def test_push_rejects_bad_input():
    channel = pp.PushChannel()
    with pytest.raises(pp.PushError):
        channel.enqueue("ghost", b"x")  # unknown PIN
    pin = pp.pin_from("s")
    channel.register(pin)
    with pytest.raises(pp.PushError):
        channel.register(pin)  # duplicate
    with pytest.raises(pp.PushError):
        channel.enqueue(pin, b"")  # empty payload
    with pytest.raises(pp.PushError):
        channel.mark_read(pin, "nope")  # unknown message
