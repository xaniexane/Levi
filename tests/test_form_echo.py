"""echo form tests: the mirror.

Proving bar: reflect() is fail-closed on non-dict identities (hostile
input is rejected, never reflected), coherence is bounded 0..1, and the
reflection signature is deterministic.
"""

import pytest

from levi.identity.cycle import ORGANISM_FORMS
from levi.identity.echo import EchoEngine


def test_reflect_rejects_non_dict_identities():
    engine = EchoEngine()
    for bad in ("echo", 42, None, ["echo"], b"echo"):
        with pytest.raises(ValueError):
            engine.reflect(bad)


def test_reflect_all_organism_forms_green():
    engine = EchoEngine()
    assert len(ORGANISM_FORMS) == 18
    for name, spec in ORGANISM_FORMS.items():
        identity = {"name": name, "role": spec["role"], "traits": dict(spec["traits"])}
        r = engine.reflect(identity)
        assert 0.0 <= r.coherence <= 1.0, name
        assert isinstance(r.fractures, list)


def test_reflection_signature_deterministic():
    engine = EchoEngine()
    ident = {"name": "echo", "traits": {"reflective": 1.0}}
    assert engine.reflect(ident).signature == engine.reflect(ident).signature


def test_fractures_lower_coherence():
    engine = EchoEngine()
    whole = engine.reflect({"name": "x", "traits": {"a": 1.0}})
    # traits must be numeric; a non-numeric trait is a fracture
    broken = engine.reflect({"name": "x", "traits": {"a": "not-a-number"}})
    assert broken.coherence < whole.coherence
    assert broken.fractures
