"""Smoke: the megazord package imports and ships its 5 personas.

Regression for P1.1: ``DEFAULT_REGISTRY`` was never re-exported from
``megazord.personas`` which made the whole package unimportable.
"""

import pytest

import megazord
from megazord import MegaZord, DEFAULT_REGISTRY

EXPECTED_PERSONAS = {"CYBRUS", "ECHO", "ALPHA", "OMEGA", "RUNTIME"}


def test_megazord_imports():
    assert megazord.MegaZord is MegaZord
    assert megazord.DEFAULT_REGISTRY is DEFAULT_REGISTRY


def test_default_registry_has_five_personas():
    names = {p.name for p in DEFAULT_REGISTRY.all()}
    assert names == EXPECTED_PERSONAS


def test_megazord_instantiates_with_default_persona():
    mz = MegaZord()
    assert mz.persona is not None
    assert mz.persona.name == "ALPHA"


@pytest.mark.parametrize("persona", sorted(EXPECTED_PERSONAS))
def test_megazord_instantiates_each_persona(persona):
    mz = MegaZord(persona=persona.lower())
    assert mz.persona.name == persona


def test_megazord_rejects_unknown_persona():
    with pytest.raises(ValueError, match="Unknown persona"):
        MegaZord(persona="levi")
