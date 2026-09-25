"""Tests for revival wave 36 (community-governance)."""

from datetime import datetime, timedelta, timezone

import pytest

from core.levi.revival import federated_moderation as fm
from core.levi.revival import meetup_scene as ms
from core.levi.revival import paid_community as pc
from core.levi.revival import print_online_loop as pl
from core.levi.revival import status_membership as sm
from core.levi.revival import stewardship_culture as sc


def make_charter(name="general"):
    return fm.Charter(name=name, carried_topics=("general",), refused_lines=("spam",))


def make_federation(**kwargs):
    fed = fm.Federation(**kwargs)
    fed.register_node("alpha", make_charter("alpha"))
    fed.register_node("beta", make_charter("beta"))
    for node_id in ("alpha", "beta"):
        for i in range(3):
            fed.endorse(node_id, f"endorser{i}", "mod1")
        fed.elect_moderator(node_id, "mod1")
    return fed


# -- federated_moderation --------------------------------------------------


def test_federated_heat_score_labels_hot_messages():
    assert fm.heat_score("Hello, nice to see you here.") < fm.heat_score(
        "YOU IDIOT SHUT UP!!! I HATE YOU LOSER"
    )


def test_federated_hot_post_is_held_then_delivered():
    fed = make_federation(cooling_seconds=0)
    result = fed.submit("alpha", "alice", "YOU IDIOT SHUT UP!!! I HATE YOU LOSER")
    assert result["held"] is True
    assert fed.pending_cooling() == 1
    delivered = fed.deliver_due()
    assert delivered == 1
    assert fed.pending_cooling() == 0


def test_federated_shun_and_delink_enforce_without_central_ban():
    fed = make_federation()
    fed.shun("alpha", "troll", "mod1")
    with pytest.raises(fm.FederationError):
        fed.submit("alpha", "troll", "a calm hello")
    fed.delink("beta", "alpha", "mod1")
    assert fed.links("beta") == []
    # beta cut ties with alpha: alpha's traffic no longer reaches beta
    fed.submit("alpha", "ann", "a calm hello")
    assert fed.node("alpha").posts
    assert fed.node("beta").posts == []


# -- paid_community --------------------------------------------------------


def make_commons():
    commons = pc.Commons("test-commons")
    commons.seed_host("host1", "Ada Host", "founders")
    return commons


def test_paid_community_seed_host_and_fee_gate():
    commons = make_commons()
    commons.apply("m1", "Mia Member", "friends-of-ada")
    with pytest.raises(pc.CommonsError):  # fee not paid
        commons.admit("m1", "host1")
    commons.pay_fee("m1", "receipt-001")
    with pytest.raises(pc.CommonsError):  # no vouch yet
        commons.admit("m1", "host1")
    commons.vouch("m1", "host1")
    member = commons.admit("m1", "host1")
    assert member.name == "Mia Member" and member.fee_paid


def test_paid_community_standing_and_probation_lapse():
    commons = make_commons()
    commons.apply("m2", "Moe", "friends")
    commons.pay_fee("m2", "r2")
    commons.vouch("m2", "host1")
    commons.admit("m2", "host1")
    for _ in range(10):
        commons.record_post("m2")
    assert commons.standing("m2") > 0
    commons.probate("m2", "host1", "rule 3")
    commons.probate("m2", "host1", "rule 3")
    result = commons.probate("m2", "host1", "rule 3")
    assert result["status"] == "lapsed"
    assert commons.standing("m2") == -1


def test_paid_community_reinstate_and_census():
    commons = make_commons()
    commons.seed_host("host2", "Zed Host", "founders")
    commons.suspend("host1", "host2", "test")
    commons.reinstate("host1", "host2")
    census = commons.census()
    assert census["hosts"] == 2 and census["active"] == 2
    with pytest.raises(pc.CommonsError):
        commons.admit("ghost", "host1")


# -- status_membership -----------------------------------------------------


def make_gravity():
    gravity = sm.Gravity(max_magnets=2)
    gravity.add_member("m1", "Magnet One")
    gravity.add_member("m2", "Magnet Two")
    gravity.add_member("p1", "Paying One")
    gravity.sponsor_magnet("m1", "keeps the writing scene alive")
    gravity.sponsor_magnet("m2", "runs the weekly jam")
    return gravity


def test_status_membership_gravity_is_explicit_heuristic():
    gravity = make_gravity()
    gravity.record_post("p1", starts_thread=True)
    gravity.endorse("p1", "m1")
    gravity.mark_helpful("p1", "m2")
    g = gravity.gravity_of("p1")
    assert g == 1.0 + 3.0 + 2.0 + 4.0  # posts + thread + endorsement + helpful


def test_status_membership_sponsorship_is_renewable_grant():
    gravity = make_gravity()
    magnet = gravity.member("m1")
    assert magnet.magnet and not magnet.paying
    gravity.renew("m1", False, note="seat rotates this year")
    released = gravity.member("m1")
    assert not released.magnet and released.paying
    assert len(gravity.magnets()) == 1


