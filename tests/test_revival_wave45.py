"""Tests for revival wave 45 — folksonomy, dunbar circles, public commons."""

import time

import pytest

from levi.revival.folksonomy import Folksonomy
from levi.revival.link_stacks import LinkStack, StackLibrary
from levi.revival.friend_cap import CappedCircle, CapDenied
from levi.revival.dunbar_layers import DunbarLayers, TierDenied
from levi.revival.public_terminals import MessageBase, Terminal, CATEGORIES
from levi.revival.city_freenet import CityNode, SLA_SECONDS
from levi.revival.rural_bbs import RuralNode


def _pool() -> Folksonomy:
    f = Folksonomy()
    f.add(
        "https://a.example/x",
        "X guide",
        "amy",
        ["python", "guide", "beginner"],
        timestamp=1_000.0,
    )
    f.add(
        "https://b.example/y",
        "Y deep dive",
        "bo",
        ["python", "advanced"],
        timestamp=2_000.0,
    )
    f.add(
        "https://a.example/x",
        "X guide",
        "cy",
        ["python", "reference"],
        timestamp=3_000.0,
    )
    return f


# --- folksonomy ----------------------------------------------------------


def test_folksonomy_add_and_tag_search():
    f = _pool()
    hits = f.search(["python"])
    assert len(hits) == 3
    both = f.search(["python", "guide"])
    assert [b.title for b in both] == ["X guide"]


def test_folksonomy_popular_tags_ranked_by_use():
    f = _pool()
    popular = f.popular_tags(limit=3)
    assert popular[0] == "python"
    assert f.tag_count("python") == 3
    assert f.tag_count("guide") == 1


def test_folksonomy_recency_decay_orders_ties():
    f = Folksonomy(decay_per_day=0.5)
    f.add("https://o.example/1", "Old", "a", ["vintage"], timestamp=1.0)
    f.add("https://o.example/2", "New", "b", ["fresh"], timestamp=time.time())
    assert f.popular_tags(limit=2)[0] == "fresh"


def test_folksonomy_related_and_suggest():
    f = _pool()
    related = f.related_tags("python")
    assert "guide" in related and "beginner" in related
    suggestions = f.suggest_tags(url="https://a.example/x")
    # other people's tags for the same URL get reused
    assert "reference" in suggestions or "guide" in suggestions


def test_folksonomy_remove_withdraws_from_index():
    f = _pool()
    bm = f.search(["advanced"])[0]
    assert f.remove(bm.id) is True
    assert f.search(["advanced"]) == []
    assert f.remove("bm999999") is False


# --- link stacks ---------------------------------------------------------


def test_link_stacks_build_publish_and_fork():
    lib = StackLibrary()
    f = _pool()
    stack = lib.from_pool(f, "Python shelf", "dex", ["python"])
    assert len(stack) == 3
    fresh = f.add("https://c.example/z", "Z notes", "dan", ["python", "notes"])
    stack.add_bookmark(fresh, blurb="start here")
    assert len(stack) == 4
    stack.publish()
    lib.register(stack)
    assert lib.published() == [stack]
    forked = stack.fork("eve")
    assert forked.forked_from == stack.id
    assert len(forked) == len(stack)
    forked.remove(stack.entries[0].bookmark_id)
    assert len(stack) == len(forked) + 1  # original untouched


def test_link_stacks_reorder_and_no_duplicates():
    f = _pool()
    stack = LinkStack("Shelf", "dex")
    bms = f.search(["python"])
    stack.add_bookmark(bms[0])
    stack.add_bookmark(bms[1])
    assert stack.move(bms[1].id, 0) is True
    assert stack.entries[0].bookmark_id == bms[1].id
    with pytest.raises(ValueError):
        stack.add_bookmark(bms[0])  # duplicate denied


def test_link_stacks_most_included_is_use_heuristic():
    lib = StackLibrary()
    f = _pool()
    s1 = lib.from_pool(f, "A", "dex", ["python"])
    s2 = LinkStack("B", "eve")
    popular = f.search(["python"])[0]
    s2.add_bookmark(popular)
    lib.note_inclusion(s1)
    lib.note_inclusion(s2)
    top = lib.most_included(limit=1)
    assert top[0][0] == popular.id and top[0][1] == 2


# --- friend cap ----------------------------------------------------------


