"""Tests for the roster creation matrix (core/levi/packaging/roster_matrix.py)."""

import pytest

from levi.packaging.roster_matrix import (
    DEFAULT_MODEL,
    EDITIONS,
    MODEL_TYPES,
    RosterError,
    advise_upgrades,
    is_selectable,
    model_type,
    model_types,
    resolve_roster,
    roster_receipt,
    slots_for,
)

EXPECTED_IDS = {
    "own-cloud",
    "groq",
    "gemini",
    "openai",
    "xai",
    "local-brain",
    "rules",
}


def test_model_type_ids_exact():
    assert set(MODEL_TYPES) == EXPECTED_IDS


def test_every_model_type_has_description_and_status():
    for mt in model_types():
        assert mt.description and mt.description.strip()
        assert mt.status in ("planned", "auth-gated", "real-weak", "real")
        assert mt.detail and mt.detail.strip()


def test_honest_statuses():
    assert model_type("own-cloud").status == "planned"
    for t in ("groq", "gemini", "openai", "xai"):
        assert model_type(t).status == "auth-gated"
    assert model_type("local-brain").status == "real-weak"
    assert model_type("rules").status == "real"


def test_planned_is_not_selectable():
    assert not is_selectable("own-cloud")
    assert is_selectable("rules")
    assert is_selectable("groq")


def test_unknown_model_type_raises():
    with pytest.raises(RosterError):
        model_type("skynet")


def test_slot_kinds():
    crew = slots_for("crew")
    edition = slots_for("edition")
    assert any(s.slot_id == "face" for s in crew)
    assert any(s.slot_id == "face" for s in edition)
    with pytest.raises(RosterError):
        slots_for("army")


def test_default_roster_resolves_all_rules():
    assignments = resolve_roster("crew")
    assert assignments, "empty crew roster"
    for a in assignments:
        assert a.model_id == DEFAULT_MODEL == "rules"
        assert a.model_status == "real"


def test_every_slot_resolves_to_valid_model_type():
    for kind in ("crew", "edition"):
        for a in resolve_roster(kind):
            assert a.model_id in EXPECTED_IDS


def test_planned_model_refused():
    with pytest.raises(RosterError):
        resolve_roster("crew", model_overrides={"face": "own-cloud"})


def test_auth_gated_without_authorization_refused():
    with pytest.raises(RosterError):
        resolve_roster("crew", model_overrides={"face": "groq"})


def test_auth_gated_with_authorization_allowed():
    assignments = resolve_roster(
        "crew",
        slot_ids=["face"],
        model_overrides={"face": "groq"},
        authorized_teachers=["groq"],
    )
    assert assignments[0].model_id == "groq"
    assert assignments[0].authorized is True


def test_unknown_slot_raises():
    with pytest.raises(RosterError):
        resolve_roster("crew", slot_ids=["janitor"])


def test_unknown_override_model_raises():
    with pytest.raises(RosterError):
        resolve_roster("crew", model_overrides={"face": "hal9000"})


def test_editions_listed():
    assert set(EDITIONS) == {
        "government",
        "schools",
        "universities",
        "corporate",
        "tiny-business",
    }


def test_genesis_basic_is_zero_cost():
    """Basic genesis: every slot on rules — no keys, no spend, no teachers."""
    assignments = resolve_roster("edition")
    assert all(a.model_id == "rules" for a in assignments)
    receipt = roster_receipt("edition", assignments)
    assert receipt["model_mix"] == {"rules": len(assignments)}
    assert receipt["all_real_or_authorized"] is True


def test_receipt_is_deterministic():
    a1 = resolve_roster("crew")
    a2 = resolve_roster("crew")
    assert roster_receipt("crew", a1) == roster_receipt("crew", a2)


def test_advise_upgrades_names_teacher_without_escalating():
    assignments = resolve_roster("crew", slot_ids=["face", "receptionist"])
    advice = advise_upgrades(assignments)
    # face is high-stakes on rules -> advised; receptionist low-stakes -> not
    assert [x["slot_id"] for x in advice] == ["face"]
    assert advice[0]["recommend"] == "groq"
    # advice must not change the assignment itself
    assert assignments[0].model_id == "rules"


def test_partial_slot_selection():
    assignments = resolve_roster("crew", slot_ids=["face", "booker"])
    assert [a.slot_id for a in assignments] == ["face", "booker"]
