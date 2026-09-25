"""LEVI analog — pre-digital computation, revived LEVI-native.

REMIX DELTA: what the originals taught, and what LEVI does differently.

What the originals taught
--------------------------
- Thomson's ball-and-disc integrator (1876): integration is *mechanical* —
  a ball rolling on a spinning disc turns calculus into displacement. The
  machine makes the mathematics visible and touchable.
- Bush's differential analyzer (1931): integrators alone were toys; the
  torque amplifier made them *chainable*, so a differential equation became
  a wiring diagram. Composition beats components.
- REAC / EAI patch-panel machines (1950s-60s): op-amp integrators, summers,
  and multipliers behind a plugboard let engineers wire an ODE in minutes
  and watch it solve itself in real time. Solving was *playful*.
- Comdyna GP-6 (1970s): analog shrank to a suitcase, but digital won on
  precision and reproducibility, and the whole paradigm was composted.
- d'Ocagne's nomographs (1880s): a paper chart that computes — draw one
  straight line across three scales and read the answer. Zero energy,
  survives any outage, teaches the *shape* of an equation.
- Michelson's harmonic analyzer (1890s): springs and gears adding sines;
  Fourier analysis as a machine you could watch.

What LEVI does differently (the remix, not the replica)
-------------------------------------------------------
- :mod:`levi.analog.bench` — a virtual patch-panel workbench. The same
  blocks (integrator, summer, gain, multiplier, sine, const), but solved
  with bounded fixed-step RK4, every run sealed with a machine-checked
  Receipt (steps used, peak |dy/dt|, blocks evaluated), algebraic loops
  refused at build time, and a "Meccano view" (parts_list) that shows what
  each virtual block *would have been* in brass — demystification, not
  mystification. LEVI-native delta: receipts and bounds; the originals had
  neither.
- :mod:`levi.analog.nomo` — nomographs as living charts: solve with
  bounded bisection (honest residual reported, never hidden), render the
  same chart as ASCII for the terminal and as SVG for printing. LEVI-native
  delta: the accuracy note is computed, not promised.
- :mod:`levi.analog.fourier` — Michelson's harmonic analyzer as a terminal
  playground: stack sine bars, watch the waveform, decompose it back with a
  pure-Python DFT. LEVI-native delta: analysis and synthesis in one loop,
  stdlib-only, no hardware.

What it ADDS that the giants refuse: equations as wiring diagrams for
learners, printable compute that needs no server, and Fourier you can hear
with your eyes — all local, all free, all honest about their limits.

Safety boundaries: deny-closed everywhere. Fixed step budgets
(StepBudgetExceeded), bounded bisection, bounded iteration; missing
patch-panel inputs default to 0.0 *explicitly*. Algebraic loops (instant
feedback without an integrator) are refused at build time, not chased at
runtime.

Run: ``python -m levi.analog --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
    "HOME_DIRNAME",
    "StepBudgetExceeded",
]

from .bench import StepBudgetExceeded

HOME_DIRNAME = "analog"

SHELF = {
    "name": "analog workbench",
    "summary": (
        "Virtual patch-panel analog computer (ball-and-disc lineage, Bush torque "
        "amplifier lineage), printable nomograph charts, and a terminal Fourier "
        "playground. Bounded solvers with receipts; stdlib-only; offline."
    ),
    "items": [
        "bench: Gain/Summer/Integrator/Sine/Mul/Const blocks, RK4 bounded solver, receipts, Meccano parts list",
        "nomo: X(u)+Y(v)=Z(w) nomographs, bisection solve, ASCII + SVG charts, computed accuracy note",
        "fourier: bars_to_wave, pure-Python DFT analyze, plot_ascii waveform",
    ],
}
