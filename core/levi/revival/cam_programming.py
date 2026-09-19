"""Cam programming: declarative automation as a pinned barrel.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #11)

The mechanism: a rotating cylinder (the barrel) studded with pins in
rows. Each row is a track; each angular position is a time step. As the
barrel turns, pins strike levers and fire actions. The program is the
pin pattern — declarative (it says *when*, never *how*), inspectable
(you can see every pin), and read-only once pinned (the barrel is
memory you cannot accidentally rewrite mid-performance).

What this module models:
- ``PinBarrel``: tracks x steps grid; ``pin``/``unpin``/``is_pinned``;
  ``run`` turns the barrel and returns the ordered strike events,
  optionally invoking per-track actuator callables.
- ``BarrelProgram``: the frozen, read-only snapshot — pinning a frozen
  program raises, the way a pinned barrel cannot be re-pinned
  mid-revolution.
- ``Cam``: the continuous cousin — a radial profile function whose
  follower lift is the profile's height above its minimum; included
  because barrel pins are the discretized form of a cam's edge.

Honest limits: time is logical (steps per revolution), not wall-clock —
``run`` does not sleep or schedule; actuators are plain callables
invoked synchronously. This is a program representation and a
deterministic simulator, not a real-time controller. No network, stdlib
only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional, Tuple


ORIGIN = "levi-revival/cam-programming"


@dataclass(frozen=True)
class Strike:
    """One pin striking its lever: track, step, and revolution number."""

    track: int
    step: int
    revolution: int


@dataclass(frozen=True)
class BarrelProgram:
    """A frozen pin pattern: read-only memory.

    ``pins`` maps track -> frozenset of pinned steps. Any attempt to
    mutate raises ``TypeError`` (frozen dataclass) — the barrel, once
    pinned, does not change under the performer's hands.
    """

    tracks: int
    steps: int
    pins: Tuple[frozenset, ...]

    def is_pinned(self, track: int, step: int) -> bool:
        self._check(track, step)
        return step in self.pins[track]

    def _check(self, track: int, step: int) -> None:
        if not 0 <= track < self.tracks:
            raise IndexError(f"track {track} out of range 0..{self.tracks - 1}")
        if not 0 <= step < self.steps:
            raise IndexError(f"step {step} out of range 0..{self.steps - 1}")


class PinBarrel:
    """A pinnable program barrel: tracks x steps of declarative timing."""

    def __init__(self, tracks: int, steps: int) -> None:
        if tracks < 1 or steps < 1:
            raise ValueError("barrel needs at least one track and one step")
        self.tracks = tracks
        self.steps = steps
        self._pins: List[set] = [set() for _ in range(tracks)]

    def _check(self, track: int, step: int) -> None:
        if not 0 <= track < self.tracks:
            raise IndexError(f"track {track} out of range 0..{self.tracks - 1}")
        if not 0 <= step < self.steps:
            raise IndexError(f"step {step} out of range 0..{self.steps - 1}")

    # -- pinning the program ---------------------------------------------
    def pin(self, track: int, step: int) -> None:
        """Drive a pin at (track, step). Idempotent."""
        self._check(track, step)
        self._pins[track].add(step)

    def unpin(self, track: int, step: int) -> None:
        """Pull the pin at (track, step). Idempotent."""
        self._check(track, step)
        self._pins[track].discard(step)

    def is_pinned(self, track: int, step: int) -> bool:
        self._check(track, step)
        return step in self._pins[track]

    def freeze(self) -> BarrelProgram:
        """Return the read-only snapshot of the current pin pattern."""
        return BarrelProgram(
            tracks=self.tracks,
            steps=self.steps,
            pins=tuple(frozenset(s) for s in self._pins),
        )

    # -- performing --------------------------------------------------------
    def run(
        self,
        revolutions: int = 1,
        actuators: Optional[Mapping[int, Callable[[Strike], None]]] = None,
    ) -> List[Strike]:
        """Turn the barrel and collect the strike events in order.

        Steps advance 0..steps-1 within each revolution; tracks fire in
        track order within a step. Actuators, if given, are invoked
        synchronously per strike.
        """
        if revolutions < 1:
            raise ValueError("revolutions must be >= 1")
        strikes: List[Strike] = []
        for rev in range(revolutions):
            for step in range(self.steps):
                for track in range(self.tracks):
                    if step in self._pins[track]:
                        strike = Strike(track=track, step=step, revolution=rev)
                        strikes.append(strike)
                        if actuators and track in actuators:
                            actuators[track](strike)
        return strikes

    # -- inspection ----------------------------------------------------------
    def inspect(self) -> str:
        """The barrel unrolled: one row per track, pins as '*'.

        The whole program is visible at a glance — that inspectability
        is the reason pinned programs are trustworthy.
        """
        rows = []
        for track in range(self.tracks):
            row = "".join(
                "*" if s in self._pins[track] else "." for s in range(self.steps)
            )
            rows.append(f"t{track}: {row}")
        return "\n".join(rows)


class Cam:
    """A radial cam: follower lift follows the profile's height.

    ``profile`` maps an angle in [0, 2*pi) to a radius. The lift at an
    angle is the radius minus the profile's minimum — the follower only
    ever feels height above the lowest point, exactly like a real
    follower riding the cam's edge.
    """

    def __init__(self, profile: Callable[[float], float], samples: int = 360) -> None:
        if samples < 8:
            raise ValueError("samples must be >= 8")
        import math

        self._lift = [profile(2.0 * math.pi * i / samples) for i in range(samples)]
        base = min(self._lift)
        self._lift = [r - base for r in self._lift]
        self.samples = samples

    def lift_at(self, step: int) -> float:
        """Follower lift at a discrete step of the revolution."""
        return self._lift[step % self.samples]

    def max_lift(self) -> float:
        return max(self._lift)

    def dwell_steps(self) -> int:
        """Steps where the follower rests at the base circle (lift ~ 0)."""
        return sum(1 for lift in self._lift if lift <= 1e-9)
