"""Tests for revival wave 23: resurrection (b) — dead-web social mechanics."""

import pytest

from core.levi.revival import canvas_profile as cp
from core.levi.revival import top8_ritual as t8
from core.levi.revival import community_identity as ci
from core.levi.revival import sysop_stewardship as ss
from core.levi.revival import neighborhood_homepages as nh
from core.levi.revival import skinnable_surfaces as sk
from core.levi.revival import creator_ladder as cl


# ------------------------------------------------------------------
# canvas_profile
# ------------------------------------------------------------------


def test_canvas_skin_and_widget_layout():
    p = cp.blank_canvas("chauncey")
    p.apply_skin("paper")
    p.add_widget("w1", "about", "Hello", "hi there")
    p.add_widget("w2", "guestbook", "Say hi")
    p.move_widget("w2", 0)
    assert [w.widget_id for w in p.widgets] == ["w2", "w1"]
    assert p.effective_skin()["palette"] == "ink-on-cream"
    assert "guestbook" in cp.describe(p)


def test_canvas_custom_skin_and_tweaks():
    p = cp.blank_canvas("chauncey")
    p.add_skin(
        "midnight", {"palette": "deep-blue", "texture": "stars", "density": "airy"}
    )
    p.apply_skin("midnight")
    p.tweak_token("palette", "deep-blue-v2")
    assert p.effective_skin()["palette"] == "deep-blue-v2"
    assert "midnight" in p.to_dict()["skins"]
    with pytest.raises(KeyError):
        p.apply_skin("nope")


def test_canvas_roundtrip_and_validation():
    p = cp.blank_canvas("chauncey")
    p.add_widget("w1", "now", "Now")
    p2 = cp.CanvasProfile.from_dict(p.to_dict())
    assert p2.owner == "chauncey"
    assert [w.widget_id for w in p2.widgets] == ["w1"]
    with pytest.raises(ValueError):
        p2.add_widget("w1", "now", "dup")
    with pytest.raises(ValueError):
        p2.add_widget("w9", "telepathy", "bad-type")


# ------------------------------------------------------------------
# top8_ritual
# ------------------------------------------------------------------


def test_top8_place_promote_demote_retire():
    c = t8.new_circle("chauncey")
    c.place("a")
    c.place("b")
    c.place("c")
    assert c.rank_of("b") == 2
    c.promote("b")
    assert c.rank_of("b") == 1
    c.demote("b")
    assert c.rank_of("b") == 2
    c.retire("c")
    assert c.rank_of("c") is None
    assert len(c.slots) == 2


def test_top8_capacity_and_insert():
    c = t8.new_circle("chauncey")
    for i in range(8):
        c.place(f"f{i}")
    assert c.full()
    with pytest.raises(ValueError):
        c.place("f9")
    c.retire("f7")
    c.insert("vip", 1)
    assert c.rank_of("vip") == 1
    assert c.full()


def test_top8_journal_is_visible():
    c = t8.new_circle("chauncey")
    c.place("a")
    c.place("b")
    c.promote("b")
    recent = c.recent_changes(2)
    assert recent[0].action == "promote"
    assert recent[1].action == "place"
    with pytest.raises(ValueError):
        c.promote("b")  # already #1


# ------------------------------------------------------------------
# community_identity
# ------------------------------------------------------------------


def test_community_join_roles_and_badges():
    com = ci.found_community("nocturne", "we keep the night", "chauncey", tags=["art"])
    com.join("raven")
    com.set_role("chauncey", "raven", ci.ROLE_MODERATOR)
    com.award_badge("raven", "raven", "night-owl")
    card = com.identity_card("raven")
    assert card["role"] == "moderator"
    assert card["badges"] == ["night-owl"]
    assert card["community"] == "nocturne"
    assert com.member_count() == 2


def test_community_handoff_and_leave():
    com = ci.found_community("nocturne", "we keep the night", "chauncey")
    com.join("raven")
    with pytest.raises(ValueError):
        com.leave("chauncey")  # founder cannot abandon without handoff
    com.hand_off("chauncey", "raven")
    assert com.founder == "raven"
    com.leave("chauncey")
    assert com.member_count() == 1


def test_community_permission_guards():
    com = ci.found_community("nocturne", "we keep the night", "chauncey")
    com.join("raven")
    with pytest.raises(PermissionError):
        com.award_badge("raven", "chauncey", "poser")
    with pytest.raises(PermissionError):
        com.set_role("raven", "chauncey", ci.ROLE_MODERATOR)
    with pytest.raises(ValueError):
        com.join("raven")  # duplicate


# ------------------------------------------------------------------
# sysop_stewardship
# ------------------------------------------------------------------


def test_room_stewardship_handoff_and_rules():
    room = ss.open_room("tavern", "chauncey", code=["be kind"])
    room.admit("raven")
    room.add_rule("chauncey", "no shouting")
    assert room.code[-1] == "no shouting"
    room.hand_off("raven")
    assert room.sysop == "raven"
    assert room.log[-1].kind == "handoff"


def test_room_expel_requires_sysop():
    room = ss.open_room("tavern", "chauncey")
    room.admit("raven")
    with pytest.raises(PermissionError):
        room.expel("raven", "chauncey")
    room.expel("chauncey", "raven", reason="door game cheater")
    assert "raven" not in room.members


