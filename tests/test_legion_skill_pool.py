"""Guards for the shared Legion skill pool — law-guard-prove, not formal proof.

Proves: 65 skills load with valid definitions; the pool is a singleton
shared by every caller; discovery always surfaces the backend flag and
never presents needs-wiring skills as executable; Nanobit resolves through
the same pool object (import, not a copy); Nanobit's existing behavior is
unchanged by the wiring.
"""

import pytest

from levi.legion.skill_pool import (
    BACKENDS,
    INVARIANTS,
    SkillPool,
    find_skill,
    get_pool,
    list_skills,
    skills_for,
)
from levi.legion.skill_pool.definitions import SKILL_DEFINITIONS
from levi.revival.omega import nanobit as nb


# -- invariant 1: every skill well-formed --------------------------------


def test_pool_loads_80_skills():
    skills = list_skills()
    assert len(skills) == 80, (
        f"expected 80 skills (78 + pattern_bridge + Action), got {len(skills)}"
    )


def test_skill_ids_unique_and_namespaced():
    ids = [s["id"] for s in list_skills()]
    assert len(set(ids)) == len(ids), "duplicate skill ids"
    assert all(i.startswith("legion_") for i in ids), "ids must be legion_ namespaced"


def test_every_skill_has_name_description_trigger():
    for s in list_skills():
        assert s["name"].strip(), f"{s['id']}: empty name"
        assert s["description"].strip(), f"{s['id']}: empty description"
        assert s["triggers"], f"{s['id']}: no triggers"
        assert s["backend"] in BACKENDS, f"{s['id']}: illegal backend"


def test_invalid_definition_rejected_loudly():
    with pytest.raises(ValueError):
        SkillPool(
            [
                {
                    "id": "legion_bad",
                    "name": "",
                    "description": "x",
                    "category": "meta",
                    "backend": "playbook-only",
                    "triggers": ("x",),
                }
            ]
        )
    with pytest.raises(ValueError):
        SkillPool(
            [
                {
                    "id": "legion_bad2",
                    "name": "n",
                    "description": "x",
                    "category": "meta",
                    "backend": "fictional",
                    "triggers": ("x",),
                }
            ]
        )
    with pytest.raises(ValueError):
        SkillPool([dict(SKILL_DEFINITIONS[0]), dict(SKILL_DEFINITIONS[0])])


def test_backend_flag_breakdown_is_honest():
    counts = get_pool().backend_counts()
    assert (
        counts
        == {
            "platform-native": 4,
            "playbook-only": 47,  # 32 + 4 law domain + 9 new domains (all honest playbook-only)
            "needs-wiring": 29,
        }
    ), f"backend breakdown changed: {counts}"
    assert sum(counts.values()) == 80


# -- invariant 2: singleton-shared ----------------------------------------


def test_pool_is_singleton():
    assert get_pool() is get_pool()


def test_list_skills_returns_copies_not_internals():
    skills = list_skills()
    skills.append({"id": "legion_fake"})
    assert get_pool().get("legion_fake") is None


# -- invariant 3: backend flag always surfaced -----------------------------


def test_find_skill_surfaces_backend_flag():
    results = find_skill("send an email to my inbox")
    by_id = {r["id"]: r for r in results}
    assert "legion_gmail" in by_id
    gmail = by_id["legion_gmail"]
    assert gmail["backend"] == "needs-wiring"
    assert gmail["executable_now"] is False


def test_find_skill_never_hides_flag():
    results = find_skill("plan my trip itinerary and check flight status")
    assert results, "expected matches"
    for r in results:
        assert "backend" in r, f"{r['id']}: backend flag missing"
        assert r["backend"] in BACKENDS
        assert r["executable_now"] == (r["backend"] != "needs-wiring")


def test_find_skill_can_exclude_needs_wiring():
    results = find_skill("write me a story", include_needs_wiring=False)
    assert all(r["backend"] != "needs-wiring" for r in results)


def test_find_skill_unknown_task_returns_empty():
    assert find_skill("zzzzqqq nothing matches this") == []
    assert find_skill("") == []


def test_skills_for_domain_category_match():
    business = skills_for("business")
    assert business, "expected business skills"
    assert all(s["category"] == "business" for s in business)
    assert len(business) == 18  # 16 transcript + branding_generator + excel_generator


def test_skills_for_unknown_domain_falls_back_to_search():
    results = skills_for("email")
    assert any(r["id"] == "legion_gmail" for r in results)


# -- invariant 4: nanobit resolves through the same pool -------------------


def test_nanobit_resolves_same_pool_object():
    assert nb.skill_pool() is get_pool()


def test_nanobit_find_skill_matches_pool():
    via_nb = nb.find_skill("draft a contract")
    via_pool = find_skill("draft a contract")
    assert [r["id"] for r in via_nb] == [r["id"] for r in via_pool]
    assert any(r["id"] == "legion_legal_contract" for r in via_nb)


def test_nanobit_existing_behavior_unchanged():
    # face selection untouched by the wiring
    face = nb.read_the_room("please debug this python script, there's a bug")
    assert face["face"] == "code-gremlin"
    assert face["deterministic"] is True
    # ceiling guard untouched
    with pytest.raises(nb.NanobitRefusal):
        nb._check_ceiling("critical")


def test_invariants_declared():
    assert len(INVARIANTS) == 7
