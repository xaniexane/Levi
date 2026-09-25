"""MONIAC-style hydraulic economy: money as water in tanks.

Studied from: precompute-hunt-20260915 report.md [Find 3, USEFUL PATTERN]
(functional shape only: tanks as sectors, valves/floats auto-controlling
flows so stability, lag, and feedback are visible).

A circuit of tanks (economic sectors) joined by pipes (spending
channels). Water level = money stock. A pipe's flow runs downhill from
the fuller tank to the emptier one, throttled by its valve opening.
Float valves watch a tank's level and open or close a pipe to hold the
level near a target — the feedback that makes booms and busts visible
as sloshing.

This is a heuristic discrete-time hydraulic analogy, not an economic
model: flows are linear in level difference, tanks have hard capacity
(overflow is spilled and lost, honestly counted), and float valves are
simple proportional controllers with a stated gain. Nothing here
predicts real economies.

stdlib-only, local-first, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/moniac_flow"


@dataclass
class Tank:
    """A sector: holds a stock of water (money) up to a capacity."""

    name: str
    capacity: float
    level: float = 0.0
    spilled: float = 0.0  # cumulative overflow lost, honestly counted

    def add(self, amount: float) -> None:
        self.level += amount
        if self.level > self.capacity:
            self.spilled += self.level - self.capacity
            self.level = self.capacity
        if self.level < 0.0:
            self.level = 0.0


@dataclass
class Pipe:
    """A spending channel between two tanks.

    Flow is proportional to the source-minus-destination level gap,
    throttled by ``opening`` in [0, 1]. Sign follows the gap, so flow
    reverses if the destination runs fuller than the source.
    """

    name: str
    src: str
    dst: str
    conductance: float
    opening: float = 1.0

    def flow(self, levels: Dict[str, float]) -> float:
        gap = levels[self.src] - levels[self.dst]
        return self.conductance * max(0.0, min(1.0, self.opening)) * gap


@dataclass
class FloatValve:
    """Feedback: holds ``tank`` near ``target`` by driving ``pipe``.

    Each step the opening moves toward ``clamp(gain * (level - target))``
    — the valve opens wider when the tank runs hot, draining it faster.
    ``smoothing`` in [0, 1] models the float's mechanical lag: 1.0 means
    the valve snaps to the commanded opening, lower values lag.
    """

    tank: str
    pipe: str
    target: float
    gain: float = 0.1
    smoothing: float = 1.0


@dataclass
class Step:
    """One simulated tick: per-pipe flows and post-step levels."""

    index: int
    flows: Dict[str, float]
    levels: Dict[str, float]


class Circuit:
    """A hydraulic economy: tanks, pipes, float-valve feedback, sources."""

    def __init__(self) -> None:
        self.tanks: Dict[str, Tank] = {}
        self.pipes: Dict[str, Pipe] = {}
        self.valves: List[FloatValve] = []
        self.sources: Dict[str, float] = {}  # tank -> inflow per step
        self.sinks: Dict[str, float] = {}  # tank -> outflow per step
        self.history: List[Step] = []

    def add_tank(self, name: str, capacity: float, level: float = 0.0) -> Tank:
        tank = Tank(name=name, capacity=capacity, level=level)
        self.tanks[name] = tank
        return tank

    def add_pipe(
        self, name: str, src: str, dst: str, conductance: float, opening: float = 1.0
    ) -> Pipe:
        if src not in self.tanks or dst not in self.tanks:
            raise KeyError("pipe endpoints must be existing tanks")
        pipe = Pipe(
            name=name, src=src, dst=dst, conductance=conductance, opening=opening
        )
        self.pipes[name] = pipe
        return pipe

    def add_float_valve(
        self,
        tank: str,
        pipe: str,
        target: float,
        gain: float = 0.1,
        smoothing: float = 1.0,
    ) -> FloatValve:
        if tank not in self.tanks or pipe not in self.pipes:
            raise KeyError("valve needs an existing tank and pipe")
        valve = FloatValve(
            tank=tank, pipe=pipe, target=target, gain=gain, smoothing=smoothing
        )
        self.valves.append(valve)
        return valve

    def add_source(self, tank: str, rate: float) -> None:
        """Constant inflow (e.g. government spending) into ``tank``."""
        if tank not in self.tanks:
            raise KeyError(f"no tank {tank!r}")
        self.sources[tank] = self.sources.get(tank, 0.0) + rate

    def add_sink(self, tank: str, rate: float) -> None:
        """Constant outflow (e.g. taxation) out of ``tank``."""
        if tank not in self.tanks:
            raise KeyError(f"no tank {tank!r}")
        self.sinks[tank] = self.sinks.get(tank, 0.0) + rate

    def total_water(self) -> float:
        """Conserved quantity: water in tanks + cumulative spill + sinks."""
        in_tanks = sum(t.level for t in self.tanks.values())
        spilled = sum(t.spilled for t in self.tanks.values())
        return in_tanks + spilled

    def step(self, dt: float = 1.0) -> Step:
        if dt <= 0:
            raise ValueError("dt must be positive")
        levels = {name: t.level for name, t in self.tanks.items()}
        flows: Dict[str, float] = {}
        deltas: Dict[str, float] = {name: 0.0 for name in self.tanks}

        for name, pipe in self.pipes.items():
            q = pipe.flow(levels) * dt
            # A pipe cannot move more water than the source holds.
            q = max(-self.tanks[pipe.dst].level, min(q, self.tanks[pipe.src].level))
            flows[name] = q
            deltas[pipe.src] -= q
            deltas[pipe.dst] += q

        for tank, rate in self.sources.items():
            deltas[tank] += rate * dt
        for tank, rate in self.sinks.items():
            room = self.tanks[tank].level + deltas[tank]
            take = min(rate * dt, max(0.0, room))
            deltas[tank] -= take

        for name, delta in deltas.items():
            self.tanks[name].add(delta)

        # Float valves react to the new levels, with mechanical lag.
        for valve in self.valves:
            level = self.tanks[valve.tank].level
            commanded = valve.gain * (level - valve.target)
            commanded = max(0.0, min(1.0, commanded))
            pipe = self.pipes[valve.pipe]
            s = max(0.0, min(1.0, valve.smoothing))
            pipe.opening = pipe.opening + s * (commanded - pipe.opening)

        record = Step(
            index=len(self.history),
            flows=flows,
            levels={n: t.level for n, t in self.tanks.items()},
        )
        self.history.append(record)
        return record

    def run(self, steps: int, dt: float = 1.0) -> List[Step]:
        for _ in range(steps):
            self.step(dt)
        return self.history
