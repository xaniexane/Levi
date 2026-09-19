"""Tests for revival wave 22 — resurrection (a): dead-web social mechanics."""

from datetime import timedelta

import pytest

from core.levi.revival import (
    attribution_chains,
    audience_circles,
    away_messages,
    folksonomy_tagging,
    reader_inbox,
    stumble_button,
    symmetric_voting,
)


# ---------------------------------------------------------------------------
# reader_inbox


def test_reader_origins():
    assert reader_inbox.ORIGIN == "levi-revival/reader-inbox"


def test_reader_chronological_newest_first_no_ranking():
    r = reader_inbox.Reader()
    r.add_entry("old", "blog-a")
    r.add_entry("new", "blog-a")
    titles = [e.title for e in r.timeline()]
    assert titles == ["new", "old"]


def test_reader_star_share_and_graph():
    r = reader_inbox.Reader()
    e = r.add_entry("essay", "zine", tags=["slow"])
    r.star(e.id)
    share = r.share_with_notes(e.id, "chauncey", "mimi", "read this slowly")
    assert share.note == "read this slowly"
    assert r.shares_for("mimi") == [share]
    assert r.shares_for("stranger") == []
    graph = r.reading_graph()
    assert graph["sources"] == {"zine": 1}
    assert graph["starred_count"] == 1
    assert graph["shares_sent"] == 1


def test_reader_share_needs_note_and_valid_refs():
    r = reader_inbox.Reader()
    e = r.add_entry("essay", "zine")
    with pytest.raises(reader_inbox.ReaderError):
        r.share_with_notes(e.id, "a", "b", "   ")
    with pytest.raises(reader_inbox.ReaderError):
        r.share_with_notes(999, "a", "b", "note")


def test_reader_unread_flow():
    r = reader_inbox.Reader()
    a = r.add_entry("a", "s")
    b = r.add_entry("b", "s")
    r.mark_read(a.id)
    assert [e.id for e in r.unread()] == [b.id]
    assert len(r) == 2


# ---------------------------------------------------------------------------
# audience_circles


def test_circles_origins():
    assert audience_circles.ORIGIN == "levi-revival/audience-circles"


def test_circles_default_first_question():
    g = audience_circles.Circles(owner="chauncey")
    g.add_circle("family")
    g.add_member("family", "mimi")
    # default answers "who is this for?" with the private circle
    default = audience_circles.Audience.default_for(g)
    assert default.resolve(g) == frozenset({"chauncey"})
    g.set_default_circle("family")
    assert audience_circles.Audience.default_for(g).resolve(g) == frozenset({"mimi"})


def test_circles_grammar_combine_exclude():
    g = audience_circles.Circles(owner="chauncey")
    g.add_circle("crew")
    g.add_member("crew", "ana")
    g.add_member("crew", "bo")
    g.add_circle("kin")
    g.add_member("kin", "cy")
    aud = audience_circles.Audience.to("crew").combine(
        audience_circles.Audience.to("kin")
    )
    assert aud.resolve(g) == frozenset({"ana", "bo", "cy"})
    trimmed = audience_circles.Audience.to("crew").exclude("bo")
    assert trimmed.resolve(g) == frozenset({"ana"})
    assert not trimmed.visible_to("bo", g)
    assert trimmed.visible_to("ana", g)
    only = audience_circles.Audience.only("ana")
    assert only.resolve(g) == frozenset({"ana"})
    assert "ana" in only.explain(g)


def test_circles_refuses_unknown_and_private_tamper():
    g = audience_circles.Circles()
    with pytest.raises(audience_circles.CirclesError):
        g.add_member("nope", "x")
    with pytest.raises(audience_circles.CirclesError):
        g.remove_member("me", "me")
    with pytest.raises(audience_circles.CirclesError):
        g.set_default_circle("nope")


def test_circles_to_all_and_explain():
    g = audience_circles.Circles(owner="chauncey")
    g.add_circle("c1")
    g.add_member("c1", "z")
    aud = audience_circles.Audience.to_all()
    assert aud.resolve(g) == frozenset({"chauncey", "z"})
    assert "z" in aud.explain(g)


# ---------------------------------------------------------------------------
# away_messages


def test_away_origins():
    assert away_messages.ORIGIN == "levi-revival/away-messages"


def test_away_no_reply_obligation_declared():
    b = away_messages.Board()
    m = b.set("chauncey", "deep in build mode")
    assert m.expects_reply is False
    assert b.current("chauncey").mood == "deep in build mode"
    assert [x.person for x in b.visible_board()] == ["chauncey"]


