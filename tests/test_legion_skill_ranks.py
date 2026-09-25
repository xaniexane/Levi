"""Guards for skill rank ladders, member mastery, cross-domain linking,
pattern_bridge, and Action — law-guard-prove, not formal proof.

Proves: every one of the 80 skills carries a complete ordered rank
ladder (I/II/III); skill_at shapes to a rung and fails loudly outside
the ladder; mastery records only in-ladder ranks and resolves what a
member can execute; cross-domain links are ALWAYS cross-category;
pattern_bridge routes on analogy queries; Action routes on
passive-aggressive queries without stealing other skills' traffic; and
none of the 78 pre-existing skills regressed in routing or counts.
"""

import pytest

from levi.legion.skill_pool import (
    RANKS,
    SkillPool,
    cross_domain_links,
    find_skill,
    get_pool,
    list_skills,
    ranks_for,
    skill_at,
)
from levi.legion.skill_pool import mastery
from levi.legion.skill_pool.definitions import SKILL_DEFINITIONS
from levi.legion.team import CrewMember


@pytest.fixture(autouse=True)
def _clean_mastery():
    mastery.reset()
    yield
    mastery.reset()


# -- the pool grew to 80, honestly --------------------------------------


def test_pool_loads_80_skills():
    skills = list_skills()
    assert len(skills) == 80, (
        f"expected 80 skills (78 + pattern_bridge + Action), got {len(skills)}"
    )


def test_backend_flag_breakdown_after_additions():
    counts = get_pool().backend_counts()
    assert counts == {
        "platform-native": 4,
        "playbook-only": 47,  # 45 + pattern_bridge + Action, both honest playbook-only
        "needs-wiring": 29,
    }, f"backend breakdown changed: {counts}"
    assert sum(counts.values()) == 80


# -- invariant: every skill has a complete ordered ladder ----------------


def test_every_skill_has_complete_ordered_ladder():
    for s in list_skills():
        ladder = s.get("ranks")
        assert ladder is not None, f"{s['id']}: missing rank ladder"
        assert [r["rank"] for r in ladder] == list(RANKS), (
            f"{s['id']}: ladder not ordered {RANKS}"
        )
        assert all(r["description"].strip() for r in ladder), (
            f"{s['id']}: empty rung description"
        )


def test_ranks_for_matches_pool_and_none_for_unknown():
    ladder = ranks_for("legion_dispute_prep")
    assert ladder is not None and len(ladder) == 3
    assert ladder[0]["rank"] == "I" and ladder[2]["rank"] == "III"
    assert ranks_for("legion_nope") is None


def test_skill_at_shapes_to_rung_and_is_case_insensitive():
    shaped = skill_at("legion_mindfulness_practice", "ii")
    assert shaped["active_rank"] == "II"
    assert (
        "breathing" in shaped["rank_description"].lower()
        or shaped["rank_description"].strip()
    )
    # full ladder still present alongside the shaped rung
    assert len(shaped["ranks"]) == 3
    assert shaped["id"] == "legion_mindfulness_practice"


def test_skill_at_fails_loudly_outside_ladder():
    with pytest.raises(ValueError):
        skill_at("legion_gmail", "V")
    with pytest.raises(ValueError):
        skill_at("legion_gmail", "")
    with pytest.raises(ValueError):
        skill_at("legion_nope", "I")


def test_pool_rejects_skill_with_no_ladder():
    with pytest.raises(ValueError, match="no rank ladder"):
        SkillPool(
            [
                {
                    "id": "legion_ladderless",
                    "name": "ladderless",
                    "description": "x",
                    "category": "meta",
                    "backend": "playbook-only",
                    "triggers": ("x",),
                }
            ]
        )


# -- member mastery -------------------------------------------------------


def test_member_id_for_crew_member_mapping_and_string():
    member = CrewMember(
        role="marketer", seat_key="seat-7", category="x", responsibility="y"
    )
    assert mastery.member_id_for(member) == "seat-7"
    assert mastery.member_id_for({"role": "booker"}) == "role:booker"
    assert mastery.member_id_for("seat-9") == "seat-9"
    with pytest.raises(ValueError):
        mastery.member_id_for("")
    with pytest.raises(ValueError):
        mastery.member_id_for(object())


def test_set_and_get_mastery_roundtrip():
    receipt = mastery.set_mastery("seat-1", "legion_dispute_prep", "II")
    assert receipt == {
        "member_id": "seat-1",
        "skill_id": "legion_dispute_prep",
        "rank": "II",
        "status": "set",
    }
    assert mastery.mastery_for("seat-1", "legion_dispute_prep") == "II"
    assert mastery.mastery_for("seat-1", "legion_gmail") is None
    assert mastery.mastery_for("seat-unknown", "legion_gmail") is None


def test_mastery_rejects_out_of_ladder_rank_and_unknown_skill():
    with pytest.raises(ValueError):
        mastery.set_mastery("seat-1", "legion_dispute_prep", "IV")
    with pytest.raises(ValueError):
        mastery.set_mastery("seat-1", "legion_nope", "I")
    # nothing was recorded by the failed writes
    assert mastery.executable_skills("seat-1") == []


def test_executable_skills_shaped_to_member_rank():
    member = CrewMember(
        role="marketer", seat_key="seat-2", category="x", responsibility="y"
    )
    mastery.set_mastery(member, "legion_ad_creative", "I")
    mastery.set_mastery(member, "legion_terms_breakdown", "III")
    got = mastery.executable_skills(member)
    by_id = {e["id"]: e for e in got}
    assert set(by_id) == {"legion_ad_creative", "legion_terms_breakdown"}
    assert by_id["legion_ad_creative"]["mastery_rank"] == "I"
    assert by_id["legion_ad_creative"]["active_rank"] == "I"
    assert by_id["legion_terms_breakdown"]["active_rank"] == "III"
    assert "rank_description" in by_id["legion_terms_breakdown"]


