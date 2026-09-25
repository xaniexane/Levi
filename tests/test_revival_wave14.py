"""Wave 14 tests: forge-additions (c) — sovereign code-home features."""

import pytest

from core.levi.revival import capability_protocol as cp
from core.levi.revival import bridging_threads as bt
from core.levi.revival import community_charters as cc
from core.levi.revival import cleanroom_search as cs
from core.levi.revival import mail_triage as mt
from core.levi.revival import remix_studio as rs
from core.levi.revival import goal_recommender as gr


# --------------------------------------------------------------------------
# 1. capability_protocol
# --------------------------------------------------------------------------


def _directory():
    d = cp.CapabilityDirectory("local-authority", secret=b"\x00" * 32)
    d.register_service(
        "notes", lambda action, res, args: f"{action}:{res}", ("read", "write")
    )
    return d


def test_capability_mint_invoke_and_quota():
    d = _directory()
    token = d.mint("alice", "notes", ("read",), quota=2)
    assert d.invoke(token, "read", "note-1") == "read:note-1"
    assert d.invoke(token, "read", "note-2") == "read:note-2"
    with pytest.raises(cp.ProtocolError):  # quota exhausted
        d.invoke(token, "read", "note-3")


def test_capability_deny_closed_and_tamper():
    d = _directory()
    token = d.mint("alice", "notes", ("read",))
    with pytest.raises(cp.ProtocolError):  # token does not grant write
        d.invoke(token, "write")
    tampered = cp.CapabilityToken(**{**token.__dict__, "actions": ("read", "write")})
    with pytest.raises(cp.ProtocolError):  # MAC fails
        d.invoke(tampered, "write")
    wire = token.wire_encode()
    assert d.verify_wire(wire).token_id == token.token_id
    with pytest.raises(cp.ProtocolError):
        d.verify_wire(wire.replace("PROTO/1", "PROTO/9"))


def test_capability_attenuation_cannot_grow():
    d = _directory()
    token = d.mint("alice", "notes", ("read", "write"))
    child = d.delegate(token, "bob", ("read",))
    assert child.grants("notes", "read")
    assert not child.grants("notes", "write")
    with pytest.raises(cp.ProtocolError):  # cannot escalate via attenuation
        token.attenuate("mallory", ("write", "delete"))
    expired = d.mint("alice", "notes", ("read",), ttl_seconds=-1)
    with pytest.raises(cp.ProtocolError):
        d.invoke(expired, "read")


def test_capability_expiry_and_audit():
    d = _directory()
    token = d.mint("alice", "notes", ("read",))
    assert d.invoke(token, "read") == "read:*"
    log = d.audit_log()
    assert any("mint" in entry for entry in log)
    assert any("invoke" in entry for entry in log)


# --------------------------------------------------------------------------
# 2. bridging_threads
# --------------------------------------------------------------------------


def _identities():
    return (
        bt.PortableIdentity("pro-alice", "secret-a", stance="pro"),
        bt.PortableIdentity("con-bob", "secret-b", stance="con"),
        bt.PortableIdentity("pro-carol", "secret-c", stance="pro"),
    )


def test_bridging_ranking_rewards_cross_stance():
    alice, bob, carol = _identities()
    tree = bt.ThreadTree()
    c1 = tree.post(
        alice, "A detailed, well-sourced argument with several paragraphs of reasoning."
    )
    c2 = tree.post(
        carol, "Another solid argument from the same side, also detailed and careful."
    )
    tree.vote(c1.comment_id, 5)
    tree.vote(c2.comment_id, 5)
    tree.endorse(bob, c1.comment_id)  # cross-stance endorsement -> bridging
    tree.endorse(alice, c2.comment_id)  # same-stance -> no bridging
    ranked = tree.rank()
    assert ranked[0] == c1.comment_id
    assert tree.bridging_score(tree._comments[c1.comment_id]) == 1.0
    assert tree.bridging_score(tree._comments[c2.comment_id]) == 0.0