def test_away_expiry_falls_off_on_read():
    b = away_messages.Board()
    b.set("ana", "lunch", ttl=timedelta(seconds=1))
    b.set("bo", "heads down")  # no ttl: stays
    assert len(b.visible_board()) == 2
    b.purge_expired()
    # ttl not yet passed: still there (lazy, honest)
    assert b.current("ana") is not None
    # force expiry in the past via a later reference time
    from datetime import datetime, timezone

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert b.current("ana", at=future) is None
    assert b.current("bo", at=future) is not None
    assert b.history("ana")[0].mood == "lunch"


def test_away_clear_is_voluntary_and_validated():
    b = away_messages.Board()
    assert b.clear("ghost") is False
    b.set("chauncey", "afk")
    assert b.clear("chauncey") is True
    assert b.current("chauncey") is None
    with pytest.raises(away_messages.BoardError):
        b.set("x", "   ")
    with pytest.raises(away_messages.BoardError):
        b.set("x", "ok", ttl=timedelta(seconds=-5))


# ---------------------------------------------------------------------------
# stumble_button


def test_stumble_origins():
    assert stumble_button.ORIGIN == "levi-revival/stumble-button"


def test_stumble_seeded_draw_is_reproducible():
    def stocked(seed):
        v = stumble_button.Vault(seed=seed)
        v.add("a1", "archive")
        v.add("b1", "bookmarks")
        v.add("a2", "archive")
        return v

    v1, v2 = stocked(7), stocked(7)
    first = [v1.stumble().title for _ in range(10)]
    second = [v2.stumble().title for _ in range(10)]
    assert first == second
    assert set(first) <= {"a1", "a2", "b1"}


def test_stumble_delight_is_only_metric_and_biases_gently():
    v = stumble_button.Vault(seed=1)
    v.add("a1", "archive")
    v.add("b1", "bookmarks")
    for _ in range(20):
        art = v.stumble()
        v.record_reaction(art.id, delighted=(art.collection == "archive"))
    rates = v.delight_rates()
    assert rates["archive"] > rates["bookmarks"]
    # unknown shelves still get drawn: smoothing keeps the button surprising
    assert rates["bookmarks"] > 0
    assert v.stats()["draws"]["archive"] + v.stats()["draws"]["bookmarks"] == 20


def test_stumble_empty_vault_and_validation():
    v = stumble_button.Vault()
    with pytest.raises(stumble_button.VaultError):
        v.stumble()
    with pytest.raises(stumble_button.VaultError):
        v.add("", "archive")
    with pytest.raises(stumble_button.VaultError):
        v.record_reaction(42, True)


# ---------------------------------------------------------------------------
# symmetric_voting


def test_voting_origins():
    assert symmetric_voting.ORIGIN == "levi-revival/symmetric-voting"


def test_voting_bury_is_symmetric_and_tiers_are_transparent():
    s = symmetric_voting.Surface(
        policy=symmetric_voting.Policy(promote_at=2, bury_at=-2, quorum=2)
    )
    item = s.add_item("essay")
    s.upvote(item.id, "ana")
    s.bury(item.id, "bo")
    s.upvote(item.id, "cy")
    st = s.standing(item.id)
    assert st["upvotes"] == 2 and st["buries"] == 1 and st["score"] == 1
    # quorum=2 met, score 1: below promote_at=2, both verbs present -> contested
    assert st["tier"] == "contested"
    s.upvote(item.id, "dee")
    assert s.standing(item.id)["tier"] == "rising"


def test_voting_sunk_tier_and_one_vote_per_verb():
    s = symmetric_voting.Surface(
        policy=symmetric_voting.Policy(promote_at=3, bury_at=-2, quorum=2)
    )
    item = s.add_item("hot take")
    s.bury(item.id, "ana")
    s.bury(item.id, "bo")
    assert s.standing(item.id)["tier"] == "sunk"
    with pytest.raises(symmetric_voting.SurfaceError):
        s.bury(item.id, "ana")  # already buried: one vote per verb
    # changing mind moves the vote, not doubles it
    s.change_vote(item.id, "ana", "up")
    st = s.standing(item.id)
    assert st["upvotes"] == 1 and st["buries"] == 1 and st["total_votes"] == 2
    s.retract(item.id, "bo")
    assert s.standing(item.id)["total_votes"] == 1
    assert s.standing(item.id)["tier"] == "new"  # below quorum again


def test_voting_ranked_and_policy_visible():
    s = symmetric_voting.Surface()
    s.add_item("low")
    high = s.add_item("high")
    s.upvote(high.id, "a")
    order = [st["title"] for st in s.ranked()]
    assert order == ["high", "low"]
    p = s.policy()
    assert p.promote_at > p.bury_at and p.quorum >= 1
    with pytest.raises(symmetric_voting.SurfaceError):
        symmetric_voting.Policy(promote_at=1, bury_at=1)


