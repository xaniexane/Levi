"""REAC-style electronic analog computer: op-amps plus a patch panel.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #9, USEFUL PATTERN] — first commercial electronic analog
computer: op-amps + patch panel made ODE-solving a product.

The machine is a rack of computing modules behind a patch bay:

* ``Pot`` — coefficient potentiometer, scales a signal by 0..1;
* ``Summer`` — inverting weighted summer;
* ``Inverter`` — sign change;
* ``Integrator`` — ``d(out)/dt = -(sum w_i v_i)`` with an initial
  condition loaded on RESET;
* ``Multiplier`` — scaled product ``(x*y)/Vref``;
* ``PatchPanel`` — named jacks; a patch cord routes one module's
  output to another's input.

Operating discipline is the product: RESET (load initial conditions),
OPERATE (integrate in machine time), HOLD (freeze). Machine time runs
faster or slower than problem time by ``time_scale``. Any node driven
past ``±Vref`` raises ``overload`` and freezes the run — the machine
refuses to lie quietly.

Honest limits: combinational settling is done by relaxation iteration
(a numerical stand-in for parallel electronics); integration is
explicit Euler at the machine step. Overload detection is the honest
part: out-of-range answers are flagged, not silently clipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/reac-analog"

VREF = 100.0  # reference volts: the machine's full-scale range


@dataclass
class Jack:
    name: str
    value: float = 0.0


class Module:
    """Base computing module with named input jacks and one output."""

    def __init__(self, name: str, inputs: List[str]) -> None:
        self.name = name
        self.jacks: Dict[str, Jack] = {j: Jack(f"{name}.{j}") for j in inputs}
        self.output = Jack(f"{name}.out")

    def compute(self) -> None:
        raise NotImplementedError("subclass implements the transfer")

    def is_integrator(self) -> bool:
        return False


class Pot(Module):
    """Coefficient potentiometer: out = ratio * in, ratio in [0, 1]."""

    def __init__(self, name: str, ratio: float) -> None:
        if not 0.0 <= ratio <= 1.0:
            raise ValueError("pot ratio must be in [0, 1]")
        super().__init__(name, ["in"])
        self.ratio = ratio

    def compute(self) -> None:
        self.output.value = self.ratio * self.jacks["in"].value


class Summer(Module):
    """Inverting summer: out = -(w1*v1 + w2*v2 + ...)."""

    def __init__(self, name: str, weights: List[float]) -> None:
        super().__init__(name, [f"in{i}" for i in range(len(weights))])
        if not weights:
            raise ValueError("summer needs at least one input")
        self.weights = list(weights)

    def compute(self) -> None:
        total = sum(w * self.jacks[f"in{i}"].value for i, w in enumerate(self.weights))
        self.output.value = -total


class Inverter(Module):
    """Sign inverter: out = -in."""

    def __init__(self, name: str) -> None:
        super().__init__(name, ["in"])

    def compute(self) -> None:
        self.output.value = -self.jacks["in"].value


class Integrator(Module):
    """Integrator: d(out)/dt = -(sum w_i v_i); IC loaded on RESET."""

    def __init__(self, name: str, weights: List[float], initial: float = 0.0) -> None:
        super().__init__(name, [f"in{i}" for i in range(len(weights))])
        if not weights:
            raise ValueError("integrator needs at least one input")
        self.weights = list(weights)
        self.initial = initial

    def is_integrator(self) -> bool:
        return True

    def reset(self) -> None:
        self.output.value = self.initial

    def compute(self) -> None:
        pass  # integrators advance in Rack.operate, not in settle

    def input_sum(self) -> float:
        return sum(w * self.jacks[f"in{i}"].value for i, w in enumerate(self.weights))


class Multiplier(Module):
    """Scaled product: out = (x * y) / Vref. Keeps full-scale products
    inside the ±Vref range by construction."""

    def __init__(self, name: str) -> None:
        super().__init__(name, ["x", "y"])

    def compute(self) -> None:
        self.output.value = self.jacks["x"].value * self.jacks["y"].value / VREF


class PatchPanel:
    """The patch bay: cords route module outputs to module input jacks."""

    def __init__(self) -> None:
        self.cords: List[Tuple[Jack, Jack]] = []

    def patch(self, source: Jack, dest: Jack) -> None:
        self.cords.append((source, dest))

    def propagate(self) -> None:
        for source, dest in self.cords:
            dest.value = source.value

    def diagram(self) -> List[str]:
        return [f"{s.name} -> {d.name}" for s, d in self.cords]


class Rack:
    """The REAC-style rack: modules, patch panel, operating modes."""

    def __init__(self, vref: float = VREF, time_scale: float = 1.0) -> None:
        if vref <= 0:
            raise ValueError("vref must be positive")
        if time_scale <= 0:
            raise ValueError("time_scale must be positive")
        self.vref = vref
        self.time_scale = time_scale  # machine seconds per problem second
        self.modules: Dict[str, Module] = {}
        self.panel = PatchPanel()
        self.mode = "RESET"
        self.overload: List[str] = []

    def add(self, module: Module) -> Module:
        if module.name in self.modules:
            raise ValueError(f"duplicate module name: {module.name}")
        self.modules[module.name] = module
        return module

    def reset(self) -> None:
        """RESET: load initial conditions, clear overload flags."""
        self.mode = "RESET"
        self.overload = []
        for module in self.modules.values():
            if isinstance(module, Integrator):
                module.reset()
        self._settle()

    def hold(self) -> None:
        self.mode = "HOLD"

    def operate(self, problem_dt: float, steps: int) -> List[Dict[str, float]]:
        """OPERATE: integrate. ``problem_dt`` is in problem seconds;
        the machine steps ``problem_dt * time_scale`` internally."""
        if problem_dt <= 0 or steps < 1:
            raise ValueError("need positive dt and at least one step")
        self.mode = "OPERATE"
        machine_dt = problem_dt * self.time_scale
        trace: List[Dict[str, float]] = []
        for _ in range(steps):
            if self.mode != "OPERATE":
                break
            self._settle()
            for module in self.modules.values():
                if isinstance(module, Integrator):
                    module.output.value += -module.input_sum() * machine_dt
            self._check_overload()
            if self.overload:
                self.mode = "HOLD"  # freeze on overload; refuse to lie
                break
            trace.append({n: m.output.value for n, m in self.modules.items()})
        return trace

    def _settle(self, rounds: int = 25, tol: float = 1e-9) -> None:
        """Relax the combinational network (numerical stand-in for the
        parallel electronics settling). Integrators hold their state."""
        combs = [m for m in self.modules.values() if not m.is_integrator()]
        for _ in range(rounds):
            before = [m.output.value for m in combs]
            for module in combs:
                module.compute()
            self.panel.propagate()
            for module in combs:
                module.compute()
            after = [m.output.value for m in combs]
            if max(abs(a - b) for a, b in zip(after, before, strict=True)) < tol:
                break

    def _check_overload(self) -> None:
        self.overload = [
            f"{m.name}.out"
            for m in self.modules.values()
            if abs(m.output.value) > self.vref
        ]


def spring_mass_damper(
    mass: float, damping: float, stiffness: float, x0: float, v0: float
) -> Rack:
    """Patch ``m x'' + c x' + k x = 0`` with scaled coefficients.

    Uses two integrators: ``X = int_x.out`` tracks ``x`` and
    ``V = int_v.out`` tracks ``-v``. Then ``dX/dt = -V`` needs no sign
    work, and ``dV/dt = -a`` with ``a = -(c/m)v - (k/m)x`` is formed by
    a summer whose stiffness input passes through one inverter and
    whose output passes through another — sign changes go through
    inverters, the machine-honest way.
    Coefficients are entered as fractions of full scale (the
    operator's scaling job, done here by the caller choosing sane
    numbers).
    """
    rack = Rack()
    int_v = rack.add(Integrator("int_v", [1.0], initial=-v0))
    int_x = rack.add(Integrator("int_x", [1.0], initial=x0))
    invx = rack.add(Inverter("invx"))
    nega = rack.add(Inverter("nega"))
    acc = rack.add(Summer("acc", [damping / mass, stiffness / mass]))
    rack.panel.patch(int_x.output, invx.jacks["in"])
    rack.panel.patch(acc.output, nega.jacks["in"])
    rack.panel.patch(int_v.output, acc.jacks["in0"])
    rack.panel.patch(invx.output, acc.jacks["in1"])
    rack.panel.patch(nega.output, int_v.jacks["in0"])
    rack.panel.patch(int_v.output, int_x.jacks["in0"])
    return rack
