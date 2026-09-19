"""Tests for the signal lenses package (levi.personas.signal_lenses).

- All three signal lenses load, with no id collision against the canon six.
- Every lens text field passes check_no_mask.
- get_signal_lens round-trips; unknown ids return None.
"""

from levi.bot.persona import check_no_mask
from levi.personas import (
    SIGNAL_LENSES,
    get_signal_lens,
    list_signal_lenses,
    register_signal_lenses_into_lattice,
)
from levi.personas.lenses import LENSES

EXPECTED_IDS = ["drill", "terse", "witness"]  # stable sorted order


def test_all_three_signal_lenses_load():
    lenses = list_signal_lenses()
    assert [sg.id for sg in lenses] == EXPECTED_IDS
    for lens in lenses:
        assert lens.name
        assert lens.tagline
        assert lens.stance
        assert lens.role
        assert lens.tone.word_choice
        assert lens.tone.cadence
        assert lens.tone.do and lens.tone.dont


def test_no_collision_with_canon_lenses():
    assert not (set(SIGNAL_LENSES) & set(LENSES))


def test_every_text_field_passes_check_no_mask():
    for lens in list_signal_lenses():
        for field_text in lens.text_fields():
            violations = check_no_mask(field_text)
            assert violations == [], (
                f"signal lens {lens.id!r} field {field_text!r}: {violations}"
            )


def test_get_signal_lens_round_trip():
    assert get_signal_lens("terse").name == "Terse"
    assert get_signal_lens("nope") is None


def test_register_into_lattice_is_callable_and_idempotent():
    class _Lattice:
        def __init__(self):
            self.registry = {}

        def register(self, persona):
            self.registry[persona.id] = persona

    lattice = _Lattice()
    first = register_signal_lenses_into_lattice(lattice)
    second = register_signal_lenses_into_lattice(lattice)
    assert first == 3
    assert second == 0
    assert set(lattice.registry) == {"signal_drill", "signal_terse", "signal_witness"}


def test_register_handles_missing_lattice_gracefully():
    assert register_signal_lenses_into_lattice(None) == 0
