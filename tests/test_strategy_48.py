"""Tests for the 48-law forward/reverse strategy engine + life formula."""

import pytest

from levi.strategy import (
    ENGINE,
    FormulaResult,
    Law,
    Projection,
    Reflection,
    apply,
    consult,
    domains,
    get_law,
    laws,
    project,
    return_to_sender,
)


def test_all_48_load():
    all_laws = laws()
    assert len(all_laws) == 48
    assert [law.id for law in all_laws] == list(range(1, 49))


def test_ids_unique_and_names_unique():
    all_laws = laws()
    assert len({law.id for law in all_laws}) == 48
    assert len({law.name for law in all_laws}) == 48


def test_every_law_has_forward_reverse_constraints():
    for law in laws():
        assert isinstance(law, Law)
        assert law.name.strip(), f"law {law.id} has empty name"
        assert law.doctrine.strip(), f"law {law.id} has empty doctrine"
        assert law.forward.strip(), f"law {law.id} missing forward"
        assert law.reverse.strip(), f"law {law.id} missing reverse"
        assert law.forward != law.reverse, f"law {law.id} forward==reverse"
        assert len(law.constraints) >= 1, f"law {law.id} missing constraints"
        assert len(law.signals) >= 1, f"law {law.id} missing signals"


def test_no_empty_entries_anywhere():
    for law in laws():
        for field in (law.name, law.doctrine, law.forward, law.reverse):
            assert field and field.strip()
        for c in law.constraints:
            assert c.strip()
        for s in law.signals:
            assert s.strip()


def test_forward_reverse_are_one_object():
    law = get_law(28)
    assert law.forward and law.reverse
    assert law.id == 28 and law.name == "Allies, Not Pawns"


def test_consult_returns_ranked_readings():
    readings = consult("I need to focus on one goal and quit distractions", top=5)
    assert len(readings) >= 1
    scores = [r.score for r in readings]
    assert scores == sorted(scores, reverse=True)
    for r in readings:
        assert r.stance in ("forward", "reverse", "both")
        assert r.guidance().strip()


def test_consult_respects_top():
    readings = consult("trust reputation build work focus", top=3)
    assert 1 <= len(readings) <= 3


def test_consult_empty_situation():
    assert consult("", top=5) == []
    assert consult("   ", top=5) == []


def test_project_returns_535_projection():
    proj = project("saving money for a house while paying debt")
    assert isinstance(proj, Projection)
    assert len(proj.steps5) == 5
    assert len(proj.locked3) == 3
    assert len(proj.next5) == 5
    assert [s.n for s in proj.steps5] == [1, 2, 3, 4, 5]
    assert [s.n for s in proj.next5] == [6, 7, 8, 9, 10]
    assert proj.efficient_pick.strip()
    for s in proj.steps5:
        assert s.cost_tier in ("low", "medium", "high")
        assert s.price.strip() and s.outcome.strip()


def test_project_is_deterministic():
    a = project("should I change careers at 40")
    b = project("should I change careers at 40")
    assert [(s.law_id, s.stance, s.cost_tier, s.move) for s in a.steps5] == \
           [(s.law_id, s.stance, s.cost_tier, s.move) for s in b.steps5]
    assert a.efficient_pick == b.efficient_pick


def test_project_depth_bounds():
    assert len(project("x y z focus goal", depth=3).steps5) == 3
    assert len(project("x y z focus goal", depth=99).steps5) == 7


def test_return_to_sender_is_clean():
    r = return_to_sender("my manager insulted me in front of the team")
    assert isinstance(r, Reflection)
    assert r.reflected.strip() and r.your_move.strip()
    assert len(r.not_this) == 3
    blob = " ".join([r.reflected, r.your_move, *r.not_this]).lower()
    assert "no escalation" in blob
    assert "no manipulation" in blob
    assert "no absorption" in blob
    # never advises retaliation
    assert "retaliat" not in blob and "revenge" not in blob


def test_detect_attack():
    assert ENGINE.detect_attack("he keeps trying to undermine my work")
    assert ENGINE.detect_attack("she provoked me in the meeting")
    assert not ENGINE.detect_attack("I want to save money for a trip")


def test_apply_runs_whole_formula():
    res = apply("my coworker sabotaged my presentation to make me look bad")
    assert isinstance(res, FormulaResult)
    assert res.reflection is not None
    assert isinstance(res.projection, Projection)
    assert res.readings


def test_apply_no_attack_no_reflection():
    res = apply("I want to build a morning exercise habit")
    assert res.reflection is None
    assert isinstance(res.projection, Projection)


def test_domains_span_life_areas():
    all_domains = set(domains())
    for expected in ("health", "relationships", "money", "work", "goals", "daily"):
        assert expected in all_domains, f"missing life area: {expected}"
    for law in laws():
        assert len(law.domains) >= 3, f"law {law.id} lacks domain examples"


def test_consult_domain_boost():
    plain = consult("saving money for the future", top=3)
    boosted = consult("saving money for the future", top=3, domain="money")
    assert boosted
    assert boosted[0].law.id in {3, 13, 21, 24, 40, 42}  # money-domain laws
    assert any("domain:money" in s for s in boosted[0].matched_signals)
    _ = plain  # both run clean



def test_reading_guidance_matches_stance():
    readings = consult("reputation trust credibility", top=5)
    assert readings
    for r in readings:
        g = r.guidance()
        if r.stance == "forward":
            assert g == r.law.forward
        elif r.stance == "reverse":
            assert g == r.law.reverse
        else:
            assert "FORWARD" in g and "REVERSE" in g


def test_relevant_laws_surface():
    readings = consult("should I quit my failing project and focus on one goal", top=3)
    ids = [r.law.id for r in readings]
    assert 5 in ids or 8 in ids or 27 in ids  # clean cut / true north / decisive no


def test_engine_get_invalid():
    with pytest.raises(KeyError):
        ENGINE.get(49)