def test_fluff_penalty_demotion():
    alice, bob, carol = _identities()
    tree = bt.ThreadTree()
    fluff = tree.post(bob, "OMG LOL THIS!!! 100%!!!")
    solid = tree.post(
        alice, "Here is a careful analysis with evidence and measured conclusions."
    )
    tree.vote(fluff.comment_id, 3)
    assert bt.ThreadTree.fluff_score("OMG LOL THIS!!! 100%!!!") > 0.5
    assert tree.explain(solid.comment_id)["fluff"] < 0.3
    ranked = tree.rank()
    assert ranked.index(solid.comment_id) < ranked.index(fluff.comment_id)


def test_threading_and_portable_identity():
    alice, bob, _ = _identities()
    tree = bt.ThreadTree()
    root = tree.post(alice, "Root question about the proposal.")
    reply = tree.post(bob, "A reply with some detail.", parent_id=root.comment_id)
    walk = tree.thread(root.comment_id)
    assert walk == [
        (root.comment_id, 0, "Root question about the proposal."),
        (reply.comment_id, 1, "A reply with some detail."),
    ]
    assert alice.identity_id.startswith("key-id:")
    assert alice.identity_id != bob.identity_id
    sig = alice.sign_endorsement(reply.comment_id)
    assert alice.verify_endorsement(reply.comment_id, sig)
    assert not alice.verify_endorsement(reply.comment_id, "deadbeef")
    with pytest.raises(bt.ThreadError):  # no self-endorsement
        tree.endorse(alice, root.comment_id)


# --------------------------------------------------------------------------
# 3. community_charters
# --------------------------------------------------------------------------


def _founders():
    return [
        cc.FounderKey("f1", "sec-one"),
        cc.FounderKey("f2", "sec-two"),
        cc.FounderKey("f3", "sec-three"),
    ]


def test_charter_found_and_quorum_amendment():
    f1, f2, f3 = _founders()
    charter = cc.Charter.found("garden", "a test community", "be kind", [f1, f2, f3])
    assert charter.quorum == 2
    amendment = charter.propose_amendment("f1", "bylaws", "be kind, stay curious")
    charter.sign_amendment(amendment.amendment_id, f1)
    assert charter.bylaws == "be kind"  # one signature is below quorum
    charter.sign_amendment(amendment.amendment_id, f2)
    assert amendment.enacted
    assert charter.bylaws == "be kind, stay curious"
    assert charter.verify_chain()


def test_charter_role_grant_and_mod_tooling():
    f1, f2, f3 = _founders()
    charter = cc.Charter.found("garden", "a test community", "be kind", [f1, f2])
    amendment = charter.propose_amendment("f1", "role", "moderator", target="dana")
    charter.sign_amendment(amendment.amendment_id, f1)
    charter.sign_amendment(amendment.amendment_id, f2)
    assert charter.roles["dana"] == "moderator"
    charter.warn(f1, "dana", "first warning")
    charter.suspend(f1, "erin", "spam", days=7)
    assert charter.member_status("erin") == "suspended"
    assert charter.member_status("dana") == "warned"
    log = charter.mod_log()
    assert [m.kind for m in log] == ["warn", "suspend"]


def test_charter_export_import_roundtrip():
    f1, f2, _ = _founders()
    charter = cc.Charter.found("garden", "a test community", "be kind", [f1, f2])
    amendment = charter.propose_amendment("f1", "purpose", "a kinder test community")
    charter.sign_amendment(amendment.amendment_id, f1)
    charter.sign_amendment(amendment.amendment_id, f2)
    charter.ban(f1, "troll", "harassment")
    data = charter.export()
    restored = cc.Charter.import_charter(data, [f1, f2])
    assert restored.purpose == "a kinder test community"
    assert restored.member_status("troll") == "banned"
    assert restored.verify_chain()
    wrong_keys = [cc.FounderKey("f1", "wrong"), cc.FounderKey("f2", "wrong")]
    with pytest.raises(cc.CharterError):
        cc.Charter.import_charter(data, wrong_keys)


# --------------------------------------------------------------------------
# 4. cleanroom_search
# --------------------------------------------------------------------------


