"""Virtual-town spatial metaphor for navigating a service landscape.

Studied from: dead-networks-20260916/report.md [eWorld]

Functional description: the whole service surface is rendered as a town —
each capability is a building you walk to, grouped into districts. Instead
of menus or URLs, navigation is spatial: ask for a service, get walking
directions; stroll and see what is near. The town is a real street graph
(districts connected by streets, buildings on street corners), and routing
is breadth-first search over that graph.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/town-metaphor"


@dataclass
class Building:
    """A service rendered as a place in the town."""

    id: str
    name: str
    kind: str
    district: str
    corner: str
    blurb: str = ""


@dataclass
class District:
    name: str
    corners: List[str] = field(default_factory=list)


class Town:
    """A walkable town of service-buildings connected by streets."""

    def __init__(self, name: str = "Levitown") -> None:
        self.name = name
        self._buildings: Dict[str, Building] = {}
        self._districts: Dict[str, District] = {}
        self._streets: Dict[str, set] = {}

    # -- construction -------------------------------------------------
    def add_district(self, name: str) -> None:
        if name not in self._districts:
            self._districts[name] = District(name)

    def add_street(self, a: str, b: str) -> None:
        """Lay a two-way street between corner ``a`` and corner ``b``."""
        for corner in (a, b):
            self._streets.setdefault(corner, set())
        self._streets[a].add(b)
        self._streets[b].add(a)

    def add_building(
        self,
        id: str,
        name: str,
        kind: str,
        district: str,
        corner: str,
        blurb: str = "",
    ) -> Building:
        if id in self._buildings:
            raise ValueError(f"building already exists: {id!r}")
        self.add_district(district)
        building = Building(id, name, kind, district, corner, blurb)
        self._buildings[id] = building
        if corner not in self._districts[district].corners:
            self._districts[district].corners.append(corner)
        return building

    # -- lookup -------------------------------------------------------
    def buildings(self) -> List[Building]:
        return list(self._buildings.values())

    def find(self, id: str) -> Building:
        return self._buildings[id]

    def find_by_kind(self, kind: str) -> List[Building]:
        return [b for b in self._buildings.values() if b.kind == kind]

    def find_by_district(self, district: str) -> List[Building]:
        return [b for b in self._buildings.values() if b.district == district]

    def search(self, query: str) -> List[Building]:
        q = query.lower()
        return [
            b
            for b in self._buildings.values()
            if q in b.name.lower() or q in b.kind.lower() or q in b.blurb.lower()
        ]

    # -- walking ------------------------------------------------------
    def route(self, from_id: str, to_id: str) -> List[str]:
        """Shortest walk between two buildings, as a list of corners.

        Empty list means unreachable (disconnected streets).
        """
        start = self.find(from_id).corner
        goal = self.find(to_id).corner
        if start == goal:
            return [start]
        prev: Dict[str, Optional[str]] = {start: None}
        queue = deque([start])
        while queue:
            here = queue.popleft()
            for nxt in sorted(self._streets.get(here, ())):
                if nxt not in prev:
                    prev[nxt] = here
                    if nxt == goal:
                        path = [goal]
                        while prev[path[-1]] is not None:
                            path.append(prev[path[-1]])  # type: ignore[arg-type]
                        return path[::-1]
                    queue.append(nxt)
        return []

    def directions(self, from_id: str, to_id: str) -> List[str]:
        """Human-readable walking directions from one building to another."""
        frm, to = self.find(from_id), self.find(to_id)
        if frm.id == to.id:
            return [f"You are already at {to.name}."]
        path = self.route(from_id, to_id)
        if not path:
            return [f"No street connects {frm.name} to {to.name} yet."]
        steps = [
            f"Leave {frm.name} ({frm.corner}).",
            f"Walk {len(path) - 1} block(s): "
            + " -> ".join(path)
            + f", arriving at {to.corner}.",
            f"You reach {to.name} in the {to.district} district.",
        ]
        return steps

    def nearby(self, building_id: str, blocks: int = 1) -> List[Building]:
        """Buildings within ``blocks`` street corners of the given building."""
        start = self.find(building_id).corner
        seen = {start: 0}
        queue = deque([start])
        while queue:
            here = queue.popleft()
            for nxt in self._streets.get(here, ()):
                if nxt not in seen:
                    seen[nxt] = seen[here] + 1
                    queue.append(nxt)
        corners = {c for c, d in seen.items() if d <= blocks}
        return [
            b
            for b in self._buildings.values()
            if b.corner in corners and b.id != building_id
        ]

    def describe(self) -> str:
        lines = [f"Welcome to {self.name}."]
        for dname in sorted(self._districts):
            bs = self.find_by_district(dname)
            lines.append(f"  {dname} district: {', '.join(b.name for b in bs)}")
        return "\n".join(lines)


def demo_town() -> Dict[str, object]:
    town = Town("Levitown")
    town.add_street("plaza", "market-cross")
    town.add_street("market-cross", "library-lane")
    town.add_street("plaza", "dockside")
    town.add_building("post", "Post Office", "messaging", "Civic", "plaza")
    town.add_building("ledger", "Ledger Hall", "finance", "Civic", "market-cross")
    town.add_building("archive", "Grand Archive", "memory", "Scholar", "library-lane")
    town.add_building("docks", "Ferry Docks", "transport", "Harbor", "dockside")
    return {
        "describe": town.describe(),
        "directions": town.directions("docks", "archive"),
        "nearby_post": [b.name for b in town.nearby("post")],
        "messaging": [b.name for b in town.find_by_kind("messaging")],
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_town(), indent=2))
