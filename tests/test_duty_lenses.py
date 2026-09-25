"""Tests for the duty lenses (stewardship voice family)."""

import pytest

from levi.bot.persona import check_no_mask
from levi.personas import (
    DEFAULT_DUTY_LENS,
    DUTY_LAW,
    DUTY_LENSES,
    get_duty_lens,
    list_duty_lenses,
    register_duty_lenses_into_lattice,
)
from levi.personas.duty_lenses import DEFAULT_DUTY_LENS as _MOD_DEFAULT


def test_three_lenses_present():
    assert sorted(DUTY_LENSES) == ["sentry", "steward", "witness"]
    assert [lens.id for lens in list_duty_lenses()] == [
        "steward",
        "witness",
        "sentry",
    ]


def test_default_duty_lens():
    assert DEFAULT_DUTY_LENS == "steward"
    assert _MOD_DEFAULT == DEFAULT_DUTY_LENS


def test_get_duty_lens():
    assert get_duty_lens("sentry").name == "Sentry"


def test_unknown_duty_lens_denied_closed():
    with pytest.raises(KeyError) as excinfo:
        get_duty_lens("jester")
    assert "sentry" in str(excinfo.value)  # names what's available


def test_every_text_field_passes_no_mask():
    for lens in list_duty_lenses():
        for field in lens.text_fields():
            violations = check_no_mask(field)
            assert violations == [], f"{lens.id}: {violations} in {field!r}"


def test_duty_law_carries_lens_law():
    from levi.personas.lenses import LENS_LAW

    assert LENS_LAW in DUTY_LAW


def test_to_dict_shape():
    d = get_duty_lens("witness").to_dict()
    assert d["id"] == "witness"
    assert "tone" in d and "stance" in d and "role" in d


class _FakeLattice:
    def __init__(self):
        self.registry = {}

    def register(self, persona):
        self.registry[persona.id] = persona


def test_lattice_bridge_idempotent():
    lattice = _FakeLattice()
    added_first = register_duty_lenses_into_lattice(lattice)
    added_second = register_duty_lenses_into_lattice(lattice)
    assert added_first == 3
    assert added_second == 0
    assert sorted(lattice.registry) == [
        "duty_sentry",
        "duty_steward",
        "duty_witness",
    ]


def test_lattice_bridge_without_persona_module_returns_zero():
    class _NoRegistry:
        registry = None

    assert register_duty_lenses_into_lattice(_NoRegistry()) == 0
