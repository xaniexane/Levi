"""Wave 35 tests: sovereign reading & discourse mechanisms."""

import pytest

from levi.revival import shared_shelf, share_note, starred_canon, opml_export
from levi.revival import stash, symmetric_downvote, cosy_conferencing, listserv


# ---------------------------------------------------------------- shared_shelf


def _shelf():
    return shared_shelf.SharedShelf("keeper")


def test_shared_shelf_newest_first_pages():
    shelf = _shelf()
    a = shelf.share("u1", "First")
    b = shelf.share("u2", "Second", note="read this")
    assert shelf.page(1) == [b, a]
    assert len(shelf) == 2


def test_shared_shelf_note_and_unread_tracking():
    shelf = _shelf()
    shelf.share("u1", "No note")
    noted = shelf.share("u2", "Noted", note="sharer's take")
    assert shelf.with_notes() == [noted]
    assert shelf.unread_count() == 2
    shelf.mark_read(noted.item_id)
    assert shelf.unread_count() == 1
    assert shelf.search("sharer") == [noted]


def test_shared_shelf_validation_and_remove():
    shelf = _shelf()
    with pytest.raises(ValueError):
        shelf.share("", "title")
    with pytest.raises(ValueError):
        shared_shelf.SharedShelf("")
    item = shelf.share("u1", "Gone")
    shelf.remove(item.item_id)
    assert len(shelf) == 0
    with pytest.raises(KeyError):
        shelf.remove("sh-999")


# ---------------------------------------------------------------- share_note


def _notebook():
    return share_note.ShareNotebook("curator")


def test_share_note_requires_note():
    nb = _notebook()
    with pytest.raises(ValueError):
        nb.share("u", "title", "   ")
    s = nb.share("u", "title", "why this matters")
    assert s.note == "why this matters"
    assert s.revision_count == 1


def test_share_note_revision_history():
    nb = _notebook()
    s = nb.share("u", "title", "first take")
    nb.revise_note(s.share_id, "second take")
    got = nb.get(s.share_id)
    assert got.note == "second take"
    assert got.revision_count == 2
    assert got.note_revisions[0] == "first take"
    with pytest.raises(ValueError):
        nb.revise_note(s.share_id, "")


def test_share_note_search_and_word_count():
    nb = _notebook()
    nb.share("u1", "Alpha", "bright future of radios")
    nb.share("u2", "Beta", "cooking notes")
    assert len(nb.search_notes("radio")) == 1
    assert nb.notes_word_count() == 6
    nb.unshare("sn-1")
    assert len(nb) == 1


# ---------------------------------------------------------------- starred_canon


def _canon():
    return starred_canon.StarredCanon()


def test_starred_canon_keeper_order():
    canon = _canon()
    first = canon.star("u1", "First")
    second = canon.star("u2", "Second")
    assert canon.canon() == [first, second]
    canon.unstar(first.item_id)
    assert len(canon) == 1
    with pytest.raises(KeyError):
        canon.unstar(first.item_id)


def test_starred_canon_annotate_and_tags():
    canon = _canon()
    s = canon.star("u1", "Kept", keeper_note="defend this", tags=["essay"])
    assert s.keeper_note == "defend this"
    assert canon.by_tag("essay") == [s]
    assert canon.by_tag("nope") == []
    assert canon.keepers_notes() == [s]
    canon.tag(s.item_id, "essay")  # no duplicate
    assert s.tags == ["essay"]
    canon.annotate(s.item_id, "new reason")
    assert s.keeper_note == "new reason"


def test_starred_canon_validation():
    canon = _canon()
    with pytest.raises(ValueError):
        canon.star("", "title")
    with pytest.raises(ValueError):
        canon.star("u", "  ")


# ---------------------------------------------------------------- opml_export


