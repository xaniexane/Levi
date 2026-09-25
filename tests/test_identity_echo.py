"""Tests for levi.identity.echo — the mirror."""

import pytest

from levi.identity.echo import EchoEngine, reflection_to_dict


def _identity(**over):
    base = {
        "name": "test-id",
        "traits": {"caution": 0.6, "novelty": 0.4},
        "params": {"tempo": 1.0},
        "fragments": ["steady hand", "long view"],
        "lineage": [],
    }
    base.update(over)
    return base


def test_reflect_deterministic():
    eng = EchoEngine()
    a = reflection_to_dict(eng.reflect(_identity()))
    b = reflection_to_dict(eng.reflect(_identity()))
    assert a == b


def test_coherent_identity_scores_high():
    r = EchoEngine().reflect(_identity())
    assert 0.0 <= r.coherence <= 1.0
    assert r.coherence == 1.0
    assert r.fractures == []


def test_out_of_range_trait_fractures():
    r = EchoEngine().reflect(_identity(traits={"caution": 1.7}))
    assert any(f["type"] == "trait-out-of-range" for f in r.fractures)
    assert r.coherence < 1.0


def test_fragment_conflict_fractures():
    r = EchoEngine().reflect(_identity(fragments=["brave", "not:brave"]))
    assert any(f["type"] == "fragment-conflict" for f in r.fractures)


def test_duplicate_fragment_fractures():
    r = EchoEngine().reflect(_identity(fragments=["x", "x"]))
    assert any(f["type"] == "fragment-duplicate" for f in r.fractures)


def test_mirror_is_faithful_copy():
    ident = _identity()
    r = EchoEngine().reflect(ident)
    assert r.mirror["traits"] == ident["traits"]
    assert r.mirror["name"] == "test-id"


def test_signature_stable_and_hex():
    r = EchoEngine().reflect(_identity())
    assert len(r.signature) == 64
    assert all(c in "0123456789abcdef" for c in r.signature)


def test_non_dict_raises():
    with pytest.raises(ValueError):
        EchoEngine().reflect("nope")


def test_module_identity_reflects():
    from levi.identity.scope import iter_module_identities

    idents = iter_module_identities()
    assert len(idents) > 10
    r = EchoEngine().reflect(idents[0])
    assert 0.0 <= r.coherence <= 1.0
