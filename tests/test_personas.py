"""Tests for the companion lenses package (levi.personas).

- All six lenses load.
- Every lens text field passes check_no_mask (no borrowed identity,
  no provider branding).
- get_lens round-trips.
- set_active_lens fails closed on unknown ids (returns False, keeps current).
- Active-lens persistence round-trips via the LEVI_PERSONAS_STATE env override.
"""

import os

import pytest

from levi.bot.persona import check_no_mask
from levi.personas import (
    DEFAULT_LENS,
    active_lens,
    get_lens,
    list_lenses,
    set_active_lens,
)

EXPECTED_IDS = ["friend", "mentor", "challenger", "protector", "trickster", "archivist"]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Point persistence at a temp file so tests never touch ~/.levi."""
    monkeypatch.setenv("LEVI_PERSONAS_STATE", str(tmp_path / "active.json"))


def test_all_six_lenses_load():
    lenses = list_lenses()
    assert [l.id for l in lenses] == EXPECTED_IDS
    for lens in lenses:
        assert lens.name
        assert lens.tagline
        assert lens.stance
        assert lens.role
        assert lens.tone.word_choice
        assert lens.tone.cadence
        assert lens.tone.do and lens.tone.dont


def test_every_text_field_passes_check_no_mask():
    for lens in list_lenses():
        for field_text in lens.text_fields():
            violations = check_no_mask(field_text)
            assert violations == [], (
                f"lens {lens.id!r} has no-mask violations in {field_text!r}: {violations}"
            )


def test_get_lens_round_trip():
    for lens in list_lenses():
        fetched = get_lens(lens.id)
        assert fetched is not None
        assert fetched == lens
    assert get_lens("bogus-lens") is None


def test_default_active_lens():
    assert active_lens().id == DEFAULT_LENS


def test_select_unknown_id_fails_closed():
    assert set_active_lens("mentor")
    assert active_lens().id == "mentor"
    assert set_active_lens("nope-not-a-lens") is False
    # Current selection untouched.
    assert active_lens().id == "mentor"
    assert set_active_lens("") is False
    assert active_lens().id == "mentor"


def test_active_persistence_round_trips(tmp_path, monkeypatch):
    state_file = tmp_path / "persist.json"
    monkeypatch.setenv("LEVI_PERSONAS_STATE", str(state_file))
    assert set_active_lens("trickster") is True
    # Re-read from disk as a fresh observation (new "process view").
    assert state_file.exists()
    assert active_lens().id == "trickster"
    assert set_active_lens("archivist") is True
    assert active_lens().id == "archivist"


def test_corrupt_state_falls_back_to_default(tmp_path, monkeypatch):
    state_file = tmp_path / "bad.json"
    state_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("LEVI_PERSONAS_STATE", str(state_file))
    assert active_lens().id == DEFAULT_LENS


def test_lattice_bridge_registers_six(tmp_path, monkeypatch):
    from levi.persona.lattice import PersonaLattice
    from levi.personas import register_into_lattice

    lat = PersonaLattice()
    n = register_into_lattice(lat)
    assert n == 6
    for lid in EXPECTED_IDS:
        assert lat.get(f"lens_{lid}") is not None
    # Idempotent.
    assert register_into_lattice(lat) == 0


def test_lens_text_fields_are_all_strings():
    for lens in list_lenses():
        for field_text in lens.text_fields():
            assert isinstance(field_text, str) and field_text, lens.id