def _subs():
    sl = opml_export.SubscriptionList()
    sl.add("Feed A", "https://a.example/feed", "https://a.example", "tech")
    sl.add("Feed B", "https://b.example/feed", category="tech")
    sl.add("Feed C", "https://c.example/feed")
    return sl


def test_opml_export_roundtrip():
    sl = _subs()
    doc = sl.to_opml("keeper")
    assert doc.startswith('<?xml version="1.0"')
    assert "<opml" in doc and "xmlUrl" in doc
    back = opml_export.SubscriptionList.from_opml(doc)
    assert len(back) == 3
    tech = back.in_category("tech")
    assert {s.title for s in tech} == {"Feed A", "Feed B"}
    by_url = {s.xml_url: s for s in back.feeds()}
    assert by_url["https://a.example/feed"].html_url == "https://a.example"


def test_opml_export_categories_and_remove():
    sl = _subs()
    assert len(sl.in_category("tech")) == 2
    assert sl.remove("https://b.example/feed") is True
    assert sl.remove("https://missing.example") is False
    assert len(sl) == 2


def test_opml_export_rejects_bad_input():
    sl = opml_export.SubscriptionList()
    with pytest.raises(ValueError):
        sl.add("", "https://x.example/feed")
    with pytest.raises(ValueError):
        sl.add("Title", "")
    with pytest.raises(ValueError):
        opml_export.SubscriptionList.from_opml("<rss></rss>")


# ---------------------------------------------------------------- stash


def _stash():
    return stash.Stash()


def test_stash_save_and_search():
    st = _stash()
    st.save("u1", "Radio History", "early crystal radio sets", tags=["radio"])
    st.save("u2", "Gardening", "tomato planting guide")
    hits = st.search("radio")
    assert len(hits) == 1
    assert hits[0].title == "Radio History"
    assert st.search("tomato planting")  # snapshot text searched


def test_stash_tags_and_newest():
    st = _stash()
    st.save("u1", "A", tags=["read", "radio"])
    st.save("u2", "B", tags=["radio"])
    assert st.by_tag("radio") == [st.newest(2)[0], st.newest(2)[1]]
    assert set(st.tags()) == {"read", "radio"}
    st.retag("stash-1", ["archive"])
    assert st.by_tag("radio") == [st.newest(1)[0]]
    st.discard("stash-2")
    assert len(st) == 1


def test_stash_validation():
    st = _stash()
    with pytest.raises(ValueError):
        st.save("", "title")
    with pytest.raises(ValueError):
        st.save("u", "")
    with pytest.raises(KeyError):
        st.discard("stash-999")


# ---------------------------------------------------------------- symmetric_downvote


def _front():
    return symmetric_downvote.FrontPage()


def test_symmetric_downvote_net_ranking():
    fp = _front()
    loved = fp.submit("Loved")
    buried = fp.submit("Buried")
    fp.digg(loved.item_id, "v1")
    fp.digg(loved.item_id, "v2")
    fp.digg(buried.item_id, "v1")
    fp.bury(buried.item_id, "v2")
    fp.bury(buried.item_id, "v3")
    order = fp.front_page()
    assert order[0] == loved
    assert buried.buried is True
    # buried item ranks down but never vanishes
    assert buried in order
    assert len(fp) == 2


def test_symmetric_downvote_reversible_and_symmetric():
    fp = _front()
    item = fp.submit("Item")
    fp.bury(item.item_id, "v1")
    fp.digg(item.item_id, "v1")  # switching sides flips the vote
    assert item.diggs == 1 and item.buries == 0
    fp.undigg(item.item_id, "v1")
    assert item.score == 0
    fp.bury(item.item_id, "v2")
    fp.unbury(item.item_id, "v2")
    assert item.buries == 0
    with pytest.raises(KeyError):
        fp.digg("item-999", "v1")


