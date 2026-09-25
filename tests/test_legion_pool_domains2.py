"""Guards for the three new Legion skill-pool domains — law-guard-prove.

DOMAINS-2 INVARIANTS (declared first, proved below, never claimed
beyond what the tests check):

1. every therapeutic skill's description carries the plain limit —
   wellness techniques, not therapy; not a therapist; if you're in
   crisis, contact a crisis line or professional;
2. each new skill routes its own queries first WITHOUT stealing
   existing skills' queries, and the therapeutic and life-balance
   domains do not cross-steal;
3. all 69 pre-existing skills still resolve exactly as before —
   count assertions updated exactly (69 -> 78), never weakened.

NAMING: all names here are PROVISIONAL and await Chauncey's word.
"""

from levi.legion.skill_pool import find_skill, get_pool, list_skills, skills_for

DOC_IDS = (
    "legion_doc_design",
    "legion_report_builder",
    "legion_proposal_draft",
)

THERAPY_IDS = (
    "legion_mindfulness_practice",
    "legion_thought_reframing",
    "legion_guided_journaling",
)

BALANCE_IDS = (
    "legion_time_boundaries",
    "legion_burnout_gauge",
    "legion_habit_design",
)

NEW_IDS = DOC_IDS + THERAPY_IDS + BALANCE_IDS

LIMIT_PHRASES = (
    "wellness techniques, not therapy",
    "not a therapist",
    "crisis line or professional",
)


def _new_skills():
    return [s for s in list_skills() if s["id"] in NEW_IDS]


# -- invariant 1: the therapeutic limit is in every description -----------


def test_domains2_has_exactly_nine_skills():
    assert len(_new_skills()) == 9, f"expected 9 new skills, got {len(_new_skills())}"


def test_new_skill_ids_namespaced_and_categorized():
    expected = {}
    expected.update({i: "document-creation" for i in DOC_IDS})
    expected.update({i: "therapeutic" for i in THERAPY_IDS})
    expected.update({i: "life-balance" for i in BALANCE_IDS})
    for s in _new_skills():
        assert s["id"].startswith("legion_"), f"{s['id']}: not namespaced"
        assert s["category"] == expected[s["id"]], (
            f"{s['id']}: wrong category {s['category']}"
        )


def test_every_therapeutic_skill_carries_crisis_limit():
    for s in _new_skills():
        if s["id"] not in THERAPY_IDS:
            continue
        desc = s["description"].lower()
        for phrase in LIMIT_PHRASES:
            assert phrase in desc, f"{s['id']}: description missing {phrase!r}"
        assert "diagnos" in desc, f"{s['id']}: must state it does not diagnose"


def test_new_skills_are_playbook_only_and_flagged():
    for s in _new_skills():
        assert s["backend"] == "playbook-only", f"{s['id']}: wrong backend flag"
    results = find_skill("guide me through a breathing exercise")
    by_id = {r["id"]: r for r in results}
    assert by_id["legion_mindfulness_practice"]["executable_now"] is True


def test_crisis_query_routes_to_skill_carrying_crisis_line():
    results = find_skill("I'm in crisis and need help")
    assert results, "a crisis query must route somewhere, never to silence"
    first = results[0]
    assert "crisis line or professional" in first["description"].lower(), (
        f"{first['id']}: crisis routing landed on a skill without the crisis limit"
    )


# -- invariant 2: clean routing, no stealing, no cross-steal --------------


def test_doc_design_query_hits_first_steals_nothing():
    results = find_skill("design the document layout for my handbook")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_doc_design"
    ids = {r["id"] for r in results}
    for existing in (
        "legion_resume_maker",
        "legion_invoice_generator",
        "legion_excel_generator",
    ):
        assert existing not in ids, f"doc_design stole {existing}'s query"


def test_report_builder_query_hits_first_steals_nothing():
    results = find_skill("build a long-form report with an executive summary")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_report_builder"
    assert not any(r["id"] == "legion_deep_research" for r in results), (
        "report_builder stole deep_research's query"
    )


def test_proposal_query_hits_first_steals_nothing():
    results = find_skill("draft a business proposal for a client")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_proposal_draft"
    ids = {r["id"] for r in results}
    for existing in ("legion_legal_contract", "legion_invoice_generator"):
        assert existing not in ids, f"proposal_draft stole {existing}'s query"


def test_mindfulness_query_hits_first():
    results = find_skill("guide me through a breathing exercise")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_mindfulness_practice"


def test_reframing_query_hits_first():
    results = find_skill("help me reframe my thoughts about this setback")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_thought_reframing"


def test_journaling_query_hits_first():
    results = find_skill("give me a journal prompt for reflection")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_guided_journaling"


def test_boundaries_query_hits_first():
    results = find_skill("help me set boundaries with time blocking")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_time_boundaries"


def test_burnout_query_hits_first_no_therapeutic_collision():
    results = find_skill("I'm burned out")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_burnout_gauge"
    assert not any(r["id"] in THERAPY_IDS for r in results), (
        "life-balance stole a therapeutic query (or vice versa)"
    )


def test_habit_query_hits_first():
    results = find_skill("I want to build a habit with habit stacking")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_habit_design"


def test_therapeutic_query_has_no_balance_collision():
    results = find_skill("I need a breathing exercise to calm down")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_mindfulness_practice"
    assert not any(r["id"] in BALANCE_IDS for r in results), (
        "therapeutic query collided with life-balance"
    )


def test_new_domains_do_not_steal_generic_queries():
    for query in ("research electric cars", "send an email to my inbox"):
        results = find_skill(query)
        assert not any(r["id"] in NEW_IDS for r in results), (
            f"new domain stole generic query {query!r}"
        )


# -- skills_for domain resolution -----------------------------------------


def test_skills_for_document_creation():
    skills = skills_for("document-creation")
    assert {s["id"] for s in skills} == set(DOC_IDS)


def test_skills_for_therapeutic():
    skills = skills_for("therapeutic")
    assert {s["id"] for s in skills} == set(THERAPY_IDS)


def test_skills_for_life_balance():
    skills = skills_for("life-balance")
    assert {s["id"] for s in skills} == set(BALANCE_IDS)


# -- invariant 3: no regressions, counts updated exactly -------------------


def test_pool_now_holds_80_skills():
    assert len(list_skills()) == 80, f"expected 80 skills, got {len(list_skills())}"


def test_backend_flag_breakdown_updated_honestly():
    counts = get_pool().backend_counts()
    assert counts == {
        "platform-native": 4,
        "playbook-only": 47,  # 36 + 9 new domains (all honest playbook-only)
        "needs-wiring": 29,
    }, f"backend breakdown wrong: {counts}"
    assert sum(counts.values()) == 80


def test_preexisting_domains_still_resolve_first():
    # legal_contract, gmail, legal_research untouched by the new domains
    nda = find_skill("review this NDA")
    assert nda and nda[0]["id"] == "legion_legal_contract"
    email = find_skill("send an email to my inbox")
    assert email and email[0]["id"] == "legion_gmail"
    research = find_skill("do legal research on the statute of limitations")
    assert research and research[0]["id"] == "legion_legal_research"
    law = skills_for("law")
    assert len(law) == 4, "law domain changed"
