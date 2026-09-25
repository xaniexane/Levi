"""Proof for core/levi/cube: each declared law gets a machine check."""

import os
import tempfile

import pytest

from levi.cube import Cube, CubeError


def make_cube() -> Cube:
    c = Cube("sales", {"region": ["north", "south"], "month": ["jan", "feb"]})
    c.set("revenue", {"region": "north", "month": "jan"}, 100)
    c.set("revenue", {"region": "south", "month": "jan"}, 50)
    c.set("expense", {"region": "north", "month": "jan"}, 30)
    c.define_formula(
        "profit",
        lambda cube, m: (
            (cube.get("revenue", m) or 0) - (cube.get("expense", m) or 0)
            if cube.get("revenue", m) is not None or cube.get("expense", m) is not None
            else None
        ),
    )
    return c


def test_l1_no_positional_addresses():
    c = Cube("x", {"a": ["m1", "m2"]})
    with pytest.raises(CubeError):
        c.set("f", {"wrong": "m1"}, 1)  # unknown dimension
    with pytest.raises(CubeError):
        c.set("f", {"a": "nope"}, 1)  # unknown member
    with pytest.raises(CubeError):
        c.set("f", {}, 1)  # incomplete coordinate


def test_l2_formula_broadcasts_over_members():
    c = make_cube()
    assert c.get("profit", {"region": "north", "month": "jan"}) == 70
    # formula references facts by name; no cell addresses anywhere
    assert c.get("profit", {"region": "south", "month": "jan"}) == 50
    with pytest.raises(CubeError):
        c.set("profit", {"region": "north", "month": "jan"}, 1)  # formula is read-only


def test_l3_views_do_not_mutate():
    c = make_cube()
    before = c.to_dict()
    c.slice({"region": "north"})
    c.dice("revenue", {"month": "jan"})
    c.aggregate("revenue", over="month")
    assert c.to_dict() == before


def test_l4_missing_is_none_never_zero():
    c = make_cube()
    # expense never set for south/jan -> None, not 0
    assert c.get("expense", {"region": "south", "month": "jan"}) is None
    assert c.get("nope", {"region": "north", "month": "jan"}) is None
    # aggregate over an all-empty slice -> None, not 0
    assert c.aggregate("expense", over="region")["south"] is None
    assert c.aggregate("revenue", over="region")["north"] == 100


def test_l5_json_round_trip():
    c = make_cube()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "cube.json")
        c.save(p)
        c2 = Cube.load(p)
    assert c2.to_dict() == c.to_dict()
    assert c2.get("revenue", {"region": "north", "month": "jan"}) == 100


def test_l5_formula_stub_fails_loudly_until_reregistered():
    c = make_cube()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "cube.json")
        c.save(p)
        c2 = Cube.load(p)
    with pytest.raises(CubeError):
        c2.get("profit", {"region": "north", "month": "jan"})
    c2.define_formula("profit", lambda cube, m: 1)
    assert c2.get("profit", {"region": "north", "month": "jan"}) == 1


def test_slice_projects_views():
    c = make_cube()
    view = c.slice({"region": "north"})
    assert view["revenue"][(("month", "jan"),)] == 100
    assert view["revenue"][(("month", "feb"),)] is None
    assert view["profit"][(("month", "jan"),)] == 70


def test_duplicate_members_rejected():
    with pytest.raises(CubeError):
        Cube("x", {"a": ["m", "m"]})
    with pytest.raises(CubeError):
        Cube("x", {})