def _search_index():
    idx = cs.CleanroomIndex()
    idx.add_document(
        cs.make_document(
            "d1", "levi brain", "levi synthetic brain trained locally", ("d2",)
        )
    )
    idx.add_document(
        cs.make_document(
            "d2", "levi memory", "levi memory store and journal", ("d1", "d3")
        )
    )
    idx.add_document(
        cs.make_document("d3", "weather report", "rain expected tomorrow afternoon", ())
    )
    idx.compute_authority()
    return idx


def test_search_term_and_link_ranking():
    idx = _search_index()
    results = idx.search("levi brain")
    assert results[0].doc_id == "d1"
    assert results[0].components["term"] > 0
    weather = idx.search("rain")
    assert weather[0].doc_id == "d3"
    assert idx.stats()["documents"] == 3


def test_search_unpersonalized_is_genuine():
    idx = _search_index()
    plain = [r.doc_id for r in idx.search("levi")]
    flagged = [r.doc_id for r in idx.search("levi", personalized=True)]
    assert plain == flagged  # no boost -> identical
    boosted = [
        r.doc_id for r in idx.search("levi", personalized=True, boost={"d3": 50.0})
    ]
    assert boosted[0] == "d3"  # caller-supplied boost only applies when given
    assert "personal_boost" not in idx.explain("levi", "d1")


def test_search_explain_breakdown():
    idx = _search_index()
    detail = idx.explain("levi brain", "d1")
    assert set(detail) >= {"term", "link", "recency", "total"}
    # Total is exactly the auditable combination of the components.
    expect = detail["term"] + idx.link_weight * detail["link"] * 10.0
    assert abs(detail["total"] - expect) < 1e-3
    assert idx.explain("rain", "d3")["term"] > 0
    with pytest.raises(cs.SearchError):
        idx.explain("levi", "nope")


# --------------------------------------------------------------------------
# 5. mail_triage
# --------------------------------------------------------------------------


def _mail_store():
    store = mt.MailStore(clock=lambda: 1_000_000.0)
    store.ingest(
        "boss@work.example",
        "Q3 deadline approaching",
        "The report is due Friday?",
        999_000.0,
    )
    store.ingest(
        "news@list.example", "Weekly newsletter", "Lots of links inside.", 999_500.0
    )
    store.ingest(
        "boss@work.example",
        "Re: Q3 deadline approaching",
        "Reminder: due Friday.",
        999_800.0,
    )
    return store


def test_snooze_and_wake():
    store = _mail_store()
    assert len(store.inbox()) == 3
    store.snooze(2, 2_000_000.0)
    assert {m.msg_id for m in store.inbox()} == {1, 3}
    assert store.wake_due() == []  # nothing due yet
    # Controllable clock: snooze, advance time, wake.
    now = [1_000_000.0]
    timed = mt.MailStore(clock=lambda: now[0])
    timed.ingest("a@b.c", "hi", "body")
    timed.snooze(1, 2_000_000.0)
    assert len(timed.inbox()) == 0
    assert timed.wake_due() == []
    now[0] = 3_000_000.0
    assert timed.wake_due() == [1]
    assert len(timed.inbox()) == 1


def test_bundle_grouping():
    store = _mail_store()
    by_thread = store.bundle("thread")
    assert sorted(by_thread["q3 deadline approaching"]) == [1, 3]
    by_sender = store.bundle("sender")
    assert sorted(by_sender["boss@work.example"]) == [1, 3]
    by_domain = store.bundle("domain")
    assert "list.example" in by_domain
    with pytest.raises(mt.TriageError):
        store.bundle("nope")


def test_smart_reply_and_triage_order():
    store = _mail_store()
    draft = store.smart_reply(1)
    assert draft.template_key == "question"  # first matching rule wins
    assert set(draft.rule_hits) == {"question", "deadline"}
    assert "[your answer here]" in draft.text  # no invented facts
    newsletter = store.smart_reply(2)
    assert newsletter.template_key == "neutral"
    order = [msg_id for msg_id, _ in store.triage()]
    assert order[0] == 1  # deadline + question beats the newsletter
    store.mark_read(1)
    assert [m for m in store.inbox() if m.msg_id == 1][0].read


# --------------------------------------------------------------------------
# 6. remix_studio
# --------------------------------------------------------------------------


