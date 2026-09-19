"""LEVI's fog-of-war wargame: double-blind play under an umpire.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #39)

The old mechanism: two players who cannot see each other's pieces. Each
writes *orders* for the turn — movement, and nothing else is certain —
and an umpire, who sees the whole map, executes them. The umpire is the
engine of honesty: they resolve what the rules cover by table and dice,
and adjudicate what the rules *don't* cover by judgment. Neither player
ever sees the true map; each sees their own units plus whatever of the
enemy has been *spotted*.

This module implements it:

* ``Map`` — a small grid; units have positions hidden from the enemy.
* ``Order`` — written orders per turn (move to a square, hold, scout).
* ``Umpire`` — the rules engine: validates orders, moves units, computes
  spotting (within range, line of sight is distance-based here), and
  resolves combat by dice against a strength table. A ``human_override``
  hook lets a person overrule any adjudication the rules don't cover —
  that hook *is* the umpire's judgment, made explicit.
* Double-blind views: ``view_for(player)`` returns only that player's
  units plus spotted enemies. Spotted status decays: last turn's sighting
  is a memory, not a fact.

Dice are seedable so adjudication is reproducible when you want it to be.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/kriegsspiel"

Coord = Tuple[int, int]


class OrderKind(Enum):
    MOVE = "move"
    HOLD = "hold"
    SCOUT = "scout"  # move with extended spotting radius this turn


@dataclass
class Order:
    """A written order for one unit, submitted before the turn resolves."""

    unit_id: str
    kind: OrderKind
    destination: Optional[Coord] = None

    def validate(self) -> None:
        if self.kind == OrderKind.MOVE and self.destination is None:
            raise ValueError("move orders require a destination")


@dataclass
class Unit:
    unit_id: str
    owner: str
    strength: int  # combat dice / hit points, both
    position: Coord
    spotting_range: int = 2
    alive: bool = True

    def distance_to(self, other: Coord) -> int:
        return abs(self.position[0] - other[0]) + abs(self.position[1] - other[1])


# Combat table: attacker strength vs defender strength -> attacker win chance
# on a single d6 roll. The table is the rules; the umpire's judgment is the rest.
COMBAT_TABLE: Dict[Tuple[int, int], int] = {
    (3, 1): 5,
    (3, 2): 4,
    (3, 3): 3,
    (2, 1): 4,
    (2, 2): 3,
    (2, 3): 2,
    (1, 1): 3,
    (1, 2): 2,
    (1, 3): 1,
}


@dataclass
class Adjudication:
    """Everything the umpire decided this turn, in the open."""

    turn: int
    movements: List[Dict[str, object]] = field(default_factory=list)
    combats: List[Dict[str, object]] = field(default_factory=list)
    spots: List[Dict[str, object]] = field(default_factory=list)
    overrides: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class Map:
    """The true map. Only the umpire ever holds this."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.units: Dict[str, Unit] = {}

    def add_unit(self, unit: Unit) -> None:
        if not (
            0 <= unit.position[0] < self.width and 0 <= unit.position[1] < self.height
        ):
            raise ValueError("unit placed off the map")
        self.units[unit.unit_id] = unit

    def in_bounds(self, coord: Coord) -> bool:
        return 0 <= coord[0] < self.width and 0 <= coord[1] < self.height

    def unit_at(self, coord: Coord) -> Optional[Unit]:
        for u in self.units.values():
            if u.alive and u.position == coord:
                return u
        return None