def test_status_membership_lopsidedness_warns_on_concentration():
    gravity = make_gravity()
    for _ in range(9):
        gravity.record_interaction("p1", "m1")
    gravity.record_interaction("p1", "m2")
    orbits = gravity.orbit("p1")
    assert orbits[0]["target"] == "m1"
    assert gravity.lopsidedness() == 0.9


# -- meetup_scene ------------------------------------------------------------


def make_scene(now=None):
    scene = ms.Scene("test-scene")
    scene.add_steward("stew")
    scene.schedule_meetup("meet1", "First Meet", "hall", "2026-10-01", "stew", now=now)
    return scene


def test_meetup_scene_verified_attendance_builds_credibility():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    scene = make_scene(now=now)
    scene.rsvp("meet1", "alice")
    assert scene.verify_attendance("meet1", "alice", "stew", now=now)
    assert scene.credibility("alice", now=now) == pytest.approx(1.0)
    # older attendance decays
    later = now + timedelta(days=ms.Scene.HALF_LIFE_DAYS)
    assert scene.credibility("alice", now=later) == pytest.approx(0.5, rel=1e-3)


def test_meetup_scene_steward_nomination_requires_showing_up():
    scene = make_scene()
    with pytest.raises(ms.SceneError):
        scene.nominate_steward("ghost", "stew")
    scene.verify_attendance("meet1", "alice", "stew")
    assert scene.nominate_steward("alice", "stew") is True
    assert "alice" in scene.stewards()


def test_meetup_scene_host_multiplier_and_no_shows():
    scene = make_scene()
    scene.record_no_show("meet1", "bob", "stew")
    scene.attach_thread("meet1", "thread:recap")
    report = scene.meetup_report("meet1")
    assert report["no_shows"] == ["bob"]
    assert report["threads"] == ["thread:recap"]
    assert scene.credibility("stew") > scene.credibility("bob")


# -- stewardship_culture -----------------------------------------------------


def make_stewardship():
    st = sc.Stewardship("the-place", "keeper", charter="be kind, share back")
    st.publish_rules(("no spam", "share one per take"))
    st.set_questionnaire(
        [("what do we share?", "knowledge"), ("the keeper's rule?", "be kind")],
        pass_threshold=0.5,
    )
    return st


def test_stewardship_questionnaire_ritual_gates_membership():
    st = make_stewardship()
    assert st.apply("alice", ["knowledge", "be kind"])["passed"] is True
    assert st.is_member("alice")
    result = st.apply("bob", ["nothing", "whatever"])
    assert result["passed"] is False
    assert not st.is_member("bob")


def test_stewardship_ratio_probation_and_recovery():
    st = make_stewardship()
    st.apply("alice", ["knowledge", "be kind"])
    st.record_take("alice")
    st.record_take("alice")
    st.record_share("alice")  # ratio 0.5 == floor: still fine
    assert st.ratio("alice") == pytest.approx(0.5)
    st.record_take("alice")  # ratio 0.333 < floor: probation
    census = st.census()
    assert census["on_probation"] == 1
    st.record_share("alice")  # back above floor
    assert st.census()["on_probation"] == 0


def test_stewardship_enforcement_requires_published_rules():
    st = make_stewardship()
    st.apply("alice", ["knowledge", "be kind"])
    st.warn("alice", "no spam")
    st.silence("alice", "no spam")
    assert st.is_silenced("alice")
    st.unsilence("alice")
    with pytest.raises(sc.StewardshipError):
        st.warn("alice", "a rule that was never published")
    assert st.enforcement_log()  # hash-chained ledger has entries


# -- print_online_loop -------------------------------------------------------


def make_loop():
    loop = pl.Loop("test-loop", harvest_bar=2, max_excerpts=3)
    loop.publish_article(
        "a1", "The First Issue", "body...", "What did you think of the opening?"
    )
    return loop


def test_print_online_loop_article_opens_thread():
    loop = make_loop()
    pid = loop.post("thread:a1", "reader1", "The opening was wonderful.")
    assert loop.endorse("thread:a1", pid, 3) == 3


def test_print_online_loop_harvest_marks_and_does_not_repeat():
    loop = make_loop()
    p1 = loop.post("thread:a1", "reader1", "Great piece.")
    p2 = loop.post("thread:a1", "reader2", "Meh.")
    loop.endorse("thread:a1", p1, 5)
    loop.endorse("thread:a1", p2, 1)
    first = loop.harvest_excerpts()
    assert len(first) == 1
    assert first[0].author == "reader1"
    assert first[0].post_id == p1
    second = loop.harvest_excerpts()
    assert second == []  # harvested posts never print twice


def test_print_online_loop_edition_closes_with_provenance():
    loop = make_loop()
    p1 = loop.post("thread:a1", "reader1", "A line worth printing.")
    loop.endorse("thread:a1", p1, 4)
    edition = loop.assemble_edition(1, [])
    assert edition["edition_no"] == 1
    assert len(edition["from_the_forum"]) == 1
    prov = loop.provenance(1)
    assert prov[0]["author"] == "reader1"
    assert prov[0]["answering_article"] == "a1"
    with pytest.raises(pl.LoopError):
        loop.assemble_edition(1, [])  # edition numbers must increase
