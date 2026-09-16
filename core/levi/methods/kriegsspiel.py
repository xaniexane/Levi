"""Kriegsspiel: adversarial decision wargame with umpire + fog-of-war.

History: the Prussian staff wargame (Reisswitz, 1824) — two teams issue
*written orders* against a map with hidden enemy information; dice and
combat tables resolve engagements; a human *umpire* adjudicates everything
the rules don't cover and controls information flow — each side sees only
what its own units could see. Later "free Kriegsspiel" dropped most tables
in favor of umpire judgment.

The mechanism: *fog plus adjudication*. Hidden information forces real
decision-making under uncertainty (no perfect-information chess thinking);
written orders force clarity of intent; the umpire supplies the world's
friction — the enemy's reactions, chance, misunderstanding. The game
trains *judgment*, not rules-mastery.

In LEVI: umpired decision rehearsal under fog. LEVI plays umpire — holding
the hidden state (competitor moves, market reactions), adjudicating your
written plans against it, and revealing only what your "units" would
observe. You practice the decision *in the fog*, then debrief against the
ground truth it held back. Dice are seeded for determinism; every turn,
every order, and every revelation is logged for the debrief.

Honesty: LOAD-BEARING — the only training method in this wave that
practices judgment rather than knowledge. The combat model here is a
deliberately simple sketch (dice + strength ratios), not a simulation
claim; the load-bearing part is the fog/umpire/debrief protocol.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class KriegsspielError(Exception):
    """Base class for wargame failures."""


class OrderRejected(KriegsspielError):
    """A written order was invalid (unknown unit, illegal move, wrong side)."""


# ---------------------------------------------------------------------------
# Board, units, orders
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    unit_id: str
    side: str  # "red" or "blue"
    x: int
    y: int
    strength: int = 3
    sight: int = 3

    def alive(self) -> bool:
        return self.strength > 0

    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Order:
    """A written order: what one unit is told to do this turn."""

    unit_id: str
    kind: str  # "move", "attack", "hold"
    dx: int = 0
    dy: int = 0
    target_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("move", "attack", "hold"):
            raise ValueError(f"unknown order kind {self.kind!r}")


@dataclass
class Observation:
    """What one side is allowed to see after a turn (fog-of-war applied)."""

    side: str
    turn: int
    own_units: list[dict] = field(default_factory=list)
    seen_enemy: list[dict] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The umpire
# ---------------------------------------------------------------------------


class Umpire:
    """Holds the hidden ground truth; adjudicates; rations information."""

    def __init__(self, width: int, height: int, seed: int = 0):
        if width < 1 or height < 1:
            raise ValueError("map dimensions must be positive")
        self.width = width
        self.height = height
        self._rng = random.Random(seed)
        self.seed = seed
        self.units: dict[str, Unit] = {}
        self.turn = 0
        self.order_log: list[dict] = []
        self.event_log: list[str] = []

    # -- setup --------------------------------------------------------------
    def add_unit(self, unit: Unit) -> Unit:
        if unit.side not in ("red", "blue"):
            raise ValueError("side must be 'red' or 'blue'")
        if unit.unit_id in self.units:
            raise ValueError(f"unit {unit.unit_id!r} already on the map")
        if not (0 <= unit.x < self.width and 0 <= unit.y < self.height):
            raise ValueError(f"unit {unit.unit_id!r} placed off-map")
        self.units[unit.unit_id] = unit
        return unit

    # -- the turn -------------------------------------------------------------
    def submit_orders(self, side: str, orders: list[Order]) -> None:
        """File written orders for a side. Invalid orders are rejected
        loudly — the umpire never silently drops an order."""
        for order in orders:
            unit = self.units.get(order.unit_id)
            if unit is None or not unit.alive():
                raise OrderRejected(f"no live unit {order.unit_id!r}")
            if unit.side != side:
                raise OrderRejected(
                    f"unit {order.unit_id!r} belongs to {unit.side}, not {side}"
                )
            if order.kind == "move":
                nx, ny = unit.x + order.dx, unit.y + order.dy
                if abs(order.dx) + abs(order.dy) != 1:
                    raise OrderRejected(
                        f"move for {order.unit_id!r}: one orthogonal step per turn"
                    )
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    raise OrderRejected(f"move for {order.unit_id!r} leaves the map")
            if order.kind == "attack":
                target = self.units.get(order.target_id)
                if target is None or not target.alive():
                    raise OrderRejected(f"attack target {order.target_id!r} invalid")
                if target.side == side:
                    raise OrderRejected("no friendly fire: target is on your side")
                if abs(unit.x - target.x) + abs(unit.y - target.y) != 1:
                    raise OrderRejected(
                        f"{order.unit_id!r} cannot reach {order.target_id!r} "
                        "(attacks are adjacent only)"
                    )
        self.order_log.append({"turn": self.turn + 1, "side": side,
                               "orders": [vars(o) for o in orders]})
        self._pending = getattr(self, "_pending", {})
        self._pending[side] = orders

    def resolve_turn(self) -> dict[str, Observation]:
        """Adjudicate both sides' orders (moves, then attacks), then ration
        observations per side. Returns ``{side: Observation}``."""
        pending: dict[str, list[Order]] = getattr(self, "_pending", {})
        if "red" not in pending or "blue" not in pending:
            raise KriegsspielError(
                "both sides must submit orders before the turn resolves"
            )
        self.turn += 1
        events: list[str] = []

        # Phase 1: moves (simultaneous).
        for side in ("red", "blue"):
            for order in pending[side]:
                unit = self.units[order.unit_id]
                if not unit.alive():
                    continue
                if order.kind == "move":
                    unit.x += order.dx
                    unit.y += order.dy
                    events.append(
                        f"turn {self.turn}: {unit.unit_id} moves to {unit.pos()}")

        # Phase 2: attacks (dice + strength ratio — the combat-table sketch).
        for side in ("red", "blue"):
            for order in pending[side]:
                unit = self.units[order.unit_id]
                target = self.units.get(order.target_id)
                if not unit.alive() or target is None or not target.alive():
                    continue
                if order.kind != "attack":
                    continue
                if abs(unit.x - target.x) + abs(unit.y - target.y) != 1:
                    events.append(
                        f"turn {self.turn}: {unit.unit_id}'s attack on "
                        f"{target.unit_id} fails — target moved out of reach")
                    continue
                atk = self._rng.randint(1, 6) + unit.strength
                dfn = self._rng.randint(1, 6) + target.strength
                if atk > dfn:
                    target.strength -= 1
                    events.append(
                        f"turn {self.turn}: {unit.unit_id} hits {target.unit_id} "
                        f"(now strength {max(target.strength, 0)})")
                    if not target.alive():
                        events.append(f"turn {self.turn}: {target.unit_id} destroyed")
                else:
                    events.append(
                        f"turn {self.turn}: {unit.unit_id}'s attack on "
                        f"{target.unit_id} is repulsed")

        self.event_log.extend(events)
        self._pending = {}
        return {side: self._observe(side, events) for side in ("red", "blue")}

    # -- fog-of-war -------------------------------------------------------------
    def _observe(self, side: str, events: list[str]) -> Observation:
        own = [u for u in self.units.values() if u.side == side and u.alive()]
        seen = []
        for enemy in (u for u in self.units.values()
                      if u.side != side and u.alive()):
            if any(abs(o.x - enemy.x) + abs(o.y - enemy.y) <= o.sight for o in own):
                seen.append({"unit_id": enemy.unit_id, "pos": enemy.pos(),
                             "strength": enemy.strength})
        visible_events = [
            e for e in events
            if any(u.unit_id in e for u in own) or "destroyed" in e
        ]
        return Observation(
            side=side, turn=self.turn,
            own_units=[{"unit_id": u.unit_id, "pos": u.pos(),
                        "strength": u.strength} for u in own],
            seen_enemy=seen, events=visible_events,
        )

    # -- debrief ------------------------------------------------------------------
    def debrief(self) -> dict:
        """Reveal the ground truth the umpire held back: every unit, every
        order, every event — the material for judging the decisions."""
        return {
            "seed": self.seed,
            "turns": self.turn,
            "ground_truth": {
                uid: {"side": u.side, "pos": u.pos(), "strength": u.strength,
                      "alive": u.alive()}
                for uid, u in sorted(self.units.items())
            },
            "order_log": self.order_log,
            "event_log": list(self.event_log),
            "outcome": self.outcome(),
        }

    def outcome(self) -> dict:
        red = sum(u.strength for u in self.units.values()
                  if u.side == "red" and u.alive())
        blue = sum(u.strength for u in self.units.values()
                   if u.side == "blue" and u.alive())
        winner = "red" if red > blue else "blue" if blue > red else None
        return {"red_strength": red, "blue_strength": blue, "winner": winner}


__all__ = [
    "KriegsspielError",
    "OrderRejected",
    "Unit",
    "Order",
    "Observation",
    "Umpire",
]