def test_room_shared_toy_turns():
    def scoreboard(state, player, action):
        state = dict(state)
        state[player] = state.get(player, 0) + int(action)
        return state

    room = ss.open_room("arcade", "chauncey")
    room.admit("raven")
    room.install_toy("highscore", {}, scoreboard)
    room.play("highscore", "raven", "10")
    state = room.play("highscore", "chauncey", "7")
    assert state == {"raven": 10, "chauncey": 7}
    ruling = room.rule_on("highscore dispute", "raven wins")
    assert ruling.sysop == "chauncey"


# ------------------------------------------------------------------
# neighborhood_homepages
# ------------------------------------------------------------------


def test_homestead_neighborhoods_and_pages():
    h = nh.settle()
    hood = h.found_neighborhood("harbor", motto="all boats welcome")
    page = hood.raise_page("chauncey", "lantern", tagline="builder")
    page.add_section("about", "i build things")
    assert h.find_page("chauncey") is page
    assert hood.census() == ["chauncey"]
    page.retheme("beacon")
    assert page.theme == "beacon"
    hood.tear_down("chauncey")
    assert h.find_page("chauncey") is None


def test_webring_next_prev_wrap():
    h = nh.settle()
    ring = h.start_ring("harbor-ring")
    for owner in ("a", "b", "c"):
        ring.join(owner)
    assert ring.next("a") == "b"
    assert ring.prev("a") == "c"  # wraps
    assert ring.next("c") == "a"
    ring.leave("b")
    assert ring.next("a") == "c"
    with pytest.raises(ValueError):
        ring.join("a")


def test_webring_single_member_has_no_next():
    h = nh.settle()
    ring = h.start_ring("lonely")
    ring.join("solo")
    with pytest.raises(ValueError):
        ring.next("solo")


# ------------------------------------------------------------------
# skinnable_surfaces
# ------------------------------------------------------------------


def test_surface_skin_and_plugins():
    s = sk.make_surface("now-playing")
    skin = sk.SkinManifest(
        name="neon",
        colors={"bg": "#000", "fg": "#0ff"},
        glyphs={"play": ">", "stop": "x"},
    )
    s.reskin(skin)
    assert s.skin.color("bg") == "#000"
    assert s.skin.glyph("play") == ">"
    s.install("announcer", "on_tick", lambda surface, ctx: f"tick {ctx.get('n', 0)}")
    assert s.fire("on_tick", {"n": 3}) == ["tick 3"]
    assert s.fire("on_other") == []
    s.uninstall("announcer")
    assert s.fire("on_tick") == []


def test_surface_plugin_validation():
    s = sk.make_surface("deck")
    with pytest.raises(ValueError):
        s.install("x", "on_tick", "not-callable")
    s.install("x", "on_tick", lambda surf, ctx: "ok")
    with pytest.raises(ValueError):
        s.install("x", "on_tick", lambda surf, ctx: "dup")
    with pytest.raises(KeyError):
        s.uninstall("ghost")


def test_user_station_broadcast_flow():
    ch = sk.open_station("chauncey", "LEVI FM")
    ch.enqueue("synth dawn")
    ch.enqueue("night bus")
    assert ch.go_live() == "synth dawn"
    assert ch.tune_in() == 1
    ch.set_schedule("nightly 10pm")
    line = ch.status_line()
    assert "LEVI FM" in line and "synth dawn" in line
    ch.tune_out()
    assert ch.listeners == 0
    ch.dequeue("night bus")
    with pytest.raises(ValueError):
        ch.go_live()  # empty queue


# ------------------------------------------------------------------
# creator_ladder
# ------------------------------------------------------------------


def test_ladder_votes_rungs_and_front_page():
    ladder = cl.open_ladder([("noticed", 2), ("front-page", 4)])
    ladder.post("w1", "a", "First", badges=["story"])
    ladder.post("w2", "b", "Second", badges=["code"])
    ladder.vote("w1", "v1", 1)
    ladder.vote("w1", "v2", 1)
    ladder.vote("w2", "v1", 1)
    assert ladder.score("w1") == 2
    assert ladder.rung_of("w1") == "noticed"
    ladder.vote("w1", "v3", 1)
    ladder.vote("w1", "v4", 1)
    assert ladder.rung_of("w1") == "front-page"
    page = ladder.front_page(slots=5)
    assert [w.work_id for w in page] == ["w1"]


def test_ladder_ballot_change_retract_and_self_vote():
    ladder = cl.open_ladder([("noticed", 1)])
    ladder.post("w1", "a", "First")
    with pytest.raises(ValueError):
        ladder.vote("w1", "a", 1)  # self-vote forbidden
    ladder.vote("w1", "v1", 1)
    assert ladder.score("w1") == 1
    ladder.vote("w1", "v1", -1)  # change ballot
    assert ladder.score("w1") == -1
    ladder.retract("w1", "v1")
    assert ladder.score("w1") == 0


def test_ladder_reputation_cross_domain():
    ladder = cl.open_ladder([("noticed", 1)])
    ladder.post("w1", "a", "Story", badges=["story"])
    ladder.post("w2", "a", "Code", badges=["code", "story"])
    ladder.vote("w1", "v1", 1)
    ladder.vote("w2", "v1", 1)
    ladder.vote("w2", "v2", 1)
    rep = ladder.reputation("a")
    assert rep["works"] == 2
    assert rep["total_score"] == 3
    assert rep["by_badge"]["story"] == 3
    assert rep["by_badge"]["code"] == 2
    assert cl.Ladder().rungs[0][0] == "noticed"  # defaults sane
