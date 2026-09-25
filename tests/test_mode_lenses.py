"""Tests for the mode lenses family (levi.personas.mode_lenses).

- All six mode lenses load.
- Every text field passes check_no_mask (no borrowed identity, no
  provider branding).
- get_mode_lens round-trips and returns None for unknown ids.
- The canon six lenses and signal lenses are untouched by this module.
- Lattice registration is idempotent and uses the mode_ prefix.
"""

from levi.bot.persona import check_no_mask
from levi.personas.mode_lenses import (
    get_mode_lens,
    list_mode_lenses,
    register_mode_lenses_into_lattice,
)

EXPECTED_IDS = sorted(
    ["deep-dive", "receipts", "field-kit", "quiet-brief", "pair-hands", "scout"]
)


def test_all_six_mode_lenses_load():
    lenses = list_mode_lenses()
    assert [lens.id for lens in lenses] == EXPECTED_IDS
    for lens in lenses:
        assert lens.name
        assert lens.tagline
        assert lens.stance
        assert lens.role
        assert len(lens.tone.do) >= 3
        assert len(lens.tone.dont) >= 3


def test_every_text_field_passes_check_no_mask():
    for lens in list_mode_lenses():
        for field_text in lens.text_fields():
            violations = check_no_mask(field_text)
            assert not violations, f"{lens.id}: {violations}"


def test_get_mode_lens_round_trips():
    for lens in list_mode_lenses():
        assert get_mode_lens(lens.id) is lens
    assert get_mode_lens("nope") is None


def test_canon_and_signal_lenses_untouched():
    from levi.personas import LENSES, SIGNAL_LENSES

    assert "deep-dive" not in LENSES
    assert "receipts" not in LENSES
    assert "deep-dive" not in SIGNAL_LENSES
    assert len(LENSES) == 6


def test_lattice_registration_is_idempotent():
    class FakeLattice:
        def __init__(self):
            self.registry = {}

        def register(self, persona):
            self.registry[persona.id] = persona

    lattice = FakeLattice()
    added = register_mode_lenses_into_lattice(lattice)
    assert added == 6
    assert register_mode_lenses_into_lattice(lattice) == 0  # idempotent
    assert all(pid.startswith("mode_") for pid in lattice.registry)
