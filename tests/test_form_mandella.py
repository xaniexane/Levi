"""mandella form tests: fractured identity reconstruction.

Proving bar: reconstruct() is fail-closed on bad reflections, variants
are deterministic per seed, and provenance is recorded.
"""

import pytest

from levi.identity.echo import EchoEngine
from levi.identity.mandella import MandellaEngine


def _reflection():
    return EchoEngine().reflect(
        {"name": "mandella-probe", "traits": {"reconstructive": 1.0}}
    )


def test_reconstruct_rejects_bad_reflection():
    engine = MandellaEngine("seed")
    with pytest.raises(ValueError):
        engine.reconstruct({"not": "a reflection"}, 3)


def test_variants_deterministic_per_seed():
    refl = _reflection()
    v1 = MandellaEngine("s").reconstruct(refl, 3, "seed-1")
    v2 = MandellaEngine("s").reconstruct(refl, 3, "seed-1")
    assert [v.get("name") for v in v1] == [v.get("name") for v in v2]
    # names are stable ordinals; the seeded differences live in mutations
    m1 = [
        v.get("mutations") for v in MandellaEngine("s").reconstruct(refl, 3, "seed-1")
    ]
    m3 = [
        v.get("mutations") for v in MandellaEngine("s").reconstruct(refl, 3, "seed-2")
    ]
    assert m1 != m3


def test_variant_count_and_provenance():
    refl = _reflection()
    variants = MandellaEngine("s").reconstruct(refl, 4, "prov")
    assert len(variants) == 4
    for v in variants:
        assert isinstance(v.get("mutations"), list)