def test_friend_cap_deny_closed_at_add_time():
    circle = CappedCircle("hal", cap=2)
    circle.add("amy")
    circle.add("bo")
    assert circle.is_full() is True
    with pytest.raises(CapDenied):
        circle.add("cy")
    assert circle.denials[-1].person == "cy"
    assert "cy" not in circle.members()


def test_friend_cap_removal_makes_room():
    circle = CappedCircle("hal", cap=2)
    circle.add("amy")
    circle.add("bo")
    circle.remove("amy")
    assert circle.add("cy") is True
    assert circle.remaining == 0


def test_friend_cap_pending_request_needs_approval_and_cap():
    circle = CappedCircle("hal", cap=1)
    circle.add("amy")
    circle.request("bo")
    with pytest.raises(CapDenied):
        circle.approve("bo")
    circle.remove("amy")
    assert circle.approve("bo") is True


def test_friend_cap_cannot_shrink_below_membership():
    circle = CappedCircle("hal", cap=50)
    circle.add("amy")
    with pytest.raises(ValueError):
        circle.set_cap(0)
    circle.set_cap(150)
    assert circle.cap == 150


# --- dunbar layers --------------------------------------------------------


def _layers() -> DunbarLayers:
    return DunbarLayers("hal")


def test_dunbar_nesting_required_at_add_time():
    dl = _layers()
    with pytest.raises(TierDenied):
        dl.add_to("inner", "amy")  # not in outer tiers yet
    assert dl.add_to("contacts", "amy") is True
    assert dl.add_to("friends", "amy") is True
    assert dl.add_to("close", "amy") is True
    assert dl.add_to("inner", "amy") is True
    assert dl.tier_of("amy") == "inner"


def test_dunbar_caps_deny_closed():
    dl = DunbarLayers("hal", tiers=[("inner", 1), ("outer", 2)])
    dl.add_to("outer", "amy")
    dl.add_to("outer", "bo")
    dl.add_to("inner", "amy")
    with pytest.raises(TierDenied):
        dl.add_to("inner", "bo")  # inner full
    dl2 = DunbarLayers("hal", tiers=[("inner", 1), ("outer", 1)])
    dl2.add_to("outer", "amy")
    with pytest.raises(TierDenied):
        dl2.add_to("outer", "bo")  # outer full


def test_dunbar_remove_cascades_inward():
    dl = _layers()
    for t in ("contacts", "friends", "close", "inner"):
        dl.add_to(t, "amy")
    dl.remove_from("friends", "amy")
    assert dl.tier_of("amy") == "contacts"  # inner + close + friends gone
    assert dl.verify() == []


def test_dunbar_promote_demote_preserve_invariant():
    dl = _layers()
    dl.add_to("contacts", "amy")
    assert dl.promote("amy", "friends") is True
    assert dl.tier_of("amy") == "friends"
    assert dl.demote("amy", "friends") is True
    assert dl.tier_of("amy") == "contacts"
    with pytest.raises(TierDenied):
        dl.promote("zed", "friends")  # not in outer tier
    assert dl.verify() == []


# --- public terminals -----------------------------------------------------


def test_terminals_session_required():
    base = MessageBase()
    base.post("notices", "Garage sale Saturday", "10am, 5th street")
    term = Terminal(base, location="record-store")
    with pytest.raises(RuntimeError):
        term.search("garage")
    term.begin_session()
    assert term.session_active() is True
    assert len(term.search("garage")) == 1
    term.end_session()
    assert term.session_active() is False


def test_terminals_keyword_search_ranks_matches():
    base = MessageBase()
    base.post("requests", "Need a ladder", "borrowing for a day")
    base.post("offers", "Ladder for sale", "sturdy aluminum ladder")
    base.post("events", "Block party", "music and food")
    hits = base.search("ladder aluminum")
    assert hits[0].headline == "Ladder for sale"  # more word matches first
    assert len(hits) == 2


def test_terminals_browse_and_categories():
    base = MessageBase()
    base.post("offers", "Free tomatoes", "")
    base.post("requests", "Ride to clinic", "")
    assert len(base.browse("offers")) == 1
    assert len(base.browse()) == 2
    with pytest.raises(ValueError):
        base.post("spam", "Nope", "")
    assert set(Terminal(base).categories()) == set(CATEGORIES)


