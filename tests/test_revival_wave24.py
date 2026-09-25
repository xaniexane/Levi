"""Wave 24 tests: resurrection (c) — dead-web social mechanics, honest remix."""

import json

import pytest

from core.levi.revival import magic_words
from core.levi.revival.charity_sink import CharitySink, CharitySinkError
from core.levi.revival.eprops_blogrings import (
    BlogringError,
    Blogrings,
    EProps,
    EPropsError,
)
from core.levi.revival.friends_digest import Audience, SocialGraph
from core.levi.revival.intimacy_circles import (
    CircleDeck,
    IntimacyCircle,
    IntimacyError,
)
from core.levi.revival.magic_words import MagicWordComposer
from core.levi.revival.start_page import StartPage, StartPageError


# --- magic words ---------------------------------------------------------


def test_magic_word_poll_builds_widget():
    c = MagicWordComposer(seed=7)
    w = c.compose("/poll lunch? | tacos | sushi | salad")
    assert w is not None and w.kind == "poll"
    assert w.payload["options"] == ["tacos", "sushi", "salad"]
    assert w.title == "lunch?"


def test_magic_word_dice_rolls_in_range():
    c = MagicWordComposer(seed=7)
    w = c.compose("/dice 2d6+3")
    assert w.kind == "dice"
    assert all(1 <= r <= 6 for r in w.payload["rolls"])
    assert w.payload["total"] == sum(w.payload["rolls"]) + 3
    assert w.payload["notation"] == "2d6+3"


def test_magic_word_remind_parses_offset():
    c = MagicWordComposer()
    w = c.compose("/remind water the plants @ in 20m")
    assert w.kind == "remind"
    assert w.payload["text"] == "water the plants"
    assert w.payload["due_epoch"] > 0


def test_magic_word_unknown_suggests():
    c = MagicWordComposer()
    w = c.compose("/gfi cats")
    assert w.kind == "error"
    assert "gif" in w.payload["did_you_mean"]
    assert c.compose("just a normal message") is None


# --- intimacy circles ----------------------------------------------------


def test_circle_cap_enforced_at_dunbar_layer():
    circle = IntimacyCircle("inner-ring", layer="inner")
    for i in range(5):
        circle.add(f"person-{i}")
    assert circle.is_full()
    with pytest.raises(IntimacyError):
        circle.add("person-5")


def test_share_visible_only_to_members():
    circle = IntimacyCircle("close-ones", layer="close")
    circle.add("amy")
    circle.add("ben")
    share = circle.share("secret plans", "amy")
    assert share.visible_to == {"amy", "ben"}
    assert circle.recent("zoe") == []
    assert [s.id for s in circle.recent("ben")] == [share.id]


def test_nonmember_cannot_share():
    circle = IntimacyCircle("kindred", layer="kindred")
    circle.add("amy")
    with pytest.raises(IntimacyError):
        circle.share("hello", "zoe")


def test_deck_feed_spans_circles():
    deck = CircleDeck("amy")
    a = deck.create("inner", layer="inner")
    b = deck.create("close", layer="close")
    a.add("amy")
    b.add("amy")
    b.add("ben")
    s1 = deck.share_to("inner", "inner thought")
    s2 = deck.share_to("close", "close thought")
    assert s1.circle == "inner" and s2.circle == "close"
    feed = deck.feed("ben")
    assert [s.id for s in feed] == [s2.id]
    assert deck.feed("amy")[0].id == s2.id


# --- friends digest ------------------------------------------------------


def _mutual(graph, a, b):
    assert graph.request(a, b) is True
    assert graph.accept(b, a) is True


def test_friendship_requires_mutual_accept():
    g = SocialGraph()
    assert g.request("amy", "ben") is True
    assert g.are_friends("amy", "ben") is False
    assert g.accept("ben", "amy") is True
    assert g.are_friends("amy", "ben") is True


def test_friends_locked_post_hidden_from_strangers():
    g = SocialGraph()
    _mutual(g, "amy", "ben")
    p = g.post("amy", "locked note", audience=Audience.FRIENDS)
    assert g.visible_to(p, "ben") is True
    assert g.visible_to(p, "zoe") is False
    assert g.visible_to(p, "amy") is True  # author always sees


def test_digest_is_reverse_chron_and_unranked():
    g = SocialGraph()
    _mutual(g, "amy", "ben")
    p1 = g.post("amy", "first", audience=Audience.PUBLIC)
    p2 = g.post("ben", "second", audience=Audience.FRIENDS)
    p3 = g.post("amy", "friends-only", audience=Audience.FRIENDS)
    digest = g.digest("zoe")
    assert [p.id for p in digest] == [p1.id]  # stranger sees public only
    digest = g.digest("ben")
    assert [p.id for p in digest] == [p3.id, p2.id, p1.id]


def test_named_audience_restricts_to_list():
    g = SocialGraph()
    p = g.post("amy", "for zoe", audience=Audience.NAMED, named=["zoe"])
    assert g.visible_to(p, "zoe") is True
    assert g.visible_to(p, "ben") is False