# ---------------------------------------------------------------------------
# folksonomy_tagging


def test_folksonomy_origins():
    assert folksonomy_tagging.ORIGIN == "levi-revival/folksonomy-tagging"


def test_folksonomy_human_tagging_and_tag_pages():
    g = folksonomy_tagging.Garden()
    i1 = g.add_item("slow web essay")
    i2 = g.add_item("indie reader")
    assert g.tag(i1.id, "Slow  Web", "chauncey") == "slow web"
    g.tag(i2.id, "slow web", "mimi")
    g.tag(i1.id, "essay", "chauncey")
    page = g.tag_page("slow web")
    assert page["count"] == 2
    assert {t for t, _ in page["related"]} == {"essay"}
    assert g.tags_of(i1.id) == {"slow web": "chauncey", "essay": "chauncey"}
    # no synonym merging: human words stay human words
    assert g.search("slow") == []


def test_folksonomy_tag_search_alerts_pull_not_push():
    g = folksonomy_tagging.Garden()
    g.subscribe("mimi", "slow web")
    i = g.add_item("new essay")
    assert g.pending_alerts("mimi") == []  # subscribed before the tagging
    g.tag(i.id, "slow web", "chauncey")
    alerts = g.pending_alerts("mimi")
    assert len(alerts) == 1
    assert alerts[0]["item_title"] == "new essay"
    assert alerts[0]["tagged_by"] == "chauncey"
    assert g.acknowledge("mimi") == 1
    assert g.pending_alerts("mimi") == []


def test_folksonomy_untag_and_validation():
    g = folksonomy_tagging.Garden()
    i = g.add_item("essay")
    g.tag(i.id, "slow web", "chauncey")
    with pytest.raises(folksonomy_tagging.GardenError):
        g.tag(i.id, "slow web", "mimi")  # already carried
    g.untag(i.id, "slow web", "chauncey")
    assert g.tags_of(i.id) == {}
    assert [e.action for e in g.tag_history(i.id)] == ["tagged", "untagged"]
    with pytest.raises(folksonomy_tagging.GardenError):
        g.tag(i.id, "   ", "x")
    assert g.unsubscribe("nobody", "slow web") is False


# ---------------------------------------------------------------------------
# attribution_chains


def test_attribution_origins():
    assert attribution_chains.ORIGIN == "levi-revival/attribution-chains"


def test_attribution_trail_newest_first_with_taken_notes():
    L = attribution_chains.Ledger()
    root = L.add_idea("the web is for readers", "ursula")
    mid = L.derive(
        "quiet social layers",
        "chauncey",
        sources=[(root.id, "the reader-first premise")],
    )
    leaf = L.derive(
        "reader inbox v2",
        "mimi",
        sources=[
            (mid.id, "quiet-share mechanic"),
            (root.id, "reader-first premise, restated"),
        ],
    )
    trail = L.trail(leaf.id)
    assert [t["id"] for t in trail] == [mid.id, root.id]
    assert trail[0]["taken"] == "quiet-share mechanic"
    assert trail[0]["depth"] == 1
    # root is also a DIRECT source of leaf: listed once, at shallowest depth
    assert trail[1]["depth"] == 1 and trail[1]["taken"] == (
        "reader-first premise, restated"
    )
    assert [r.id for r in L.roots(leaf.id)] == [root.id]
    assert [d.id for d in L.descendants(root.id)] == [mid.id, leaf.id]


def test_attribution_cycles_refused_sources_immutable():
    L = attribution_chains.Ledger()
    a = L.add_idea("a", "x")
    b = L.derive("b", "y", sources=[(a.id, "the premise")])
    # derive() always creates a NEW child; self/cycle construction is refused
    with pytest.raises(attribution_chains.ChainError):
        L.derive("c", "z", sources=[])
    with pytest.raises(attribution_chains.ChainError):
        L.derive("c", "z", sources=[(b.id, "")])
    with pytest.raises(attribution_chains.ChainError):
        L.derive("c", "z", sources=[(999, "ghost")])
    # parents_of returns immutable Derivation records
    assert L.parents_of(b.id)[0].parent_id == a.id


def test_attribution_credit_heuristic_labeled():
    L = attribution_chains.Ledger()
    root = L.add_idea("root idea", "ursula")
    mid = L.derive("mid", "chauncey", sources=[(root.id, "premise")])
    leaf = L.derive("leaf", "mimi", sources=[(mid.id, "mechanic")])
    credit = L.credit(leaf.id)
    assert credit["mimi"] == 1.0
    assert credit["chauncey"] == 0.5
    assert credit["ursula"] == 0.25
