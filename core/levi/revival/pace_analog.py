"""EAI PACE/TR-style real-time analog simulation: function generators.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #10, USEFUL PATTERN] — real-time simulation before digital
could; diode function generators as manufactured modules.

Two ideas carry the module:

1. **Diode function generator (DFG).** An arbitrary single-variable
   nonlinearity ``f(x)`` is manufactured as a breakpoint card:
   ``[(x0, y0), (x1, y1), ...]`` with straight-line segments between
   breakpoints — the diode network's piecewise-linear shape, modeled
   directly. Outside the card's range the output saturates and the
   module says so (``saturated`` flag), because a real DFG clips.
2. **Real-time rack.** Simulation runs at ``time_scale = 1``: machine
   time *is* problem time, so the model keeps pace with the world it
   mimics. ``repetitive`` mode re-runs the same interval for tuning.

``fit_breakpoints`` builds a card from a callable by sampling it
(heuristic fit — the docstring says so; breakpoint placement is
uniform, not optimal). The rack itself is a small integrator network
with DFG cards plugged in as nonlinear blocks; ``module_report``
lists the manufactured inventory like a catalog page.

Honest limits: uniform breakpoints waste segments on flat regions;
saturation outside the card is a hard clip, flagged, not extrapolated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


ORIGIN = "levi-revival/pace-analog"


@dataclass
class DiodeFunctionGenerator:
    """A manufactured nonlinearity: piecewise-linear card of breakpoints."""

    name: str
    breakpoints: List[Tuple[float, float]] = field(default_factory=list)
    saturated: bool = False

    def __post_init__(self) -> None:
        if len(self.breakpoints) < 2:
            raise ValueError("a DFG card needs at least 2 breakpoints")
        xs = [x for x, _ in self.breakpoints]
        if any(b <= a for a, b in zip(xs, xs[1:], strict=False)):
            raise ValueError("breakpoint x values must be strictly increasing")

    @property
    def x_min(self) -> float:
        return self.breakpoints[0][0]

    @property
    def x_max(self) -> float:
        return self.breakpoints[-1][0]

    def evaluate(self, x: float) -> float:
        """Read the card at ``x``; clips and flags saturation outside."""
        self.saturated = False
        pts = self.breakpoints
        if x <= pts[0][0]:
            self.saturated = x < pts[0][0]
            return pts[0][1]
        if x >= pts[-1][0]:
            self.saturated = x > pts[-1][0]
            return pts[-1][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
            if x0 <= x <= x1:
                frac = (x - x0) / (x1 - x0)
                return y0 + frac * (y1 - y0)
        return pts[-1][1]  # unreachable; kept total

    def segments(self) -> int:
        return len(self.breakpoints) - 1


def fit_breakpoints(
    func: Callable[[float], float],
    x_min: float,
    x_max: float,
    n_segments: int,
    name: str = "dfg",
) -> DiodeFunctionGenerator:
    """Manufacture a DFG card by sampling ``func`` at uniform breakpoints.

    Heuristic fit: uniform spacing is simple and predictable, not
    optimal — sharp knees between breakpoints are under-resolved, and
    the card's ``segments()`` count tells you exactly what you paid.
    """
    if x_max <= x_min:
        raise ValueError("x_max must exceed x_min")
    if n_segments < 1:
        raise ValueError("need at least 1 segment")
    pts = []
    for i in range(n_segments + 1):
        x = x_min + (x_max - x_min) * i / n_segments
        pts.append((x, func(x)))
    return DiodeFunctionGenerator(name=name, breakpoints=pts)


class RealtimeRack:
    """A small real-time rack: integrators plus plugged-in DFG cards.

    State vector ``y`` evolves by ``dy/dt = rhs(t, y)`` where ``rhs``
    may call DFG cards. ``time_scale = 1`` means real time; larger
    values run the machine faster than the problem.
    """

    def __init__(self, time_scale: float = 1.0) -> None:
        if time_scale <= 0:
            raise ValueError("time_scale must be positive")
        self.time_scale = time_scale
        self.dfgs: Dict[str, DiodeFunctionGenerator] = {}
        self.op_amp_count = 0

    def plug_dfg(self, dfg: DiodeFunctionGenerator) -> None:
        if dfg.name in self.dfgs:
            raise ValueError(f"DFG slot {dfg.name!r} already occupied")
        self.dfgs[dfg.name] = dfg

    def add_op_amps(self, count: int) -> None:
        if count < 0:
            raise ValueError("count cannot be negative")
        self.op_amp_count += count

    def simulate(
        self,
        rhs: Callable[[float, List[float]], List[float]],
        y0: List[float],
        t_end: float,
        dt: float,
        repetitive: int = 1,
    ) -> List[Tuple[float, List[float]]]:
        """Run the problem. Returns ``[(t, y), ...]``; ``repetitive``
        re-runs the interval that many times (for tuning)."""
        if t_end <= 0 or dt <= 0:
            raise ValueError("t_end and dt must be positive")
        if repetitive < 1:
            raise ValueError("repetitive must be >= 1")
        machine_dt = dt / self.time_scale
        runs: List[Tuple[float, List[float]]] = []
        for _ in range(repetitive):
            y = list(y0)
            t = 0.0
            trace = [(t, list(y))]
            while t < t_end - 1e-12:
                step = min(machine_dt, (t_end - t) / self.time_scale)
                dydt = rhs(t, y)
                if len(dydt) != len(y):
                    raise ValueError("rhs returned wrong state dimension")
                y = [
                    yi + d * step * self.time_scale
                    for yi, d in zip(y, dydt, strict=True)
                ]
                t += step * self.time_scale
                trace.append((t, list(y)))
            runs.extend(trace)
        return runs

    def module_report(self) -> Dict[str, object]:
        """Catalog page: what is plugged into this rack."""
        return {
            "op_amps": self.op_amp_count,
            "time_scale": self.time_scale,
            "realtime": self.time_scale == 1.0,
            "dfg_cards": {
                name: {"segments": dfg.segments(), "range": [dfg.x_min, dfg.x_max]}
                for name, dfg in self.dfgs.items()
            },
        }


def pendulum_rhs(
    length: float, gravity: float = 9.80665, dfg: DiodeFunctionGenerator | None = None
) -> Callable[[float, List[float]], List[float]]:
    """Pendulum ``theta'' = -(g/L) sin(theta)`` with the sine supplied
    by a DFG card when given (the manufactured-nonlinearity way), or
    ``math.sin`` when not (the honest-numerics way)."""

    def rhs(t: float, y: List[float]) -> List[float]:
        theta, omega = y
        s = dfg.evaluate(theta) if dfg else math.sin(theta)
        return [omega, -(gravity / length) * s]

    return rhs
