"""Guards for the Legion law domain — law-guard-prove, not formal proof.

LAW-DOMAIN INVARIANTS (declared first, proved below, never claimed
beyond what the tests check):

1. every law skill's description carries the plain-language limit —
   know-how, not a lawyer; not legal advice; no filing; no representation;
2. trigger keywords route law queries to law skills WITHOUT stealing
   legal_contract's queries (an NDA review still resolves to
   legal_contract first) and without stealing generic non-legal queries;
3. all 65 pre-existing skills still resolve exactly as before —
   no regressions from adding the law domain.

NAMING: all names here are PROVISIONAL and await Chauncey's word.
"""

from levi.legion.skill_pool import find_skill, get_pool, list_skills, skills_for

LAW_IDS = (
    "legion_legal_research",
    "legion_compliance_checklist",
    "legion_terms_breakdown",
    "legion_dispute_prep",
)

LIMIT_PHRASES = (
    "not a lawyer",
    "not legal advice",
    "no filing",
    "no representation",
)


def _law_skills():
    return [s for s in list_skills() if s["id"] in LAW_IDS]


# -- invariant 1: the honest limit is in every description ----------------


def test_law_domain_has_exactly_four_skills():
    assert len(_law_skills()) == 4, f"expected 4 law skills, got {len(_law_skills())}"


def test_every_law_skill_carries_not_a_lawyer_limit():
    for s in _law_skills():
        desc = s["description"].lower()
        for phrase in LIMIT_PHRASES:
            assert phrase in desc, f"{s['id']}: description missing {phrase!r}"


def test_law_skill_ids_namespaced_and_categorized():
    for s in _law_skills():
        assert s["id"].startswith("legion_"), f"{s['id']}: not namespaced"
        assert s["category"] == "law", f"{s['id']}: wrong category"


def test_law_skills_are_playbook_only_and_flagged():
    for s in _law_skills():
        assert s["backend"] == "playbook-only", f"{s['id']}: wrong backend flag"
    results = find_skill("do legal research on the statute of limitations")
    by_id = {r["id"]: r for r in results}
    assert by_id["legion_legal_research"]["executable_now"] is True


def test_skills_for_law_domain():
    skills = skills_for("law")
    assert {s["id"] for s in skills} == set(LAW_IDS)


# -- invariant 2: triggers route correctly, steal nothing ------------------


def test_nda_query_still_hits_legal_contract_first():
    results = find_skill("review this NDA")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_legal_contract"
    assert not any(r["id"] in LAW_IDS for r in results), (
        "law skill stole a legal_contract query"
    )


def test_legal_research_query_hits_legal_research_first():
    results = find_skill("do legal research on the statute of limitations")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_legal_research"


def test_compliance_query_hits_compliance_checklist_first():
    results = find_skill("build a compliance checklist for my app")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_compliance_checklist"


def test_terms_teardown_query_hits_terms_breakdown_first():
    results = find_skill("break down these terms of service and flag the hostile terms")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_terms_breakdown"
    # legal_contract still surfaces for the generic ToS mention — not erased
    assert any(r["id"] == "legion_legal_contract" for r in results)


def test_dispute_prep_query_hits_dispute_prep_first():
    results = find_skill("organize my evidence and timeline for this dispute")
    assert results, "expected matches"
    assert results[0]["id"] == "legion_dispute_prep"


def test_law_triggers_do_not_steal_generic_research():
    results = find_skill("research electric cars")
    assert not any(r["id"] in LAW_IDS for r in results), (
        "law skill stole a generic research query"
    )


# -- invariant 3: no regressions ------------------------------------------


def test_pool_now_holds_80_skills():
    assert len(list_skills()) == 80, f"expected 80 skills, got {len(list_skills())}"


def test_backend_flag_breakdown_updated_honestly():
    counts = get_pool().backend_counts()
    assert counts == {
        "platform-native": 4,
        "playbook-only": 47,
        "needs-wiring": 29,
    }, f"backend breakdown wrong: {counts}"
    assert sum(counts.values()) == 80


def test_preexisting_business_domain_unchanged():
    business = skills_for("business")
    assert len(business) == 18  # legal_contract still lives here, untouched
    assert any(s["id"] == "legion_legal_contract" for s in business)