def test_terminals_walkup_post():
    base = MessageBase()
    term = Terminal(base)
    term.begin_session()
    msg = term.post("lost-found", "Lost: greyhound", "answers to Biscuit")
    assert msg.category == "lost-found"
    assert base.search("greyhound")[0].id == msg.id


# --- city freenet ---------------------------------------------------------


def test_freenet_ask_routes_to_volunteer():
    node = CityNode("Springfield", topics=["plumbing", "tutoring"])
    node.register_volunteer("mia", ["plumbing"])
    node.register_volunteer("ned", ["tutoring"])
    q = node.ask("plumbing", "leaky faucet", now=1_000.0)
    assert q.assigned_to == "mia"
    node.answer(q.id, "mia", "Replace the washer.", now=2_000.0)
    assert not q.is_open
    assert node.sla_stats(now=3_000.0)["on_time_rate"] == 1.0


def test_freenet_overdue_reroutes_away():
    node = CityNode("Springfield", topics=["plumbing"])
    node.register_volunteer("mia", ["plumbing"])
    node.register_volunteer("sam", ["plumbing"])
    q = node.ask("plumbing", "burst pipe", now=0.0)
    first = q.assigned_to
    assert q.overdue(now=SLA_SECONDS + 1) is True
    rerouted = node.reroute_overdue(now=SLA_SECONDS + 1)
    assert rerouted == [q]
    assert q.reroutes == 1
    assert q.assigned_to != first  # not the one who let the clock run out
    stats = node.sla_stats(now=SLA_SECONDS + 1)
    assert stats["overdue"] == 1 and stats["open"] == 1


def test_freenet_franchise_template():
    node = CityNode("Springfield", topics=["plumbing", "tutoring"])
    node.register_volunteer("mia", ["plumbing"])
    template = node.export_template()
    assert template["topics"] == ["plumbing", "tutoring"]
    assert "plumbing" in template["roles"]
    new = CityNode.from_template(template, "Shelbyville")
    assert new.city == "Shelbyville"
    assert new.topics == node.topics
    assert new.volunteers == {}  # template carries roles, not people
    with pytest.raises(ValueError):
        new.ask("astrophysics", "stars?")


# --- rural bbs ------------------------------------------------------------


def test_bbs_dial_moves_packets_one_hop():
    a = RuralNode("alpha")
    b = RuralNode("beta")
    a.add_neighbor("beta")
    b.add_neighbor("alpha")
    a.post("general", "Hello", "first post", destination="beta")
    assert a.pending_outbound() == 1
    report = a.dial(b)
    assert report["window_open"] is True
    assert report["sent"] == 1
    assert a.pending_outbound() == 0
    assert [p.subject for p in b.read_board("general")] == ["Hello"]


def test_bbs_flood_traverses_mesh_and_hop_limit_kills_loops():
    a = RuralNode("alpha", max_hops=2)
    b = RuralNode("beta", max_hops=2)
    for x, y in ((a, b), (b, a)):
        x.add_neighbor(y.name)
    a.post("general", "Flood", "to everyone")  # destination=None floods
    report = a.dial(b)
    assert report["sent"] == 1
    # the flood arrived on b's board during the same session ...
    assert [p.subject for p in b.read_board("general")] == ["Flood"]
    # ... and the back-flush in that same session already tried to relay it
    # home, where a had seen it: loops die via the seen set
    assert b.pending_outbound() == 0
    report2 = b.dial(a)
    assert report2["sent"] == 0
    assert len(a.read_board("general")) == 1  # no duplicate delivery


def test_bbs_window_closed_no_transfer():
    a = RuralNode("alpha")
    b = RuralNode("beta")
    # window only 02:00-03:00 local
    a.add_neighbor("beta", window_start=7200.0, window_end=10800.0)
    b.add_neighbor("alpha")
    a.post("general", "Hello", "body", destination="beta")
    report = a.dial(b, now=12 * 3600.0)  # noon: window closed
    assert report["window_open"] is False
    assert a.pending_outbound() == 1  # packet waits for the window


def test_bbs_curriculum_rides_same_transport():
    a = RuralNode("alpha")
    b = RuralNode("beta")
    a.add_neighbor("beta")
    b.add_neighbor("alpha")
    pkt = a.publish_curriculum("Typing basics", ["home row", "speed drills"])
    assert pkt.kind == "curriculum"
    a.dial(b)
    received = b.read_board("curricula")
    assert len(received) == 1
    assert "Lesson 2: speed drills" in received[0].body
