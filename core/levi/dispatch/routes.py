"""Route ranking for the LEVI transportation edition (truck dispatch).

ROUTING DATA DECISION (declared at activation, 2026-09-22):
the OSRM public routing server is unreachable from this build environment,
so this module ships with a DECLARED SYNTHETIC road-network fallback —
:class:`SyntheticRoadNetwork`, a small deterministic graph carrying
distances, toll segments, and speed limits. It is labeled synthetic
wherever it surfaces (``network.kind == "synthetic"``). The ranking engine
depends only on the :class:`RoadNetwork` protocol: a real road-data source
(OSRM, Valhalla, a static OSM extract) plugs in later by implementing the
same interface — no ranking code changes. Live traffic and GPS are NOT
promised and have no seam here.

Cost model (stated plainly, per route):
    fuel_cents     = miles / mpg_loaded * dollars_per_gallon, in cents
    toll_cents     = sum of toll segments on the path
    deadhead_cents = empty miles from the driver's home base to the origin
                     / mpg_empty * dollars_per_gallon, in cents (toll-free
                     by stated assumption: deadhead runs choose free roads)
    total_cents    = fuel_cents + toll_cents + deadhead_cents
Ranking is cheapest total first; ties break on fewer miles, then path order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# -- road network seam ----------------------------------------------------


@dataclass(frozen=True)
class Edge:
    """One directed road segment."""

    from_node: str
    to_node: str
    miles: float
    toll_cents: int = 0
    mph: float = 65.0


class RoadNetwork(ABC):
    """Pluggable road-data source. Synthetic or real, same contract."""

    kind: str = "abstract"

    @abstractmethod
    def nodes(self) -> list[str]:
        """All node ids in the network."""

    @abstractmethod
    def edges_from(self, node: str) -> list[Edge]:
        """Outgoing edges from ``node``."""

    # -- shared path enumeration (simple paths, deterministic) -------------

    def simple_paths(
        self, origin: str, destination: str, max_paths: int = 32
    ) -> list[list[Edge]]:
        """Enumerate simple paths, cheapest-first by (miles, path)."""
        if origin == destination:
            return []
        found: list[list[Edge]] = []

        def dfs(current: str, path: list[Edge], visited: set[str]) -> None:
            if len(found) >= max_paths:
                return
            for edge in sorted(self.edges_from(current), key=lambda e: e.to_node):
                if edge.to_node in visited:
                    continue
                leg = path + [edge]
                if edge.to_node == destination:
                    found.append(leg)
                    continue
                visited.add(edge.to_node)
                dfs(edge.to_node, leg, visited)
                visited.discard(edge.to_node)

        dfs(origin, [], {origin})
        found.sort(
            key=lambda legs: (
                sum(e.miles for e in legs),
                tuple(e.to_node for e in legs),
            )
        )
        return found

    def shortest_miles(self, origin: str, destination: str) -> float:
        """Shortest-path distance in miles (deadhead legs)."""
        paths = self.simple_paths(origin, destination, max_paths=64)
        if not paths:
            raise RouteError(f"no path {origin!r} -> {destination!r}")
        return min(sum(e.miles for e in legs) for legs in paths)


class RouteError(ValueError):
    """No route, unknown node, or bad routing input."""


class SyntheticRoadNetwork(RoadNetwork):
    """Declared synthetic fallback: deterministic fixture graph.

    Distances are plausible midwest-lane mileages, NOT surveyed data.
    Tolls are fixture values. Never presented as real road data.
    """

    kind = "synthetic"

    def __init__(self) -> None:
        self._adj: dict[str, list[Edge]] = {}
        pairs = [
            # (a, b, miles, toll_cents, mph)
            ("SGF", "STL", 215.0, 0, 65.0),
            ("SGF", "KC", 170.0, 0, 65.0),
            ("STL", "CHI", 300.0, 1250, 65.0),
            ("KC", "CHI", 510.0, 0, 65.0),
            ("STL", "IND", 240.0, 650, 65.0),
            ("IND", "CHI", 185.0, 950, 65.0),
            ("SGF", "MEM", 290.0, 0, 60.0),
            ("MEM", "IND", 390.0, 0, 65.0),
        ]
        for a, b, miles, toll, mph in pairs:
            self._add(a, b, miles, toll, mph)
            self._add(b, a, miles, toll, mph)

    def _add(self, a: str, b: str, miles: float, toll: int, mph: float) -> None:
        self._adj.setdefault(a, []).append(
            Edge(from_node=a, to_node=b, miles=miles, toll_cents=toll, mph=mph)
        )

    def nodes(self) -> list[str]:
        return sorted(self._adj)

    def edges_from(self, node: str) -> list[Edge]:
        if node not in self._adj:
            raise RouteError(f"unknown node {node!r}")
        return list(self._adj[node])


# -- ranking ---------------------------------------------------------------


@dataclass(frozen=True)
class FuelParams:
    mpg_loaded: float = 6.0
    mpg_empty: float = 8.0
    dollars_per_gallon: float = 4.00

    def __post_init__(self) -> None:
        if self.mpg_loaded <= 0 or self.mpg_empty <= 0:
            raise RouteError("mpg must be positive")
        if self.dollars_per_gallon < 0:
            raise RouteError("fuel price cannot be negative")


@dataclass(frozen=True)
class RankedRoute:
    path: tuple[str, ...]
    miles: float
    toll_cents: int
    fuel_cents: int
    deadhead_miles: float = 0.0
    deadhead_cents: int = 0
    total_cents: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "total_cents", self.fuel_cents + self.toll_cents + self.deadhead_cents
        )


def _cents(miles: float, mpg: float, dollars_per_gallon: float) -> int:
    return int(round(miles / mpg * dollars_per_gallon * 100))


def rank_routes(
    network: RoadNetwork,
    origin: str,
    destination: str,
    fuel: FuelParams | None = None,
    deadhead_from: str | None = None,
    max_routes: int = 3,
) -> list[RankedRoute]:
    """Rank alternate routes cheapest-first. Deterministic.

    ``deadhead_from``: driver's home base node — empty miles home->origin
    are costed at ``mpg_empty``, toll-free by stated assumption.
    """
    fuel = fuel or FuelParams()
    if origin not in network.nodes() or destination not in network.nodes():
        raise RouteError(f"unknown origin/destination {origin!r} -> {destination!r}")
    deadhead_miles = (
        network.shortest_miles(deadhead_from, origin) if deadhead_from else 0.0
    )
    deadhead_cents = (
        _cents(deadhead_miles, fuel.mpg_empty, fuel.dollars_per_gallon)
        if deadhead_from
        else 0
    )

    ranked: list[RankedRoute] = []
    for legs in network.simple_paths(origin, destination):
        miles = sum(e.miles for e in legs)
        ranked.append(
            RankedRoute(
                path=tuple([origin] + [e.to_node for e in legs]),
                miles=miles,
                toll_cents=sum(e.toll_cents for e in legs),
                fuel_cents=_cents(miles, fuel.mpg_loaded, fuel.dollars_per_gallon),
                deadhead_miles=deadhead_miles,
                deadhead_cents=deadhead_cents,
            )
        )
    ranked.sort(key=lambda r: (r.total_cents, r.miles, r.path))
    return ranked[:max_routes]