def test_symmetric_downvote_controversial():
    fp = _front()
    hot = fp.submit("Fought over")
    calm = fp.submit("Calm")
    for i in range(5):
        fp.digg(hot.item_id, f"up{i}")
        fp.bury(hot.item_id, f"down{i}")
    fp.digg(calm.item_id, "v1")
    top = fp.controversial()[0]
    assert top == hot


# ---------------------------------------------------------------- cosy_conferencing


def _conf():
    conf = cosy_conferencing.Conference("hw", topic="hardware")
    conf.join("ada", expert=True)
    conf.join("bob")
    return conf


def test_cosy_threading():
    conf = _conf()
    root = conf.post("bob", "Why do chips get hot?")
    reply = conf.post("ada", "Resistance, mostly.", reply_to=root.post_id)
    follow = conf.post("bob", "Thanks!", reply_to=reply.post_id)
    assert conf.roots() == [root]
    assert conf.replies(root.post_id) == [reply]
    assert [p.post_id for p in conf.thread(follow.post_id)] == [
        root.post_id,
        reply.post_id,
        follow.post_id,
    ]


def test_cosy_expert_voice():
    conf = _conf()
    conf.post("ada", "I design chips.")
    conf.post("bob", "I use them.")
    expert_posts = conf.expert_posts()
    assert len(expert_posts) == 1
    assert expert_posts[0].expert_voice is True
    assert expert_posts[0].author == "ada"
    assert [m.handle for m in conf.experts()] == ["ada"]


def test_cosy_membership_rules_and_search():
    conf = _conf()
    with pytest.raises(KeyError):
        conf.post("stranger", "hello")
    p = conf.post("bob", "posting about circuits")
    with pytest.raises(KeyError):
        conf.post("bob", "reply to nothing", reply_to="post-999")
    assert conf.search("circuits") == [p]
    conf.leave("bob")
    with pytest.raises(KeyError):
        conf.post("bob", "gone now")
    with pytest.raises(ValueError):
        cosy_conferencing.Conference("")


# ---------------------------------------------------------------- listserv


def _list():
    server = listserv.ListServer()
    return server.create("RADIO", owner="owner@example")


def test_listserv_command_subscribe_unsubscribe():
    ml = _list()
    reply = ml.receive("amy@example", "SUBSCRIBE RADIO Amy")
    assert "subscribed" in reply
    assert "amy@example" in ml.members
    again = ml.receive("amy@example", "SUBSCRIBE RADIO")
    assert "already" in again
    out = ml.receive("amy@example", "UNSUBSCRIBE RADIO")
    assert "removed" in out
    assert ml.members == []
    assert "HELP" in ml.receive("x@example", "HELP")


def test_listserv_distribution_and_moderation():
    ml = _list()
    ml.subscribe("amy@example")
    msg = ml.distribute("amy@example", "Hi", "first post")
    assert ml.archive == [msg] and not ml.pending
    ml.receive("owner@example", "SET RADIO MODERATED")
    held = ml.distribute("amy@example", "Hi2", "second post")
    assert held.held and ml.pending == [held]
    ml.approve(held.seq)
    assert ml.archive[-1].seq == held.seq and not held.held
    assert ml.pending == []
    with pytest.raises(KeyError):
        ml.approve(999)


def test_listserv_owner_commands_and_review():
    ml = _list()
    ml.receive("owner@example", "ADD RADIO amy@example")
    review = ml.receive("amy@example", "REVIEW RADIO")
    assert "amy@example" in review
    ml.receive("owner@example", "DELETE RADIO amy@example")
    assert ml.members == []
    bad = ml.receive("amy@example", "FROBNICATE RADIO")
    assert "Unknown command" in bad
    # non-owner owner-commands are rejected
    assert "Unknown command" in ml.receive("amy@example", "SET RADIO OPEN")
    # duplicate list names rejected
    server = listserv.ListServer()
    server.create("DUP", owner="o")
    with pytest.raises(ValueError):
        server.create("dup", owner="o")
    assert server.get("DUP") is not None
