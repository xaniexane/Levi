"""Tests for revival batch B07 — social spaces, coordination, legibility.

Covers: speechacts, beats, afford, kiosk, roundtable, hearth, metaphor,
roomscript, commons. >=3 meaningful tests per module.
"""

import json

import pytest

from levi.revival import speechacts, beats, afford, kiosk, roundtable, hearth
from levi.revival import metaphor, roomscript, commons


# ---------------------------------------------------------------------------
# speechacts
# ---------------------------------------------------------------------------


def test_speechacts_full_cycle():
    conv = speechacts.Conversation()
    c = conv.request(
        "chauncey", "levi", "draft the release notes", due_in=100, now=1000.0
    )
    assert c.state is speechacts.CommitmentState.OPEN
    conv.promise(c.id, by="levi", now=1001.0)
    assert c.state is speechacts.CommitmentState.PROMISED
    conv.fulfill(c.id, by="levi", evidence="notes drafted", now=1050.0)
    assert c.state is speechacts.CommitmentState.FULFILLED
    assert c.evidence == "notes drafted"
    assert not conv.pending()


def test_speechacts_overdue_surfaces():
    conv = speechacts.Conversation()
    c = conv.request("a", "b", "do the thing", due_in=10, now=0.0)
    conv.promise(c.id, by="b", now=1.0)
    assert conv.overdue(now=5.0) == []
    overdue = conv.overdue(now=50.0)
    assert [x.id for x in overdue] == [c.id]


def test_speechacts_discipline_rejects_bad_transitions():
    conv = speechacts.Conversation()
    c = conv.request("a", "b", "task", now=0.0)
    with pytest.raises(speechacts.SpeechActError):
        conv.promise(c.id, by="a")  # only the addressee can promise
    with pytest.raises(speechacts.SpeechActError):
        conv.fulfill(c.id, by="b")  # cannot fulfill before promising
    conv.decline(c.id, by="b", reason="no bandwidth", now=2.0)
    assert c.state is speechacts.CommitmentState.DECLINED
    with pytest.raises(speechacts.SpeechActError):
        conv.promise(c.id, by="b")  # declined is terminal


def test_speechacts_assert_declare_open_no_commitment():
    conv = speechacts.Conversation()
    conv.assert_("levi", "the build is green")
    conv.declare("chauncey", "we ship friday")
    assert conv.pending() == []
    acts = [m.act for m in conv.log()]
    assert acts == [speechacts.SpeechAct.ASSERT, speechacts.SpeechAct.DECLARE]
    assert len(conv.messages) == 2


# ---------------------------------------------------------------------------
# beats
# ---------------------------------------------------------------------------


def test_beats_act_mapping_covers_twelve():
    assert beats.map_act("hello there") is beats.DiscourseAct.GREET
    assert beats.map_act("what is this?") is beats.DiscourseAct.ASK
    assert beats.map_act("thanks, that was great") is beats.DiscourseAct.PRAISE
    assert beats.map_act("never mind, forget it") is beats.DiscourseAct.DEFLECT
    assert beats.map_act("goodbye for now") is beats.DiscourseAct.FAREWELL
    assert beats.map_act("yes, exactly") is beats.DiscourseAct.AGREE
    assert len(beats.DiscourseAct) == 12


def test_beats_drama_manager_sequences_arc():
    mgr = beats.DramaManager(beats.three_act_arc())
    r1 = mgr.step("hello!")
    assert r1.beat_name == "welcome"
    r2 = mgr.step("what can you do for me?")
    assert r2.beat_name == "probe"
    assert r2.tension > r1.tension  # rising arc
    assert mgr.played == ["welcome", "probe"]


def test_beats_preconditions_gate_on_tension():
    arc = [
        beats.Beat(
            name="hot",
            line="now we're cooking",
            awaits=beats.DiscourseAct.DECLARE,
            tension_band=(0.8, 1.0),
        ),
    ]
    mgr = beats.DramaManager(arc, tension=0.1)
    r = mgr.step("here's the thing: we launch")
    assert r.beat_name == "(improvise)"  # tension too low, beat can't fire
    mgr.tension = 0.9
    r2 = mgr.step("here's the thing: we launch")
    assert r2.beat_name == "hot"


# ---------------------------------------------------------------------------
# afford
# ---------------------------------------------------------------------------


