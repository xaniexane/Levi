"""Comdyna GP-6-style suitcase analog computer: immediacy beats precision.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #11, INSPIRATIONAL] — a suitcase analog computer owning the
pedagogical niche for decades; immediacy beats precision in teaching.

This is a *teaching* computer, not a precision instrument. The design
bets are explicit:

* **Small fixed inventory** — a handful of op-amps, pots, one
  multiplier. If a lesson needs more, the lesson is wrong, not the
  machine.
* **Knobs and meters, not patch listings.** ``turn_knob`` changes a
  parameter and ``read_meter`` answers *immediately* — the whole point
  is the tight loop between hand and eye.
* **Coarse on purpose.** Answers carry about ±5% accuracy and the
  module prints that on the meter card. A student who learns that
  models are approximate has learned the real lesson.

Lessons (``lesson_decay``, ``lesson_oscillator``) return a trace plus
the one-paragraph teaching note the instructor reads aloud. The
``what_if`` sweep re-runs a lesson across knob positions instantly —
immediacy as the API.

Honest limits: Euler integration at coarse steps; the ±5% figure is a
documented design target, and ``accuracy_check`` measures the actual
error against the closed-form solution so the claim stays checkable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple


ORIGIN = "levi-revival/suitcase-analog"

OP_AMPS = 6
POTS = 4
MULTIPLIERS = 1
ACCURACY_TARGET = 0.05  # the documented ±5% teaching tolerance


@dataclass
class MeterReading:
    label: str
    value: float
    unit: str = ""
    note: str = ""

    def card(self) -> str:
        unit = f" {self.unit}" if self.unit else ""
        return (
            f"{self.label}: {self.value:.4f}{unit} "
            f"(±{ACCURACY_TARGET * 100:.0f}% teaching tolerance)"
        )


class SuitcaseComputer:
    """The suitcase: knobs in, meters out, answers now."""

    def __init__(self) -> None:
        self.knobs: Dict[str, float] = {}
        self.inventory = {"op_amps": OP_AMPS, "pots": POTS, "multipliers": MULTIPLIERS}
        self._last_trace: List[Tuple[float, float]] = []

    def turn_knob(self, name: str, value: float) -> None:
        """Set a parameter. Takes effect on the next instant run."""
        if not math.isfinite(value):
            raise ValueError("knob value must be finite")
        self.knobs[name] = value

    def read_meter(self, label: str, value: float, unit: str = "") -> MeterReading:
        return MeterReading(
            label=label, value=value, unit=unit, note="teaching tolerance applies"
        )

    def _integrate(
        self, deriv: Callable[[float, float], float], y0: float, t_end: float, dt: float
    ) -> List[Tuple[float, float]]:
        y, t = y0, 0.0
        trace = [(t, y)]
        while t < t_end - 1e-12:
            step = min(dt, t_end - t)
            y = y + deriv(t, y) * step
            t += step
            trace.append((t, y))
        self._last_trace = trace
        return trace

    def lesson_decay(
        self, rate: float | None = None, y0: float = 1.0, t_end: float = 5.0
    ) -> Dict[str, object]:
        """dy/dt = -rate*y. The first lesson: things fade exponentially."""
        rate = self.knobs.get("rate", rate if rate is not None else 1.0)
        trace = self._integrate(lambda t, y: -rate * y, y0, t_end, dt=0.05)
        exact = y0 * math.exp(-rate * t_end)
        return {
            "lesson": "decay",
            "trace": trace,
            "meter": self.read_meter("y(final)", trace[-1][1]).card(),
            "teaching_note": (
                "Turn the rate knob and watch the meter: doubling the "
                "rate halves the time to fade, every time. The curve "
                "never quite touches zero — that is the point."
            ),
            "accuracy_check": abs(trace[-1][1] - exact) / abs(exact),
        }

    def lesson_oscillator(
        self, omega: float | None = None, t_end: float = 10.0
    ) -> Dict[str, object]:
        """x'' = -omega^2 x via two integrators. The second lesson:
        energy sloshes back and forth."""
        omega = self.knobs.get("omega", omega if omega is not None else 1.0)
        # state = [x, v]; coarse Euler, two sub-steps per meter tick
        x, v, t, dt = 1.0, 0.0, 0.0, 0.02
        trace = [(t, x)]
        while t < t_end - 1e-12:
            step = min(dt, t_end - t)
            v = v + (-omega * omega * x) * step
            x = x + v * step
            t += step
            trace.append((t, x))
        self._last_trace = trace
        exact = math.cos(omega * t_end)
        return {
            "lesson": "oscillator",
            "trace": trace,
            "meter": self.read_meter("x(final)", trace[-1][1]).card(),
            "teaching_note": (
                "The mass keeps missing the center and overshooting — "
                "that overshoot *is* the oscillation. Stiffen the "
                "spring (omega knob) and count the faster wiggles."
            ),
            "accuracy_check": abs(trace[-1][1] - exact),
        }

    def what_if(
        self, lesson: str, knob: str, values: List[float]
    ) -> List[Dict[str, object]]:
        """Sweep one knob across values and re-run instantly."""
        if lesson not in ("decay", "oscillator"):
            raise ValueError(f"unknown lesson: {lesson!r}")
        results = []
        for value in values:
            self.turn_knob(knob, value)
            run = self.lesson_decay() if lesson == "decay" else self.lesson_oscillator()
            results.append(
                {
                    "knob": knob,
                    "value": value,
                    "final": run["trace"][-1][1],
                    "accuracy_check": run["accuracy_check"],
                }
            )
        return results

    def inventory_card(self) -> Dict[str, object]:
        return {
            "op_amps": self.inventory["op_amps"],
            "pots": self.inventory["pots"],
            "multipliers": self.inventory["multipliers"],
            "philosophy": "immediacy beats precision",
            "accuracy_target": ACCURACY_TARGET,
        }
