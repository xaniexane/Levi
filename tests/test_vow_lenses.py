"""Tests for the vow lenses package (levi.personas.vow_lenses).

- All three vow lenses load, with no id collision against the canon six
  or the other lens families.
- Every lens text field passes check_no_mask.
- get_vow_lens round-trips; unknown ids return None.
- Lattice registration is idempotent and uses the vow_ prefix.
"""

from levi.bot.persona import check_no_mask
from levi.personas.duty_lenses import DUTY_LENSES
from levi.personas.lenses import LENSES
from levi.personas.signal_lenses import SIGNAL_LENSES
from levi.personas.vow_lenses import (
    VOW_LENSES,
    get_vow_lens,
    list_vow_lenses,
    register_vow_lenses_into_lattice,
)

EXPECTED_IDS = ["kept-word", "open-ledger", "plain-vow"]  # stable sorted order


class _StubLattice:
    def __init__(self):
        self.registry = {}

    def register(self, persona):
        self.registry[persona.id] = persona


def test_all_three_vow_lenses_load():
    lenses = list_vow_lenses()
    assert [v.id for v in lenses] == EXPECTED_IDS
    for lens in lenses:
        assert lens.name
        assert lens.tagline
        assert lens.stance
        assert lens.role
        assert lens.tone.word_choice
        assert lens.tone.cadence
        assert lens.tone.do and lens.tone.dont


def test_no_collision_with_other_families():
    others = set(LENSES) | set(SIGNAL_LENSES) | set(DUTY_LENSES)
    assert not (set(VOW_LENSES) & others)


def test_every_text_field_passes_check_no_mask():
    for lens in list_vow_lenses():
        for field_text in lens.text_fields():
            violations = check_no_mask(field_text)
            assert violations == [], (lens.id, field_text, violations)


def test_get_vow_lens_round_trip():
    for lid in EXPECTED_IDS:
        lens = get_vow_lens(lid)
        assert lens is not None and lens.id == lid
    assert get_vow_lens("no-such-vow") is None


def test_lattice_registration_idempotent():
    lattice = _StubLattice()
    assert register_vow_lenses_into_lattice(lattice) == 3
    assert register_vow_lenses_into_lattice(lattice) == 0
    assert sorted(lattice.registry) == [f"vow_{lid}" for lid in EXPECTED_IDS]