def test_afford_agent_follows_gradient_to_best_object():
    t = afford.Terrain()
    t.place(afford.AffordanceObject("puddle", 10, 0, {"thirst": 0.2}))
    t.place(afford.AffordanceObject("well", 3, 0, {"thirst": 1.0}))
    t.spawn(afford.Agent("wanderer", 0, 0, {"thirst": 5.0}, stride=1.0))
    t.run(8)
    ag = t.agents["wanderer"]
    assert (ag.x, ag.y) == (3, 0)  # went to the well, not the puddle
    assert ag.needs["thirst"] < 5.0  # drank


def test_afford_zero_foreknowledge_new_object_reroutes():
    t = afford.Terrain()
    t.place(afford.AffordanceObject("old-spring", 9, 0, {"thirst": 0.5}))
    t.spawn(afford.Agent("a", 0, 0, {"thirst": 9.0}, stride=1.0))
    t.run(3)
    # brand-new object appears; the agent never knew its type, only its signal
    t.place(afford.AffordanceObject("mystery-x", 1, 1, {"thirst": 2.0}))
    before = (t.agents["a"].x, t.agents["a"].y)
    t.run(6)
    ag = t.agents["a"]
    assert (ag.x, ag.y) != before
    assert ag.target == "mystery-x" or (ag.x, ag.y) == (1, 1)


def test_afford_sated_agent_idles_and_depletion_stops_signal():
    t = afford.Terrain()
    t.place(afford.AffordanceObject("berry", 0, 0, {"hunger": 1.0}, capacity=1.0))
    t.spawn(afford.Agent("g", 0, 0, {"hunger": 0.0}))
    events = t.step()
    assert events[0].kind == "idle"  # sated: nothing to want
    t.agents["g"].needs["hunger"] = 5.0
    t.run(2)
    assert t.objects["berry"].advertise() == {}  # depleted: signal goes silent


# ---------------------------------------------------------------------------
# kiosk
# ---------------------------------------------------------------------------


def _kiosk_with_services():
    k = kiosk.Kiosk()
    k.register(
        kiosk.Service(
            code="411",
            name="directory",
            owner="ops",
            price_per_unit=0.50,
            owner_share=0.7,
            handler=lambda tok, u: "555-0100",
        )
    )
    k.register(
        kiosk.Service(
            code="wx",
            name="weather",
            owner="skyco",
            price_per_unit=0.25,
            owner_share=1.0,
            handler=lambda tok, u: "sunny",
        )
    )
    return k


def test_kiosk_session_is_identity_and_use_meters():
    k = _kiosk_with_services()
    tok = k.open_session()
    assert k.use(tok, "411") == "555-0100"
    k.use(tok, "wx", units=2)
    bill = k.bill(tok)
    assert bill.total == pytest.approx(0.50 + 0.50)
    assert {line.code for line in bill.lines} == {"411", "wx"}


def test_kiosk_settle_splits_revenue_to_owners():
    k = _kiosk_with_services()
    tok = k.open_session()
    k.use(tok, "411", units=2)  # $1.00 gross, 70% to ops
    k.use(tok, "wx", units=4)  # $1.00 gross, 100% to skyco
    payouts = {p.code: p for p in k.settle()}
    assert payouts["411"].owner == "ops"
    assert payouts["411"].owner_cut == pytest.approx(0.70)
    assert payouts["411"].platform_cut == pytest.approx(0.30)
    assert payouts["wx"].owner_cut == pytest.approx(1.00)
    assert payouts["wx"].platform_cut == pytest.approx(0.00)
    assert k.platform_revenue() == pytest.approx(0.30)


def test_kiosk_rejects_unknown_code_share_and_closed_session():
    k = _kiosk_with_services()
    tok = k.open_session()
    with pytest.raises(kiosk.KioskError):
        k.use(tok, "999")
    with pytest.raises(kiosk.KioskError):
        kiosk.Service(
            code="x",
            name="x",
            owner="o",
            price_per_unit=1.0,
            owner_share=1.5,
            handler=lambda t, u: "",
        )
    k.close_session(tok)
    with pytest.raises(kiosk.KioskError):
        k.use(tok, "411")


# ---------------------------------------------------------------------------
# roundtable
# ---------------------------------------------------------------------------


