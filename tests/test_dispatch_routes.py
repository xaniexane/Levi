"""Tests for dispatch route ranking — declared synthetic road data.

Hermetic: no network, no HOME writes. Run from zero:
    cd ~/workspace/levi && python3 -m pytest -q tests/test_dispatch_routes.py

Expected values below are hand-computed from the fixture graph in
levi.dispatch.routes.SyntheticRoadNetwork with
FuelParams(mpg_loaded=6.0, mpg_empty=8.0, dollars_per_gallon=4.00):

  SGF->STL->CHI : 515 mi -> fuel 515/6*400 = 34333c + toll 1250 = 35583
  SGF->STL->IND->CHI : 640 mi -> 42667c + toll 1600 = 44267
  SGF->KC->CHI  : 680 mi -> 45333c + toll 0    = 45333
  deadhead MEM->SGF : 290 mi / 8 mpg * $4 = 14500c
"""

from __future__ import annotations

import pytest

from levi.dispatch.routes import (
    Edge,
    FuelParams,
    RoadNetwork,
    RouteError,
    SyntheticRoadNetwork,
    rank_routes,
)

FUEL = FuelParams(mpg_loaded=6.0, mpg_empty=8.0, dollars_per_gallon=4.00)


def test_synthetic_network_is_labeled() -> None:
    assert SyntheticRoadNetwork().kind == "synthetic"


def test_ranking_math_known_values() -> None:
    net = SyntheticRoadNetwork()
    ranked = rank_routes(net, "SGF", "CHI", FUEL, max_routes=3)
    assert [r.total_cents for r in ranked] == [35583, 44267, 45333]
    assert [r.path for r in ranked] == [
        ("SGF", "STL", "CHI"),
        ("SGF", "STL", "IND", "CHI"),
        ("SGF", "KC", "CHI"),
    ]
    cheapest = ranked[0]
    assert cheapest.miles == 515.0
    assert cheapest.toll_cents == 1250
    assert cheapest.fuel_cents == 34333


def test_tolls_can_beat_shorter_miles() -> None:
    # The toll-free KC route (680 mi) loses to the tolled STL-IND route
    # (640 mi) on total cost: the math weighs dollars, not just miles.
    net = SyntheticRoadNetwork()
    ranked = rank_routes(net, "SGF", "CHI", FUEL, max_routes=4)
    by_path = {r.path: r for r in ranked}
    assert by_path[("SGF", "STL", "IND", "CHI")].total_cents < by_path[("SGF", "KC", "CHI")].total_cents


def test_deadhead_math() -> None:
    net = SyntheticRoadNetwork()
    ranked = rank_routes(net, "SGF", "CHI", FUEL, deadhead_from="MEM", max_routes=1)
    best = ranked[0]
    assert best.deadhead_miles == 290.0
    assert best.deadhead_cents == 14500
    assert best.total_cents == 35583 + 14500


def test_ranking_is_deterministic() -> None:
    net = SyntheticRoadNetwork()
    first = rank_routes(net, "SGF", "CHI", FUEL, max_routes=4)
    second = rank_routes(net, "SGF", "CHI", FUEL, max_routes=4)
    assert first == second


def test_pluggable_seam_custom_network() -> None:
    class TinyNet(RoadNetwork):
        kind = "custom-test"

        def nodes(self) -> list[str]:
            return ["A", "B", "C"]

        def edges_from(self, node: str) -> list[Edge]:
            adj = {
                "A": [Edge("A", "B", 100.0, 0), Edge("A", "C", 250.0, 0)],
                "B": [Edge("B", "C", 100.0, 500)],
                "C": [],
            }
            return adj[node]

    ranked = rank_routes(TinyNet(), "A", "C", FUEL, max_routes=2)
    # A->B->C: 200 mi -> 13333c fuel + 500 toll = 13833
    # A->C:    250 mi -> 16667c fuel + 0 toll   = 16667
    assert [r.total_cents for r in ranked] == [13833, 16667]
    assert ranked[0].path == ("A", "B", "C")


def test_unknown_node_refused() -> None:
    net = SyntheticRoadNetwork()
    with pytest.raises(RouteError):
        rank_routes(net, "SGF", "NOWHERE", FUEL)


def test_same_origin_destination_is_empty() -> None:
    net = SyntheticRoadNetwork()
    assert rank_routes(net, "SGF", "SGF", FUEL) == []


def test_bad_fuel_params_refused() -> None:
    with pytest.raises(RouteError):
        FuelParams(mpg_loaded=0)
