"""Tests for levi.identity.mandella — the surgeon."""

import pytest

from levi.identity.echo import EchoEngine
from levi.identity.mandella import MandellaEngine


def _reflection(**over):
    ident = {
        "name": "parent",
        "traits": {"caution": 0.6, "novelty": 0.4, "stability": 0.8},
        "params": {"tempo": 1.0, "depth": 2.0},
        "fragments": ["steady hand", "long view", "steady hand"],
        "lineage": ["gen0"],
    }
    ident.update(over)
    return EchoEngine().reflect(ident)


def test_produces_n_variants():
    vs = MandellaEngine().reconstruct(_reflection(), n_variants=4, seed="s1")
    assert len(vs) == 4


def test_deterministic_under_seed():
    a = MandellaEngine().reconstruct(_reflection(), n_variants=3, seed="abc")
    b = MandellaEngine().reconstruct(_reflection(), n_variants=3, seed="abc")
    assert a == b


def test_variants_differ_from_parent_and_record_lineage():
    vs = MandellaEngine().reconstruct(_reflection(), n_variants=2, seed="s2")
    for i, v in enumerate(vs):
        assert v["name"] == "parent#%d" % i
        assert v["lineage"][-1] == "parent"
        assert v["parent_signature"]
        assert isinstance(v["mutations"], list) and v["mutations"]


def test_repairs_happen_before_mutation():
    # duplicate fragment is repaired in every variant
    vs = MandellaEngine().reconstruct(_reflection(), n_variants=3, seed="s3")
    for v in vs:
        assert len(v["fragments"]) == len(set(v["fragments"]))


def test_mutations_bounded():
    vs = MandellaEngine().reconstruct(_reflection(), n_variants=10, seed="s4")
    for v in vs:
        for t, val in v["traits"].items():
            assert 0.0 <= val <= 1.0, (t, val)
        assert 0.85 <= v["params"]["tempo"] <= 1.15
        assert 1.7 <= v["params"]["depth"] <= 2.3


def test_bad_n_variants_raises():
    with pytest.raises(ValueError):
        MandellaEngine().reconstruct(_reflection(), n_variants=0, seed="x")


def test_bad_reflection_raises():
    with pytest.raises(ValueError):
        MandellaEngine().reconstruct({"not": "a reflection"}, n_variants=1)