def _seeded_roundtable():
    rt = roundtable.RoundTable("levi-commons")
    rt.add_topic("growth", "raising baby levi", curator="chauncey")
    th = rt.open_thread("growth", "first words", opened_by="chauncey")
    m1 = rt.post("growth", th.id, "chauncey", "the loop must stay honest")
    m2 = rt.post(
        "growth", th.id, "levi", "agreed, honesty is load-bearing", references=[m1.id]
    )
    rt.post(
        "growth", th.id, "levi", "also: watermark everything", references=[m1.id, m2.id]
    )
    return rt, th


def test_roundtable_community_memory_ranks_by_references():
    rt, _ = _seeded_roundtable()
    mem = rt.community_memory("growth", n=5)
    assert mem[0].text == "the loop must stay honest"  # most cited
    assert mem[0].citations == 2
    assert mem[1].citations == 1


def test_roundtable_memory_seeds_from_earliest_when_uncited(tmp_path):
    rt = roundtable.RoundTable("quiet")
    rt.add_topic("meta", "about", curator="c")
    th = rt.open_thread("meta", "hello", opened_by="c")
    rt.post("meta", th.id, "c", "first")
    rt.post("meta", th.id, "c", "second")
    mem = rt.community_memory("meta")
    assert [m.text for m in mem] == ["first", "second"]


def test_roundtable_persistence_roundtrip(tmp_path):
    rt, _ = _seeded_roundtable()
    p = rt.save(tmp_path / "rt.json")
    assert json.loads(p.read_text())
    rt2 = roundtable.RoundTable.load(p)
    assert rt2.pulse("growth") == rt.pulse("growth")
    mem = rt2.community_memory("growth")
    assert mem[0].citations == 2


# ---------------------------------------------------------------------------
# hearth
# ---------------------------------------------------------------------------


def _hearth():
    h = hearth.Hearth()
    h.join("chauncey")
    h.join("levi")
    h.make_host("levi")
    return h


def test_hearth_own_words_author_edit_keeps_history():
    h = _hearth()
    th = h.open_thread("general", "welcome", by="chauncey")
    p = h.post(th.id, "chauncey", "first draft")
    h.edit_post(p.id, by="chauncey", new_body="second draft")
    assert p.body == "second draft"
    hist = h.history(p.id)
    assert [b for _, b in hist] == ["first draft", "second draft"]  # history visible


def test_hearth_norm_violations_are_code_not_etiquette():
    h = _hearth()
    th = h.open_thread("general", "welcome", by="chauncey")
    p = h.post(th.id, "chauncey", "my words")
    with pytest.raises(hearth.NormViolation):
        h.edit_post(p.id, by="levi", new_body="tampered")  # not the author
    with pytest.raises(hearth.NormViolation):
        h.edit_as_host(p.id, by="levi", new_body="host rewrite")  # hosts can't rewrite
    with pytest.raises(hearth.NormViolation):
        h.reattribute(p.id, "levi", by="levi")  # authorship immutable
    assert p.body == "my words"  # untouched


def test_hearth_hosts_steward_threads_and_identities_persist():
    h = _hearth()
    th = h.open_thread("general", "welcome", by="chauncey")
    h.flag_thread(th.id, by="levi")
    assert th.flagged
    h.close_thread(th.id, by="levi")
    assert th.closed
    with pytest.raises(hearth.NormViolation):
        h.post(th.id, "chauncey", "too late")  # closed: no new words
    with pytest.raises(hearth.NormViolation):
        h.join("chauncey")  # identities don't get recycled
    with pytest.raises(hearth.NormViolation):
        h.close_thread(th.id, by="chauncey")  # not a host


# ---------------------------------------------------------------------------
# metaphor
# ---------------------------------------------------------------------------


def test_metaphor_worked_mapping_speaks_in_radio_voice():
    m = metaphor.channels_metaphor()
    line = m.speak("reflect")
    assert "channel 3" in line  # metaphor term, not the jargon
    assert "reflect" not in line.split("—")[0]
    assert m.covers("schedule") == "channel 7"


def test_metaphor_discipline_rejects_double_mapping_and_invention():
    with pytest.raises(metaphor.MetaphorError):
        metaphor.define_metaphor("bad", "x", {"a": "ask", "b": "ask"})  # 1:1 enforced
    m = metaphor.channels_metaphor()
    assert "plan" in [c for c in metaphor.LEVI_CAPABILITIES]  # sanity
    assert m.uncovered(["ask", "teleport"]) == ["teleport"]  # honest gap
    with pytest.raises(metaphor.MetaphorError):
        m.speak("teleport")  # never invents


