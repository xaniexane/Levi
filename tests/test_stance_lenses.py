"""Tests for the stance lenses (expression-only working postures)."""

from levi.personas import stance_lenses
from levi.personas.lenses import Lens


def test_four_stances_registered():
    assert set(stance_lenses.STANCE_LENSES) == {
        "predator",
        "conundrum",
        "plainspeak",
        "expander",
    }


def test_law_present():
    law = stance_lenses.STANCE_LAW
    assert "never overrides safety" in law
    assert "LEVI stays LEVI" in law


def test_lookup_and_default():
    assert stance_lenses.get_stance_lens("predator").name == "Predator"
    assert stance_lenses.get_stance_lens("nope") is None
    assert stance_lenses.resolve_stance("nope").id == stance_lenses.DEFAULT_STANCE
    assert stance_lenses.resolve_stance("expander").id == "expander"


def test_as_lens_roundtrip():
    lens = stance_lenses.get_stance_lens("conundrum").as_lens()
    assert isinstance(lens, Lens)
    assert lens.id == "conundrum"
    assert lens.text_fields()


def test_no_mask_violations():
    bad = stance_lenses.mask_violations()
    assert bad == {}, f"mask violations found: {bad}"


def test_every_field_passes_check_no_mask_directly():
    from levi.bot.persona import check_no_mask

    for stance in stance_lenses.list_stance_lenses():
        for text in stance.text_fields():
            assert check_no_mask(text) == [], f"{stance.id}: {text!r}"


def test_stance_fields_complete():
    for stance in stance_lenses.list_stance_lenses():
        assert stance.id and stance.name and stance.tagline
        assert stance.tone.word_choice and stance.tone.cadence
        assert len(stance.tone.do) >= 2
        assert len(stance.tone.dont) >= 2
        assert stance.stance and stance.role


def test_interop_self_registration():
    from levi.interop import registry as interop

    assert "persona-stances" in interop.modules()
    declared = interop.check("persona-stances")
    for stance_id in stance_lenses.STANCE_LENSES:
        assert f"persona.stance.{stance_id}" in declared["provides"]
