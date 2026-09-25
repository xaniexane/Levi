"""Proof for the nanobit organ — behavioral verification of the five
declared invariants, not a formal proof.

Covers: provisional organ registration, deterministic face selection,
the companion default, delivery receipt + is_consumable gating, ceiling
inheritance and refusal, both interrogation directions, and mogwai
composting (exactly-once, shared learnings).
"""

import pytest

from levi.revival.omega import nanobit as nb
from levi.revival.omega import substrate as sub


@pytest.fixture()
def pool() -> sub.SharedSubstrate:
    return sub.SharedSubstrate()


# -- invariant 1: never anonymous -------------------------------------------


def test_organ_registered_and_origin_tagged(pool: sub.SharedSubstrate) -> None:
    assert "nanobit" in sub.ORGANS
    assert sub.ORGAN_RISK["nanobit"] == sub.RISK_LOW
    rid = nb.deliver(pool, "hello", {})
    receipt = pool.get_receipt(rid)
    assert receipt is not None and receipt.organ == "nanobit"
    assert receipt.risk == sub.RISK_LOW


def test_registration_idempotent() -> None:
    before_risk = dict(sub.ORGAN_RISK)
    before_organs = set(sub.ORGANS)
    nb._register_organ()
    assert dict(sub.ORGAN_RISK) == before_risk
    assert set(sub.ORGANS) == before_organs


# -- invariant 3: never fakes a face -----------------------------------------


def test_face_selection_deterministic() -> None:
    a = nb.read_the_room("please debug this python script, there's a bug")
    b = nb.read_the_room("please debug this python script, there's a bug")
    assert a == b
    assert a["face"] == "code-gremlin"
    assert a["deterministic"] is True


def test_story_and_strategy_faces() -> None:
    assert (
        nb.read_the_room("help me write this chapter, the plot drags")["face"]
        == "story-gremlin"
    )
    assert (
        nb.read_the_room("pricing decision for the launch roadmap")["face"]
        == "strategist"
    )


def test_unknown_room_gets_honest_companion() -> None:
    face = nb.read_the_room("xylophone quantum banana")
    assert face["face"] == "companion"
    assert "Tell me what this room needs" in face["scope"]
    # the companion declares its scope honestly — no invented capability
    assert face["name"] == "the companion"


def test_faces_come_from_the_identity_card_only() -> None:
    ids = {f["id"] for f in nb.FACES}
    assert ids == {"code-gremlin", "story-gremlin", "strategist", "companion"}


# -- invariant 5: never consumes a quarantined receipt ------------------------


def test_deliver_refuses_quarantined_chain_receipt(pool: sub.SharedSubstrate) -> None:
    build = pool.record_receipt(
        "alpha", "build", {"ok": True}, risk="elevated", approved_by="test"
    )
    pool.challenge("echo", build.id, "looks wrong")
    with pytest.raises(nb.NanobitRefusal):
        nb.deliver(pool, "build me a thing", {"build": build.id})
    # the refusal was LOUD: a delivery receipt records the halt
    halts = [
        r
        for r in pool.receipts(organ="nanobit", kind="delivery")
        if not r.payload.get("ok", True)
    ]
    assert len(halts) == 1
    assert halts[0].payload["stage"] == "build"


def test_deliver_refuses_missing_chain_receipt(pool: sub.SharedSubstrate) -> None:
    with pytest.raises(nb.NanobitRefusal):
        nb.deliver(pool, "build me a thing", {"build": "rcpt_nope"})


def test_deliver_happy_path_records_face(pool: sub.SharedSubstrate) -> None:
    build = pool.record_receipt(
        "alpha", "build", {"ok": True}, risk="elevated", approved_by="test"
    )
    rid = nb.deliver(pool, "fix this bug in my script", {"build": build.id})
    receipt = pool.get_receipt(rid)
    assert receipt is not None
    assert receipt.payload["ok"] is True
    assert receipt.payload["face"] == "code-gremlin"
    assert pool.is_consumable(rid)


# -- invariant 2: strictest ceiling wins --------------------------------------


def test_ceiling_inheritance_low_organ_high_action() -> None:
    assert sub.ceiling_for("nanobit", "alpha") == sub.RISK_ELEVATED
    assert sub.ceiling_for("nanobit") == sub.RISK_LOW


