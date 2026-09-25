"""Geared cycles — astronomical prediction as a train of gear ratios.

Studied from: wave6-inbox, report.md [Honest Gaps — named but cut] —
Antikythera mechanism. Care note honored: this keeps the geared-cycle
prediction *shape* only — a ratio machine that turns input rotations
into cycle-phase readouts. No claim of reconstructing any artifact,
and no implication of an ancient gear industry; an honest one-off
survival is not evidence of one.

The mechanism, functionally: a stack of toothed wheels where each
meshing multiplies rotation by a ratio ``-driven_teeth / driver_teeth``
(the sign flips each mesh). Dial pointers ride on wheel arbors; one
input crank turn advances every pointer by the compounded ratio of
its train. Feed the train the right ratios and the pointers track
astronomical cycles: a lunar-phase wheel turning once per synodic
month against a node wheel turning once per draconic month reads an
eclipse *possibility* whenever both pointers sit near zero together
(the Babylonian arithmetic-cycle trick, mechanized).

Key operations: ``Gear`` (name + teeth); ``GearTrain.drive`` meshes
wheels in order and reports each arbor's turns; ``CycleDial`` binds a
train to a named cycle (period in input turns, phase offset) and
``phase()``/``at_zero()`` read it; ``EclipseWindow`` watches a
month-wheel and a node-wheel and reports when both align — the eclipse
prediction readout.

Honesty: pure ratio arithmetic, not a replica of anything. Eclipse
readouts are *possibility windows* from phase coincidence — a coarse
heuristic that ignores parallax, latitude, and real ephemeris math,
and says so. Tooth counts are illustrative, chosen to encode the
cycle ratios, not copied from any source.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

ORIGIN = "levi-revival/geared-cycles"


class GearError(Exception):
    """Bad gear: zero teeth, empty train, unknown wheel."""


class Gear:
    """A toothed wheel. Teeth must be a positive integer."""

    def __init__(self, name: str, teeth: int):
        if teeth <= 0:
            raise GearError("a gear needs a positive tooth count")
        self.name = name
        self.teeth = teeth

    def __repr__(self) -> str:  # pragma: no cover - display helper
        return f"Gear({self.name!r}, {self.teeth}t)"


class GearTrain:
    """A meshed sequence of gears driven by one input crank.

    ``gears[i]`` meshes with ``gears[i+1]``; each mesh multiplies the
    turn count by ``-teeth[i] / teeth[i+1]`` (sign flips per mesh).
    """

    def __init__(self, gears: List[Gear]):
        if len(gears) < 2:
            raise GearError("a train needs at least two meshing gears")
        self.gears = list(gears)

    def ratios(self) -> List[float]:
        """Turns of each arbor per one input-crank turn."""
        out = [1.0]
        acc = 1.0
        for a, b in zip(self.gears, self.gears[1:], strict=False):
            acc *= -a.teeth / b.teeth
            out.append(acc)
        return out

    def drive(self, input_turns: float) -> Dict[str, float]:
        """Crank the input; return each arbor's signed turn count."""
        return {
            g.name: input_turns * r
            for g, r in zip(self.gears, self.ratios(), strict=True)
        }


class CycleDial:
    """A pointer tracking one astronomical cycle off a gear train.

    ``period_input_turns``: how many crank turns make one full cycle
    (e.g. crank = days, period = 29.53 for the synodic month).
    ``arbor`` names the wheel the pointer rides on, ``arbor_ratio``
    its turns-per-crank-turn (from ``GearTrain.ratios``).
    """

    def __init__(
        self,
        name: str,
        period_input_turns: float,
        arbor: str,
        arbor_ratio: float,
        phase0: float = 0.0,
    ):
        if period_input_turns <= 0:
            raise GearError("cycle period must be positive")
        if arbor_ratio == 0:
            raise GearError("arbor ratio must be non-zero")
        self.name = name
        self.period = period_input_turns
        self.arbor = arbor
        self.arbor_ratio = arbor_ratio
        self.phase0 = phase0 % 1.0
        self.crank_turns = 0.0

    def advance(self, crank_turns: float) -> "CycleDial":
        self.crank_turns += crank_turns
        return self

    def phase(self) -> float:
        """Cycle phase in [0, 1) — 0 is the cycle's zero point."""
        turns = self.crank_turns * self.arbor_ratio
        return (self.phase0 + turns / self.period) % 1.0

    def angle_deg(self) -> float:
        """Pointer angle on the dial face."""
        return self.phase() * 360.0

    def near_zero(self, tolerance: float = 0.02) -> bool:
        """Is the pointer within ``tolerance`` of the zero mark?"""
        p = self.phase()
        return min(p, 1.0 - p) <= tolerance


class EclipseWindow:
    """Eclipse *possibility* from phase coincidence of two dials.

    The heuristic: an eclipse can only occur near new/full moon (the
    month dial at zero) while the moon is also near a node (the node
    dial at zero). Both near zero together => the window is open.
    Coarse by design — no parallax, no latitude, no ephemeris.
    """

    def __init__(
        self, month_dial: CycleDial, node_dial: CycleDial, tolerance: float = 0.03
    ):
        if not 0.0 < tolerance < 0.25:
            raise GearError("tolerance must be in (0, 0.25)")
        self.month = month_dial
        self.node = node_dial
        self.tolerance = tolerance

    def open(self) -> bool:
        """Is an eclipse possible at the current crank position?"""
        return self.month.near_zero(self.tolerance) and self.node.near_zero(
            self.tolerance
        )

    def next_open(self, step: float = 1.0, limit: float = 10000.0) -> float | None:
        """Crank turns until the next open window (or None past limit).

        Advances copies, never the live dials — the mechanism is read,
        not disturbed, by prediction.
        """
        if step <= 0:
            raise GearError("step must be positive")
        m = CycleDial(
            self.month.name,
            self.month.period,
            self.month.arbor,
            self.month.arbor_ratio,
            self.month.phase0,
        )
        n = CycleDial(
            self.node.name,
            self.node.period,
            self.node.arbor,
            self.node.arbor_ratio,
            self.node.phase0,
        )
        m.crank_turns, n.crank_turns = (self.month.crank_turns, self.node.crank_turns)
        t = 0.0
        while t <= limit:
            if m.near_zero(self.tolerance) and n.near_zero(self.tolerance):
                return t
            m.advance(step)
            n.advance(step)
            t += step
        return None


def demo() -> Tuple[float, bool]:
    """Illustrative train: crank = days; wheels encode the cycle ratios.

    60:1772 meshes the month wheel once per ~29.53 crank turns and
    60:1633 meshes the node wheel once per ~27.22 — the teeth ARE the
    program. Tooth counts are illustrative approximations of the true
    synodic (29.5306d) and draconic (27.2122d) month ratios, and the
    module says so; they are not copied from any source.
    """
    gears = [Gear("crank", 60), Gear("month_wheel", 1772), Gear("node_wheel", 1633)]
    train = GearTrain(gears)
    ratios = train.ratios()
    r = {g.name: rt for g, rt in zip(gears, ratios, strict=True)}
    # One pointer revolution per cycle: period = 1 in arbor turns.
    month = CycleDial("synodic_month", 1.0, "month_wheel", r["month_wheel"])
    node = CycleDial("draconic_month", 1.0, "node_wheel", r["node_wheel"])
    window = EclipseWindow(month, node)
    nxt = window.next_open(step=0.5)
    return (nxt if nxt is not None else -1.0), window.open()
