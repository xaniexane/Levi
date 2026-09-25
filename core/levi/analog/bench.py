"""Virtual analog workbench — the patch-panel lineage, LEVI-native.

Thomson's ball-and-disc integrator (1876) turned calculus into brass;
Bush's torque amplifier (1931) made integrators *chainable*, so a
differential equation became a wiring diagram; the REAC/EAI rooms wired
those diagrams on patch panels and watched them solve themselves.

This module keeps the patch-panel way of thinking and discards the
hardware: virtual blocks (integrator, summer, gain, multiplier, sine,
const) wired by name, solved with bounded fixed-step RK4. Every run is
sealed with a machine-checked Receipt. Deny-closed: fixed step budget,
algebraic loops refused at build time, missing inputs default to 0.0
*explicitly* (never silently wired wrong).

The ``parts_list`` "Meccano view" demystifies: it shows what each virtual
block would have been in brass and bakelite, so learners see the machine
instead of worshipping it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union


class StepBudgetExceeded(Exception):
    """Raised when a run needs more fixed steps than its budget allows.

    Deny-closed: the run refuses before doing partial work, never hangs,
    never silently truncates.
    """


# ---------------------------------------------------------------------------
# Blocks — frozen dataclasses, one per patch-panel unit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gain:
    """Scale input by k (the servo-driven potentiometer)."""

    k: float


@dataclass(frozen=True)
class Summer:
    """Add weighted inputs: out = sum(signs[i] * in[i])."""

    signs: Tuple[float, ...] = field(default_factory=lambda: (1.0,))

    def __post_init__(self) -> None:
        object.__setattr__(self, "signs", tuple(self.signs))


@dataclass(frozen=True)
class Integrator:
    """Integrate input over time; output starts at ic (the ball-and-disc)."""

    ic: float


@dataclass(frozen=True)
class Sine:
    """Independent sine source: amp * sin(2*pi*freq*t) (the master shaft)."""

    freq: float
    amp: float


@dataclass(frozen=True)
class Mul:
    """Two-input multiplier (the servo multiplier)."""


@dataclass(frozen=True)
class Const:
    """Fixed reference voltage."""

    c: float


Block = Union[Gain, Summer, Integrator, Sine, Mul, Const]


def _arity(block) -> int:
    if isinstance(block, Gain):
        return 1
    if isinstance(block, Summer):
        return len(block.signs)
    if isinstance(block, Integrator):
        return 1
    if isinstance(block, Sine):
        return 0
    if isinstance(block, Mul):
        return 2
    if isinstance(block, Const):
        return 0
    raise TypeError("unknown block type: %r" % (type(block).__name__,))


# ---------------------------------------------------------------------------
# Netlist — named blocks + wires, validated at build (deny-closed)
# ---------------------------------------------------------------------------

Wire = Tuple[str, str, int]  # (src, dst, dst_input_index)


class Netlist:
    """A named patch-panel: blocks plus wires.

    Validation at construction (all ValueError):
      - wire references an unknown block
      - input index outside the block's arity
      - two wires on the same (dst, input) — fan-in conflict
      - algebraic loop: feedback among non-integrator blocks with no
        integrator in the loop (would need an implicit solve; refused)

    Missing inputs are *explicitly* 0.0 — the analog equivalent of an
    unpatched jack, documented, never an accident.
    """

    def __init__(self, blocks: Dict[str, object], wires: List[Wire]) -> None:
        self.blocks: Dict[str, object] = dict(blocks)
        self.wires: List[Wire] = [tuple(w) for w in wires]  # type: ignore[misc]
        self._validate()

    # -- validation ------------------------------------------------------
    def _validate(self) -> None:
        for src, dst, idx in self.wires:
            if src not in self.blocks:
                raise ValueError("wire from unknown block %r" % (src,))
            if dst not in self.blocks:
                raise ValueError("wire to unknown block %r" % (dst,))
            arity = _arity(self.blocks[dst])
            if not isinstance(idx, int) or idx < 0 or idx >= arity:
                raise ValueError(
                    "wire to %r: input index %r outside arity %d" % (dst, idx, arity)
                )
        seen = set()
        for _src, dst, idx in self.wires:
            if (dst, idx) in seen:
                raise ValueError(
                    "fan-in conflict: two wires drive %r input %d" % (dst, idx)
                )
            seen.add((dst, idx))
        self._check_no_algebraic_loop()

    def _check_no_algebraic_loop(self) -> None:
        nonint = [
            name for name, b in self.blocks.items() if not isinstance(b, Integrator)
        ]
        # edges through the non-integrator subgraph only
        edges: Dict[str, List[str]] = {n: [] for n in nonint}
        for src, dst, _idx in self.wires:
            if src in edges and dst in edges:
                edges[src].append(dst)
        # Kahn's algorithm; leftovers are in a cycle
        indeg = {n: 0 for n in nonint}
        for src in nonint:
            for dst in edges[src]:
                indeg[dst] += 1
        queue = [n for n in nonint if indeg[n] == 0]
        seen = 0
        while queue:
            n = queue.pop()
            seen += 1
            for dst in edges[n]:
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    queue.append(dst)
        if seen != len(nonint):
            stuck = sorted(n for n in nonint if indeg[n] > 0)
            raise ValueError(
                "algebraic loop refused among non-integrator blocks: %s "
                "(feedback must pass through an Integrator)" % ", ".join(stuck)
            )

    # -- helpers ----------------------------------------------------------
    @property
    def integrator_names(self) -> List[str]:
        return [name for name, b in self.blocks.items() if isinstance(b, Integrator)]

    def _eval_order(self) -> List[str]:
        """Topological order for the non-integrator blocks."""
        nonint = [
            name for name, b in self.blocks.items() if not isinstance(b, Integrator)
        ]
        edges: Dict[str, List[str]] = {n: [] for n in nonint}
        for src, dst, _idx in self.wires:
            if src in edges and dst in edges:
                edges[src].append(dst)
        indeg = {n: 0 for n in nonint}
        for src in nonint:
            for dst in edges[src]:
                indeg[dst] += 1
        queue = [n for n in nonint if indeg[n] == 0]
        order = []
        while queue:
            n = queue.pop()
            order.append(n)
            for dst in edges[n]:
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    queue.append(dst)
        return order  # no loop possible: validated at construction


# ---------------------------------------------------------------------------
# Solver — bounded fixed-step RK4, receipt-sealed
# ---------------------------------------------------------------------------


@dataclass
class Trace:
    """Recorded run: time axis plus per-block output signals."""

    t: List[float]
    signals: Dict[str, List[float]]


@dataclass
class Receipt:
    """Machine-checked receipt for a run."""

    steps_used: int
    dt: float
    t_end: float
    peak_dy_dt: float
    blocks_evaluated: int
    ok: bool


def _eval_block(block, inputs: List[float], t: float) -> float:
    if isinstance(block, Const):
        return block.c
    if isinstance(block, Sine):
        return block.amp * math.sin(2.0 * math.pi * block.freq * t)
    if isinstance(block, Gain):
        return block.k * inputs[0]
    if isinstance(block, Summer):
        return sum(s * v for s, v in zip(block.signs, inputs, strict=True))
    if isinstance(block, Mul):
        return inputs[0] * inputs[1]
    raise TypeError("unknown block type: %r" % (type(block).__name__,))


def _stage(net: Netlist, order: List[str], t: float, y: List[float]):
    """One derivative evaluation: outputs for every block, d(state)/dt."""
    vals: Dict[str, float] = {}
    for i, name in enumerate(net.integrator_names):
        vals[name] = y[i]

    def input_val(dst: str, j: int) -> float:
        for src, d, jj in net.wires:
            if d == dst and jj == j:
                return vals[src]  # src is an integrator or earlier in order
        return 0.0  # unpatched jack: explicitly 0.0

    for name in order:
        block = net.blocks[name]
        ins = [input_val(name, j) for j in range(_arity(block))]
        vals[name] = _eval_block(block, ins, t)
    derivs = [input_val(name, 0) for name in net.integrator_names]
    return derivs, vals


def simulate(
    net: Netlist,
    t_end: float,
    dt: float = 0.01,
    max_steps: int = 10000,
) -> Tuple[Trace, Receipt]:
    """Run the netlist with fixed-step RK4. Deny-closed on the step budget.

    Raises StepBudgetExceeded before doing partial work when
    ceil(t_end / dt) exceeds max_steps.
    """
    if t_end <= 0:
        raise ValueError("t_end must be positive")
    if dt <= 0:
        raise ValueError("dt must be positive")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    n_steps = math.ceil(t_end / dt)
    if n_steps > max_steps:
        raise StepBudgetExceeded(
            "run needs %d steps (t_end=%g, dt=%g) but max_steps=%d; "
            "raise max_steps or coarsen dt" % (n_steps, t_end, dt, max_steps)
        )

    order = net._eval_order()
    y = [net.blocks[name].ic for name in net.integrator_names]  # type: ignore[union-attr]

    _, vals = _stage(net, order, 0.0, y)  # derivative at t=0 unused here
    ts = [0.0]
    signals: Dict[str, List[float]] = {name: [vals[name]] for name in net.blocks}

    peak = 0.0
    for _step in range(n_steps):
        t = ts[-1]
        k1, _ = _stage(net, order, t, y)
        ym = [a + 0.5 * dt * b for a, b in zip(y, k1, strict=True)]
        k2, _ = _stage(net, order, t + 0.5 * dt, ym)
        ym = [a + 0.5 * dt * b for a, b in zip(y, k2, strict=True)]
        k3, _ = _stage(net, order, t + 0.5 * dt, ym)
        ym = [a + dt * b for a, b in zip(y, k3, strict=True)]
        k4, _ = _stage(net, order, t + dt, ym)
        y = [
            a + dt * (b1 + 2.0 * b2 + 2.0 * b3 + b4) / 6.0
            for a, b1, b2, b3, b4 in zip(y, k1, k2, k3, k4, strict=True)
        ]
        # max() can't take (x, *possibly_empty_gen): a single positional
        # arg makes it iterate x. Explicit loop instead.
        for ks in (k1, k2, k3, k4):
            for d in ks:
                peak = max(peak, abs(d))
        t_next = t + dt
        _, vals = _stage(net, order, t_next, y)
        ts.append(t_next)
        for name in net.blocks:
            signals[name].append(vals[name])

    receipt = Receipt(
        steps_used=n_steps,
        dt=dt,
        t_end=t_end,
        peak_dy_dt=peak,
        blocks_evaluated=n_steps * 4 * len(net.blocks),
        ok=True,
    )
    return Trace(t=ts, signals=signals), receipt


# ---------------------------------------------------------------------------
# Meccano view — demystification for learners
# ---------------------------------------------------------------------------

_PARTS = {
    Integrator: (
        "ground-glass disc",
        "ball carriage",
        "torque amplifier (Bush's chain-maker)",
    ),
    Summer: ("resistor summing network", "patch-panel bus bar"),
    Gain: ("potentiometer", "servo-driven wiper"),
    Mul: ("servo multiplier", "squared-law diode pair"),
    Sine: ("sine-cosine potentiometer", "gear train from the master shaft"),
    Const: ("reference voltage tap", "patch cord"),
}


def parts_list(net: Netlist) -> List[str]:
    """Pseudo-'Meccano' parts for each block — what it would have been
    in brass and bakelite, so the machine is demystified, not mystified."""
    lines = []
    for name, block in net.blocks.items():
        parts = _PARTS.get(type(block), ("unknown part",))
        lines.append("%s '%s': %s" % (type(block).__name__, name, ", ".join(parts)))
    return lines


# ---------------------------------------------------------------------------
# Prebuilt demo — the damped spring: m*x'' + c*x' + k*x = 0
# ---------------------------------------------------------------------------


def damped_spring(
    m: float = 1.0,
    c: float = 0.5,
    k: float = 4.0,
    x0: float = 1.0,
    v0: float = 0.0,
) -> Netlist:
    """Patch panel for m*x'' + c*x' + k*x = 0, released from (x0, v0).

    Wiring: x -> Gain(-k/m) --\\                        (Hooke's law term)
                 v -> Gain(-c/m) --+--> Summer -> Int(v) -> Int(x) -> x
                                   \\--(damping term)     ^           |
                                                          +-----------+
    Two integrators in series; the only loop in analog computing.
    """
    if m <= 0:
        raise ValueError("m must be positive")
    return Netlist(
        blocks={
            "accel": Summer(signs=(1.0, 1.0)),  # x'' = -(k/m)x + -(c/m)v
            "vel": Integrator(ic=v0),  # integrates accel -> v
            "pos": Integrator(ic=x0),  # integrates v -> x
            "spring": Gain(k=-k / m),
            "damper": Gain(k=-c / m),
        },
        wires=[
            ("pos", "spring", 0),
            ("vel", "damper", 0),
            ("spring", "accel", 0),
            ("damper", "accel", 1),
            ("accel", "vel", 0),
            ("vel", "pos", 0),
        ],
    )