def test_above_ceiling_action_refuses() -> None:
    with pytest.raises(nb.NanobitRefusal):
        nb._check_ceiling(sub.RISK_ELEVATED)


def test_elevated_receipt_requires_approval() -> None:
    pool = sub.SharedSubstrate()
    with pytest.raises(ValueError):
        pool.record_receipt(
            "nanobit", "delivery", {"ok": True}, risk="elevated"
        )  # no approved_by
    r = pool.record_receipt(
        "nanobit",
        "delivery",
        {"ok": True},
        risk="elevated",
        approved_by="test-escalation",
    )
    assert r.approved_by == "test-escalation"


# -- interrogation: nanobit challenges others ----------------------------------


def test_nanobit_can_challenge_another_organ(pool: sub.SharedSubstrate) -> None:
    route = pool.record_receipt(
        "nexus", "route", {"ok": True}, risk="standard", approved_by="test"
    )
    ch = nb.challenge_output(pool, route.id, "route smells like a guess")
    assert ch.challenger == "nanobit"
    assert ch.target_organ == "nexus"
    assert not pool.is_consumable(route.id)


def test_challenge_needs_grounds(pool: sub.SharedSubstrate) -> None:
    route = pool.record_receipt(
        "nexus", "route", {"ok": True}, risk="standard", approved_by="test"
    )
    with pytest.raises(ValueError):
        nb.challenge_output(pool, route.id, "   ")


# -- interrogation: others challenge nanobit, mogwai composts -----------------


def test_nanobit_output_challengeable(pool: sub.SharedSubstrate) -> None:
    rid = nb.deliver(pool, "hello", {})
    ch = pool.challenge("echo", rid, "face was wrong for the room")
    assert not pool.is_consumable(rid)
    pool.resolve_challenge(ch.id, "dismissed", "face was fine")
    assert pool.is_consumable(rid)


def test_compost_turns_resolved_challenges_into_shared_learnings(
    pool: sub.SharedSubstrate,
) -> None:
    rid = nb.deliver(pool, "hello", {})
    ch1 = pool.challenge("echo", rid, "too small to trust")
    pool.resolve_challenge(ch1.id, "dismissed", "smallness was the point")
    rid2 = nb.deliver(pool, "hello again", {})
    ch2 = pool.challenge("alpha", rid2, "delivery skipped a check")
    pool.resolve_challenge(ch2.id, "upheld", "check was skipped")

    learned = nb.compost_challenges(pool)
    assert len(learned) == 2
    lessons = [e.lesson for e in pool.learnings(organ="nanobit")]
    assert len(lessons) == 2
    assert any("dismissed" in lesson for lesson in lessons)
    assert any("upheld" in lesson for lesson in lessons)
    # one memory across all faces: learnings live in the SHARED pool
    assert all(pool.learnings())


def test_compost_is_exactly_once(pool: sub.SharedSubstrate) -> None:
    rid = nb.deliver(pool, "hello", {})
    ch = pool.challenge("echo", rid, "grounds")
    pool.resolve_challenge(ch.id, "dismissed")
    assert len(nb.compost_challenges(pool)) == 1
    assert nb.compost_challenges(pool) == []
    assert len(pool.learnings(organ="nanobit")) == 1


def test_compost_ignores_other_organs_challenges(pool: sub.SharedSubstrate) -> None:
    build = pool.record_receipt(
        "alpha", "build", {"ok": True}, risk="elevated", approved_by="test"
    )
    ch = pool.challenge("echo", build.id, "grounds")
    pool.resolve_challenge(ch.id, "dismissed")
    assert nb.compost_challenges(pool) == []
    assert pool.learnings(organ="nanobit") == []


# -- loop-patch contract -------------------------------------------------------


def test_deliver_signature_matches_loop_patch_contract(
    pool: sub.SharedSubstrate,
) -> None:
    # the documented loop.py patch calls:
    #   nb.deliver(substrate, prompt, chain, approved_by)
    import inspect

    sig = inspect.signature(nb.deliver)
    params = list(sig.parameters)
    assert params == ["substrate", "prompt", "chain", "approved_by"]