def test_metaphor_explain_renders_all_capabilities_and_template():
    m = metaphor.channels_metaphor()
    lines = metaphor.explain(m)
    assert len(lines) == len(metaphor.LEVI_CAPABILITIES)
    assert any("squelch" in line for line in lines)
    assert "define_metaphor" in metaphor.METAPHOR_TEMPLATE  # template ships


# ---------------------------------------------------------------------------
# roomscript
# ---------------------------------------------------------------------------


def _party_room():
    return roomscript.Room(
        name="lobby",
        width=10,
        height=10,
        script="""
# the house rules
on enter: say "Welcome, {name}!"
on say hello: say "Hey there, {name}."
on say /dance/: emote "does a little jig"
on enter: move 2 1
""",
    )


def test_roomscript_enter_fires_greeting_and_move():
    r = _party_room()
    fired = r.enter("chauncey", x=0, y=0)
    kinds = [e.kind for e in fired]
    assert "say" in kinds and "move" in kinds
    assert any("Welcome, chauncey!" in e.text for e in fired)
    av = r.avatars["chauncey"]
    assert (av.x, av.y) == (2, 1)


def test_roomscript_say_triggers_literal_and_regex():
    r = _party_room()
    r.enter("levi")
    r.log.clear()
    fired = r.say("levi", "hello everyone")
    assert any("Hey there, levi." in e.text for e in fired)
    fired2 = r.say("levi", "time to dance!")
    assert any("does a little jig" in e.text for e in fired2)
    assert r.log[0].kind == "say" and r.log[0].text == "hello everyone"  # speech logged


def test_roomscript_bad_script_raises_and_room_serializes():
    with pytest.raises(roomscript.RoomScriptError):
        roomscript.Room("bad", script="on frobnicate: explode")
    r = _party_room()
    r.enter("a", x=3, y=4)
    r.place_prop(roomscript.Prop("couch", 5, 5, "comfy"))
    data = r.to_dict()
    r2 = roomscript.Room.from_dict(data)
    assert r2.name == "lobby"
    # enter(3,4) also fired the script's "on enter: move 2 1" rule -> (5,5)
    assert (r2.avatars["a"].x, r2.avatars["a"].y) == (5, 5)
    assert r2.props["couch"].description == "comfy"
    assert len(r2.rules) == len(r.rules)  # script survived the trip


# ---------------------------------------------------------------------------
# commons
# ---------------------------------------------------------------------------


def test_commons_boards_persist_and_notes_are_author_owned():
    c = commons.Commons("test")
    n = c.post_note("ideas", "chauncey", "build the thing")
    assert c.boards["ideas"].notes[n.id].text == "build the thing"
    c.edit_note("ideas", n.id, "chauncey", "build the thing, carefully")
    assert c.boards["ideas"].notes[n.id].text.endswith("carefully")
    with pytest.raises(PermissionError):
        c.edit_note("ideas", n.id, "levi", "hijack")


def test_commons_presence_tracks_who_views_what():
    c = commons.Commons("test")
    c.join("chauncey")
    c.join("levi")
    c.view("chauncey", "ideas")
    c.view("levi", "ideas")
    here = {p.member: p.viewing for p in c.who_here()}
    assert here == {"chauncey": "ideas", "levi": "ideas"}
    assert set(c.viewers_of("ideas")) == {"chauncey", "levi"}
    c.leave("levi")
    assert [p.member for p in c.who_here()] == ["chauncey"]


def test_commons_feed_notifies_subscribers_in_order():
    c = commons.Commons("test")
    seen = []
    c.subscribe(lambda ev: seen.append((ev.seq, ev.kind)))
    c.join("chauncey")
    c.post_note("ideas", "chauncey", "hello")
    assert [k for _, k in seen] == ["join", "post"]
    assert [s for s, _ in seen] == [1, 2]  # ordered sequence
    assert c.feed[-1].detail.startswith("chauncey posted")


def test_commons_snapshot_roundtrip():
    c = commons.Commons("test")
    c.join("chauncey")
    c.view("chauncey", "ideas")
    c.post_note("ideas", "chauncey", "keep this")
    c2 = commons.Commons.from_dict(c.to_dict())
    assert set(c2.boards) == {"ideas"}
    assert c2.who_here()[0].viewing == "ideas"
    assert list(c2.boards["ideas"].notes.values())[0].text == "keep this"