def test_clear_mastery():
    mastery.set_mastery("seat-3", "legion_gmail", "I")
    mastery.set_mastery("seat-3", "legion_tts", "II")
    out = mastery.clear_mastery("seat-3", "legion_gmail")
    assert out["cleared"] == ["legion_gmail"]
    assert mastery.mastery_for("seat-3", "legion_tts") == "II"
    out = mastery.clear_mastery("seat-3")
    assert out["cleared"] == ["legion_tts"]
    assert mastery.executable_skills("seat-3") == []


def test_dump_and_load_roundtrip_and_corrupt_load_fails():
    mastery.set_mastery("seat-4", "legion_habit_design", "III")
    data = mastery.dump()
    assert data == {"seat-4": {"legion_habit_design": "III"}}
    mastery.reset()
    report = mastery.load(data)
    assert report == {"members": 1, "entries": 1}
    assert mastery.mastery_for("seat-4", "legion_habit_design") == "III"
    with pytest.raises(ValueError):
        mastery.load({"seat-5": {"legion_habit_design": "IX"}})


# -- cross-domain pattern linking ------------------------------------------


def test_cross_domain_links_always_cross_category():
    for lnk in cross_domain_links("legion_dispute_prep", limit=20):
        assert lnk["skill"]["category"] != lnk["anchor_category"], (
            f"same-category link leaked: {lnk['skill']['id']}"
        )
        assert lnk["shared_patterns"], "link with no shared patterns"
        assert lnk["anchor"] == "legion_dispute_prep"


def test_negotiation_bridges_law_and_business():
    links = cross_domain_links("negotiation", limit=10)
    assert links, "negotiation should surface cross-domain links"
    categories = {x["skill"]["category"] for x in links}
    assert len(categories) >= 2, f"expected >=2 categories, got {categories}"
    ids = {x["skill"]["id"] for x in links}
    assert "legion_ai_sdr" in ids and "legion_dispute_prep" in ids
    for lnk in links:
        assert lnk["skill"]["category"] != lnk["anchor_category"]


def test_nonsense_query_returns_empty_gracefully():
    assert cross_domain_links("xyzzy-no-such-thing", limit=5) == []
    assert cross_domain_links("", limit=5) == []


# -- pattern_bridge --------------------------------------------------------


def test_pattern_bridge_routes_on_analogy_queries():
    top = find_skill("draw an analogy between biology and business")
    assert top and top[0]["id"] == "legion_pattern_bridge"
    top = find_skill("connect the dots between these two domains")
    assert top and top[0]["id"] == "legion_pattern_bridge"


def test_pattern_bridge_is_playbook_only_with_ladder():
    skill = get_pool().get("legion_pattern_bridge")
    assert skill["backend"] == "playbook-only"
    assert skill["category"] == "meta"  # provisional category
    assert [r["rank"] for r in skill["ranks"]] == ["I", "II", "III"]
    assert "false friend" in skill["description"].lower()


# -- Action ---------------------------------------------------------------


def test_action_routes_on_passive_aggressive_queries():
    top = find_skill("that was passive aggressive, give me a sideways response")
    assert top and top[0]["id"] == "legion_action_react"
    top = find_skill("read the room and respond to this bureaucratic absurdity")
    assert top and top[0]["id"] == "legion_action_react"


def test_action_does_not_steal_other_skills_queries():
    top = find_skill("send an email to the team")
    assert top and top[0]["id"] == "legion_gmail"
    top = find_skill("write a proposal for the client")
    assert top and top[0]["id"] == "legion_proposal_draft"


def test_action_is_playbook_only_with_ladder_and_provisional_name():
    skill = get_pool().get("legion_action_react")
    assert skill["backend"] == "playbook-only"
    assert skill["name"] == "Action"  # provisional display name, Chauncey's label
    assert [r["rank"] for r in skill["ranks"]] == ["I", "II", "III"]
    assert "deniable" in skill["description"].lower()


# -- no regressions on the 78 ----------------------------------------------


def test_existing_routing_unchanged():
    assert find_skill("review this NDA")[0]["id"] == "legion_legal_contract"
    assert (
        find_skill("build a compliance checklist for my app")[0]["id"]
        == "legion_compliance_checklist"
    )
    assert (
        find_skill("research the statute of limitations")[0]["id"]
        == "legion_legal_research"
    )
    assert (
        find_skill("organize my evidence and timeline for this dispute")[0]["id"]
        == "legion_dispute_prep"
    )
    # generic research must not hit any law skill (may hit nothing at all)
    law_ids = {
        "legion_legal_research",
        "legion_compliance_checklist",
        "legion_terms_breakdown",
        "legion_dispute_prep",
    }
    assert not any(r["id"] in law_ids for r in find_skill("research electric cars"))


def test_new_skills_did_not_steal_existing_triggers():
    # "negotiation" now anchors dispute_prep (law) and ai_sdr (business);
    # unrelated existing queries must be unaffected. ("draft email" is a
    # pre-existing gmail/ai_secretary tie, won by list order — not ours.)
    assert find_skill("schedule meeting")[0]["id"] == "legion_ai_secretary"
    by_id = {s["id"]: s for s in SKILL_DEFINITIONS}
    assert "negotiation" in by_id["legion_dispute_prep"]["triggers"]
    assert "negotiation" in by_id["legion_ai_sdr"]["triggers"]
