"""Bush–Hazen-style differential analyzer: ODEs by chained integrators.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #7, LOAD-BEARING] — the torque amplifier (capstan servo) made
integrators chainable; programming by shaft re-routing.

The machine is a set of mechanical integrator units. One unit enforces
``dZ = Y dX``: its output shaft ``Z`` advances by the integrand shaft
``Y`` times the advance of the independent-variable shaft ``X``. The
torque amplifier (capstan servo) lets one shaft drive many followers
without loading the source — in software that is trivially true, and
the module says so: here the amplifier is a fan-out discipline, not a
feat. Programming is literally re-routing: wire an integrator's output
shaft back into another unit's input and you have posed a differential
equation; re-route and you have posed a different one.

Wiring conventions:

* the ``x`` shaft of every unit carries the *increment* ``dx`` per step
  (the machine turns the independent shaft by ``dx`` each cycle);
* an ``Inverter`` gear reverses a shaft's sign;
* an ``Adder`` sums shafts into one;
* a ``TorqueAmplifier`` fans one shaft out to many followers.

Honest limits: fixed-step explicit integration; error accumulates like
any Euler scheme, and the module reports drift on known solutions
rather than claiming mechanical exactness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/diff-analyzer"


@dataclass
class Shaft:
    """A rotating shaft carrying one value."""

    name: str
    value: float = 0.0


class IntegratorUnit:
    """Mechanical integrator: ``dZ = Y dX`` per machine cycle."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.z = Shaft(f"{name}.z")  # output shaft
        self.y: Shaft | None = None  # integrand shaft (wired)
        self.x: Shaft | None = None  # independent-variable shaft (wired)

    def wire(self, y: Shaft, x: Shaft) -> "IntegratorUnit":
        self.y = y
        self.x = x
        return self

    def step(self) -> None:
        if self.y is None or self.x is None:
            raise RuntimeError(f"integrator {self.name} is not fully wired")
        self.z.value += self.y.value * self.x.value


class Inverter:
    """Sign-reversing gear pair: follower shaft is the negative of source."""

    def __init__(self, name: str) -> None:
        self.out = Shaft(f"{name}.out")
        self.source: Shaft | None = None

    def wire(self, source: Shaft) -> "Inverter":
        self.source = source
        return self

    def sync(self) -> None:
        if self.source is None:
            raise RuntimeError("inverter not wired")
        self.out.value = -self.source.value


class Adder:
    """Summing gearbox: follower shaft is the sum of its inputs."""

    def __init__(self, name: str) -> None:
        self.out = Shaft(f"{name}.out")
        self.inputs: List[Shaft] = []

    def wire(self, *shafts: Shaft) -> "Adder":
        self.inputs.extend(shafts)
        return self

    def sync(self) -> None:
        if not self.inputs:
            raise RuntimeError("adder has no inputs wired")
        self.out.value = sum(s.value for s in self.inputs)


class TorqueAmplifier:
    """Capstan servo: one shaft drives many followers without loading it.

    In the physical machine this was the hard-won breakthrough; in this
    emulation fan-out is free, and the class exists to keep the wiring
    diagram honest — every consumer of a shaft is an explicit follower.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.source: Shaft | None = None
        self.followers: List[Shaft] = []

    def drive(self, source: Shaft, count: int) -> List[Shaft]:
        """Wire ``source`` through the amplifier to ``count`` followers."""
        if count < 1:
            raise ValueError("need at least one follower")
        self.source = source
        self.followers = [Shaft(f"{self.name}.f{i}") for i in range(count)]
        self.sync()
        return self.followers

    def sync(self) -> None:
        if self.source is None:
            raise RuntimeError("torque amplifier has no source")
        for follower in self.followers:
            follower.value = self.source.value


class DifferentialAnalyzer:
    """The machine: units, wiring, and the crank that turns them."""

    def __init__(self) -> None:
        self.integrators: List[IntegratorUnit] = []
        self.gears: List[object] = []  # Inverter / Adder / TorqueAmplifier
        self.dx = Shaft("dx", 0.0)

    def add_integrator(self, name: str) -> IntegratorUnit:
        unit = IntegratorUnit(name)
        self.integrators.append(unit)
        return unit

    def add_gear(self, gear: object) -> object:
        self.gears.append(gear)
        return gear

    def set_dx(self, dx: float) -> None:
        if dx <= 0:
            raise ValueError("dx must be positive")
        self.dx.value = dx

    def cycle(self) -> None:
        """One machine cycle: sync gears, then advance every integrator."""
        for gear in self.gears:
            sync = getattr(gear, "sync", None)
            if sync is not None:
                sync()
        for unit in self.integrators:
            unit.step()
        # Followers track their sources after the crank turns.
        for gear in self.gears:
            sync = getattr(gear, "sync", None)
            if sync is not None:
                sync()

    def run(self, cycles: int) -> None:
        if cycles < 1:
            raise ValueError("cycles must be positive")
        for _ in range(cycles):
            self.cycle()

    def wiring_diagram(self) -> Dict[str, str]:
        """Human-readable routing of the current program."""
        diagram: Dict[str, str] = {}
        for unit in self.integrators:
            y = unit.y.name if unit.y else "?"
            x = unit.x.name if unit.x else "?"
            diagram[unit.name] = f"d({unit.z.name}) = {y} d({x})"
        return diagram


def solve_decay(y0: float, rate: float, dx: float, cycles: int) -> List[float]:
    """Program ``dy/dx = -rate * y``: one integrator, output fed back
    through an inverter and a gain shaft. Returns the traced ``y``."""
    machine = DifferentialAnalyzer()
    machine.set_dx(dx)
    gain = Shaft("gain", rate)
    product = Shaft("rate*y")
    inv = machine.add_gear(Inverter("neg"))
    integ = machine.add_integrator("I1")
    integ.z.value = y0
    inv.wire(integ.z)
    integ.wire(y=product, x=machine.dx)

    trace = [y0]
    for _ in range(cycles):
        product.value = gain.value * inv.out.value
        machine.cycle()
        trace.append(integ.z.value)
    return trace


def solve_harmonic(
    x0: float, v0: float, omega: float, dx: float, cycles: int
) -> List[float]:
    """Program ``d2x/dt2 = -omega^2 x`` with two chained integrators:
    ``dx/dt = v``, ``dv/dt = -omega^2 x``. Returns the traced ``x``."""
    machine = DifferentialAnalyzer()
    machine.set_dx(dx)
    w2 = Shaft("omega2", omega * omega)
    neg_x = machine.add_gear(Inverter("negx"))
    neg_w2x = Shaft("accel")
    pos = machine.add_integrator("pos")  # dz = v dt
    vel = machine.add_integrator("vel")  # dz = a dt
    pos.z.value = x0
    vel.z.value = v0
    neg_x.wire(pos.z)
    pos.wire(y=vel.z, x=machine.dx)
    vel.wire(y=neg_w2x, x=machine.dx)

    trace = [x0]
    for _ in range(cycles):
        neg_w2x.value = w2.value * neg_x.out.value
        machine.cycle()
        trace.append(pos.z.value)
    return trace