# --- charity sink -------------------------------------------------------


def test_earn_mints_and_caps_per_event():
    sink = CharitySink()
    assert sink.earn("amy", 50, kind="tending", note="weeded the commons") == 25
    assert sink.balance("amy") == 25


def test_donate_destroys_credits_atomically():
    sink = CharitySink()
    sink.add_cause("lunch money", "school lunches")
    sink.earn("amy", 25)
    entry = sink.donate("amy", "lunch money", 10)
    assert entry.amount == -10
    assert sink.balance("amy") == 15
    assert sink.get_cause("lunch money").received == 10
    assert sink.lifetime_sunk("amy") == 10
    with pytest.raises(CharitySinkError):
        sink.donate("amy", "lunch money", 999)  # overdraft refused
    assert sink.balance("amy") == 15  # failed donation changed nothing


def test_earn_ceiling_blocks_grinding():
    sink = CharitySink()
    for _ in range(4):
        sink.earn("amy", 25)
    assert sink.balance("amy") == 100
    with pytest.raises(CharitySinkError):
        sink.earn("amy", 1)


def test_unknown_cause_rejected():
    sink = CharitySink()
    sink.earn("amy", 10)
    with pytest.raises(CharitySinkError):
        sink.donate("amy", "nope", 5)


# --- eprops + blogrings --------------------------------------------------


def test_eprop_requires_note_and_counts():
    props = EProps()
    p = props.give("amy", "ben", "that essay was sharp")
    assert p.giver == "amy" and p.receiver == "ben"
    assert props.tally() == {"ben": 1}
    with pytest.raises(EPropsError):
        props.give("amy", "ben", "   ")  # note is the point
    with pytest.raises(EPropsError):
        props.give("amy", "amy", "self love")  # no self-props


def test_eprop_rate_limits():
    props = EProps()
    for i in range(10):
        props.give("amy", f"person-{i}", f"good work {i}")
    with pytest.raises(EPropsError):
        props.give("amy", "person-10", "one too many")
    with pytest.raises(EPropsError):
        props.give("amy", "person-0", "again today")  # one per pair per day


def test_blogring_vouch_gates_entry():
    rings = Blogrings()
    rings.found("slowweb", "slow web essays", "amy")
    with pytest.raises(BlogringError):
        rings.vouch("slowweb", "zoe", "zoe")  # non-member cannot vouch
    rings.vouch("slowweb", "ben", "amy")
    assert rings.get("slowweb").members == ["amy", "ben"]
    assert rings.get("slowweb").vouches["ben"] == "amy"


def test_blogring_webring_traversal_and_handover():
    rings = Blogrings()
    rings.found("slowweb", "slow web essays", "amy")
    rings.vouch("slowweb", "ben", "amy")
    rings.vouch("slowweb", "cy", "ben")
    prev_, next_ = rings.neighbors("slowweb", "ben")
    assert (prev_, next_) == ("amy", "cy")
    rings.hand_over("slowweb", "ben", by="amy")
    assert rings.get("slowweb").curator == "ben"
    with pytest.raises(BlogringError):
        rings.leave("slowweb", "ben")  # curator cannot leave


# --- start page ----------------------------------------------------------


def test_start_page_widget_lifecycle():
    page = StartPage("amy")
    w = page.add_widget("todo", title="Today")
    page.configure(
        w.id, items=[{"text": "write", "done": True}, {"text": "rest", "done": False}]
    )
    assert page.render_widget(w.id) == "1/2 done"
    assert page.remove_widget(w.id) is True
    assert page.find(w.id) is None


def test_start_page_tabs_and_collision():
    page = StartPage("amy")
    page.add_tab("Work")
    page.switch("Work")
    a = page.add_widget("note", row=0, col=0)
    b = page.add_widget("note", row=0, col=0)  # collides -> shifts down
    assert (a.row, a.col) == (0, 0)
    assert (b.row, b.col) == (0 + 1, 0) or b.row > a.row
    assert [w.id for w in page.deck()] == [a.id, b.id]
    page.rename_tab("Work", "Day Job")
    assert "Day Job" in page.tabs


def test_start_page_json_roundtrip():
    page = StartPage("amy")
    page.add_widget("links", config={"links": [{"label": "levi", "url": "x"}]})
    data = page.to_json()
    obj = json.loads(data)
    assert obj["owner"] == "amy"
    restored = StartPage.from_json(data)
    assert restored.owner == "amy"
    assert len(restored.deck()) == 1
    assert restored.deck()[0].type == "links"


def test_start_page_custom_type_and_guards():
    page = StartPage("amy")
    page.register_type("greeting", lambda cfg: f"hi {cfg.get('name', 'there')}")
    w = page.add_widget("greeting", config={"name": "amy"})
    assert page.render_widget(w.id) == "hi amy"
    with pytest.raises(StartPageError):
        page.add_widget("nope")
    with pytest.raises(StartPageError):
        page.remove_tab("Home")  # cannot remove the last tab
    assert magic_words.ORIGIN == "levi-revival/magic-words"