def _project():
    studio = rs.RemixStudio()
    project = studio.new_project("demo")
    project.add_clip("/media/a.mp4", 4.0, label="intro")
    project.add_clip("/media/b.mp4", 3.0, label="middle")
    return studio, project


def test_beat_cut_edl_export():
    studio, project = _project()
    studio.apply_template(project, "beat-cut")
    edl = studio.render_edl(project)
    assert edl.schema == rs.EDL_SCHEMA_VERSION
    assert edl.watermark is None
    assert abs(edl.duration_s - 7.0) < 1e-6
    assert edl.segments[0]["transition_in"] == "cut"
    assert studio.verify_no_watermark(edl.to_json())
    assert rs.RemixStudio.list_templates()["beat-cut"].startswith("Cut every clip")


def test_title_intro_caption_card():
    studio, project = _project()
    studio.apply_template(project, "title-intro", title="Hello")
    assert any(c.text == "Hello" and c.style == "title" for c in project.captions)
    studio.apply_template(project, "caption-card")
    assert any(c.style == "card" for c in project.captions)
    timeline = project.timeline()
    assert timeline[0]["at"] == 0.0
    assert timeline == sorted(timeline, key=lambda s: s["at"])


def test_speed_ramp_and_errors():
    studio, project = _project()
    studio.apply_template(project, "speed-ramp")
    speeds = [s["speed"] for s in project.timeline()]
    assert speeds == [1.0, 1.5]
    assert abs(project.duration() - (4.0 + 3.0 / 1.5)) < 1e-6
    with pytest.raises(rs.RemixError):
        studio.apply_template(project, "nope")
    empty = studio.new_project("empty")
    with pytest.raises(rs.RemixError):
        studio.apply_template(empty, "beat-cut")
    with pytest.raises(rs.RemixError):
        empty.add_clip("/x.mp4", -1.0)


# --------------------------------------------------------------------------
# 7. goal_recommender
# --------------------------------------------------------------------------


def _recommender():
    rec = gr.GoalRecommender()
    rec.add_item(
        gr.Item("walk", "evening walk", {"calm": 0.9, "short": 0.8, "social": 0.1})
    )
    rec.add_item(
        gr.Item("party", "big party", {"calm": 0.1, "short": 0.3, "social": 1.0})
    )
    rec.add_item(
        gr.Item("read", "quiet reading", {"calm": 1.0, "short": 0.5, "social": 0.0})
    )
    rec.set_goal(gr.Goal("unwind", {"calm": 1.0, "short": 0.5}, priority=1.0))
    return rec


def test_goal_scoring_transparent():
    rec = _recommender()
    assert rec.item_score("unwind", "walk") > rec.item_score("unwind", "party")
    detail = rec.explain("walk")
    assert detail["per_goal"]["unwind"] == detail["total"]
    assert set(detail["per_attribute"]["unwind"]) == {"calm", "short"}
    ranked = rec.recommend(limit=2)
    assert ranked[0].item_id in ("walk", "read")
    assert ranked[0].score >= ranked[1].score


def test_feedback_moves_weights_visibly():
    rec = _recommender()
    before = rec.item_score("unwind", "party")
    rec.feedback("unwind", "party", liked=True)
    after = rec.item_score("unwind", "party")
    assert after > before  # explicit like nudges toward party's attributes
    assert rec.weight_history()[-1][1] == "liked"
    rec.feedback("unwind", "party", liked=False)
    assert rec.item_score("unwind", "party") < after
    rec.reset_weights("unwind", {"calm": 1.0, "short": 0.5})
    assert rec.item_score("unwind", "party") == before
    assert rec.weight_history()[-1][1] == "reset"


def test_recommender_requires_goals_and_validates():
    rec = gr.GoalRecommender()
    rec.add_item(gr.Item("x", "x", {"calm": 0.5}))
    with pytest.raises(gr.RecommenderError):  # no goals -> no engagement trap fallback
        rec.recommend()
    with pytest.raises(gr.RecommenderError):
        rec.add_item(gr.Item("x", "dup", {"calm": 0.5}))
    with pytest.raises(gr.RecommenderError):
        gr.Goal("", {"calm": 1.0})
    with pytest.raises(gr.RecommenderError):
        rec.feedback("missing", "x", liked=True)