class Umpire:
    """The rules engine with a human-judgment hook.

    ``human_override`` is a callable receiving (context_dict) and returning
    either None (no override) or a dict describing the ruling. Anything the
    tables don't cover flows through it — the hook is the whole point.
    """

    def __init__(
        self,
        game_map: Map,
        seed: Optional[int] = None,
        human_override: Optional[
            Callable[[Dict[str, object]], Optional[Dict[str, object]]]
        ] = None,
    ) -> None:
        self.map = game_map
        self.rng = random.Random(seed)
        self.human_override = human_override
        self.turn = 0
        self.history: List[Adjudication] = []
        # spotted[(viewer, unit_id)] = last turn seen
        self._spotted: Dict[Tuple[str, str], int] = {}

    # -- orders -----------------------------------------------------------

    def resolve_turn(self, orders: Dict[str, List[Order]]) -> Adjudication:
        """Execute one turn of written orders for all players."""
        self.turn += 1
        adj = Adjudication(turn=self.turn)

        # 1. Ask the human hook about anything unusual *before* the rules run.
        if self.human_override is not None:
            ruling = self.human_override(
                {
                    "turn": self.turn,
                    "orders": {p: [o.__dict__ for o in os] for p, os in orders.items()},
                }
            )
            if ruling:
                adj.overrides.append(json.dumps(ruling))
                adj.notes.append("human override applied before resolution")

        # 2. Movement (rules engine).
        for player, player_orders in orders.items():
            for order in player_orders:
                order.validate()
                unit = self.map.units.get(order.unit_id)
                if unit is None or not unit.alive or unit.owner != player:
                    adj.notes.append(
                        f"order for {order.unit_id} ignored: not yours / not alive"
                    )
                    continue
                if order.kind == OrderKind.MOVE and order.destination is not None:
                    if not self.map.in_bounds(order.destination):
                        adj.notes.append(f"{unit.unit_id}: destination off map, holds")
                        continue
                    blocker = self.map.unit_at(order.destination)
                    if blocker is not None and blocker.owner != player:
                        adj.notes.append(
                            f"{unit.unit_id}: destination occupied by enemy, holds"
                        )
                        continue
                    old = unit.position
                    unit.position = order.destination
                    adj.movements.append(
                        {"unit": unit.unit_id, "from": old, "to": unit.position}
                    )

        # 3. Spotting: each living unit spots enemies within range.
        #    Scouts see one square further this turn.
        scout_bonus: Set[str] = set()
        for player_orders in orders.values():
            for o in player_orders:
                if o.kind == OrderKind.SCOUT:
                    scout_bonus.add(o.unit_id)
        for viewer in self.map.units.values():
            if not viewer.alive:
                continue
            rng = viewer.spotting_range + (1 if viewer.unit_id in scout_bonus else 0)
            for target in self.map.units.values():
                if not target.alive or target.owner == viewer.owner:
                    continue
                if viewer.distance_to(target.position) <= rng:
                    self._spotted[(viewer.owner, target.unit_id)] = self.turn
                    adj.spots.append(
                        {
                            "viewer": viewer.owner,
                            "unit": target.unit_id,
                            "at": target.position,
                        }
                    )

        # 4. Combat: adjacent enemies fight; dice against the strength table.
        fought: Set[Tuple[str, str]] = set()
        for a in list(self.map.units.values()):
            if not a.alive:
                continue
            for d in list(self.map.units.values()):
                if not d.alive or d.owner == a.owner:
                    continue
                pair = tuple(sorted((a.unit_id, d.unit_id)))
                if pair in fought or a.distance_to(d.position) != 1:
                    continue
                fought.add(pair)
                adj.combats.append(self._resolve_combat(a, d))

        self.history.append(adj)
        return adj

    def _resolve_combat(self, attacker: Unit, defender: Unit) -> Dict[str, object]:
        key = (min(attacker.strength, 3), min(defender.strength, 3))
        win_on = COMBAT_TABLE.get(key, 3)
        roll = self.rng.randint(1, 6)
        if roll >= win_on:
            defender.strength -= 1
            if defender.strength <= 0:
                defender.alive = False
            outcome = f"{attacker.unit_id} hits {defender.unit_id}"
        else:
            attacker.strength -= 1
            if attacker.strength <= 0:
                attacker.alive = False
            outcome = f"{defender.unit_id} repels {attacker.unit_id}"
        return {
            "attacker": attacker.unit_id,
            "defender": defender.unit_id,
            "roll": roll,
            "needed": win_on,
            "outcome": outcome,
        }

    # -- double-blind views -------------------------------------------------

    def view_for(self, player: str) -> Dict[str, object]:
        """What one player may see: own units + spotted enemies only."""
        own = [u for u in self.map.units.values() if u.owner == player and u.alive]
        seen: List[Dict[str, object]] = []
        for (viewer, unit_id), last_seen in self._spotted.items():
            if viewer != player:
                continue
            unit = self.map.units.get(unit_id)
            if unit is None or not unit.alive:
                continue
            seen.append(
                {
                    "unit_id": unit_id,
                    "strength": unit.strength,
                    # last *known* position is honest; the umpire knows it moved
                    "last_seen_at": last_seen,
                    "stale": last_seen < self.turn,
                }
            )
        return {
            "player": player,
            "turn": self.turn,
            "own_units": [
                {"unit_id": u.unit_id, "strength": u.strength, "position": u.position}
                for u in own
            ],
            "spotted_enemies": seen,
        }

    def winner(self) -> Optional[str]:
        alive_by_owner: Dict[str, int] = {}
        for u in self.map.units.values():
            if u.alive:
                alive_by_owner[u.owner] = alive_by_owner.get(u.owner, 0) + 1
        owners = list(alive_by_owner)
        return owners[0] if len(owners) == 1 else None


def demo() -> Dict[str, object]:
    game_map = Map(6, 6)
    game_map.add_unit(Unit("red-1", "red", 3, (0, 0)))
    game_map.add_unit(Unit("red-2", "red", 2, (0, 5)))
    game_map.add_unit(Unit("blue-1", "blue", 3, (5, 0)))
    game_map.add_unit(Unit("blue-2", "blue", 2, (5, 5)))
    umpire = Umpire(game_map, seed=7)
    adj = umpire.resolve_turn(
        {
            "red": [
                Order("red-1", OrderKind.MOVE, (1, 0)),
                Order("red-2", OrderKind.SCOUT, (1, 5)),
            ],
            "blue": [
                Order("blue-1", OrderKind.MOVE, (4, 0)),
                Order("blue-2", OrderKind.HOLD),
            ],
        }
    )
    red_view = umpire.view_for("red")
    blue_view = umpire.view_for("blue")

    # Fog check: does either view leak the other's true positions?
    def leaks(view: Dict[str, object], enemy: str) -> bool:
        true = {
            u.unit_id: u.position
            for u in game_map.units.values()
            if u.owner == enemy and u.alive
        }
        for s in view["spotted_enemies"]:
            if "position" in s and s["unit_id"] in true:
                return True
        return False

    return {
        "turn": adj.turn,
        "movements": len(adj.movements),
        "red_sees_positions": leaks(red_view, "blue"),
        "blue_sees_positions": leaks(blue_view, "red"),
        "red_own": len(red_view["own_units"]),
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
