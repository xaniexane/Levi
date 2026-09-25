"""Attract mode: the unattended auto-play demo loop — marketing that cannot lie.

Studied from: games-deadmechanics-20260916/findings.jsonl
[arch-games-attract-mode] (Attract mode: unattended auto-play demo loop on
the real hardware; marketing that cannot lie — the game demonstrates its
actual loop).

This is an original, from-scratch implementation for LEVI. The honest core
of attract mode is that the demo runs *the real game loop* — not a canned
video, not a scripted fake. ``AttractMode`` drives a game through its own
``update(state, inputs) -> state`` step function using a recorded input
script (``DemoScript``), looping forever until real input arrives. Because
the same step function powers real play, the demo cannot show anything the
game cannot actually do: marketing that cannot lie.

``DemoRecorder`` captures a real play session — frames of (inputs) paired
with the resulting states — into a ``DemoScript``. ``AttractMode.run`` then
replays the script against the game's step function from the initial state
and yields each frame: (frame_index, state). Two honest guards keep it a
demo and not a runaway:

- ``max_loops``: the loop terminates after N full passes of the script.
- ``interrupt``: any real input event passed to ``notify_input`` stops the
  demo immediately and hands control back to the player.

A frame budget (``frame_budget_ms``) is tracked: each replayed frame is
checked against the budget and overruns are reported in the frame record,
so the demo also proves the game hits its timing on the real hardware.

Public surface:
- ``DemoScript``: ``frames`` (tuple of input payloads), ``loop_count``.
- ``DemoRecorder``: ``capture(inputs, state)``, ``finish()`` -> DemoScript.
- ``AttractMode``: ``run(step_fn, initial_state)`` yields ``DemoFrame``;
  ``notify_input(event)`` interrupts; ``stats()``.

Honest limits: the demo is only as good as the recording — a dull script
makes a dull demo. Frame timing is measured with a monotonic clock; on a
loaded machine the budget report reflects that honestly. This module steps
the loop; it does not render.

stdlib-only. No network. Deterministic replay (same script + step fn =
same states).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Tuple


ORIGIN = "levi-revival/attract_mode"


class AttractError(ValueError):
    """Raised for invalid scripts or recorder misuse."""


@dataclass(frozen=True)
class DemoFrame:
    """One replayed frame: index, loop pass, resulting state, timing."""

    frame_index: int
    loop: int
    state: Any
    over_budget: bool


@dataclass(frozen=True)
class DemoScript:
    """The recorded input sequence that the attract loop replays."""

    frames: Tuple[Any, ...]
    recorded_frames: int = 0

    def __post_init__(self) -> None:
        if not self.frames:
            raise AttractError("a demo script needs at least one frame")


@dataclass
class DemoRecorder:
    """Captures real play into a replayable DemoScript."""

    _inputs: List[Any] = field(default_factory=list)
    _finished: bool = field(default=False, init=False)

    def capture(self, inputs: Any) -> None:
        """Record one frame's inputs from real play."""
        if self._finished:
            raise AttractError("recorder already finished")
        self._inputs.append(inputs)

    def finish(self) -> DemoScript:
        """Seal the recording into a DemoScript."""
        if self._finished:
            raise AttractError("recorder already finished")
        if not self._inputs:
            raise AttractError("cannot finish an empty recording")
        self._finished = True
        return DemoScript(frames=tuple(self._inputs), recorded_frames=len(self._inputs))


@dataclass
class AttractMode:
    """Unattended demo loop over the game's real step function.

    ``step_fn(state, inputs) -> state`` must be the same function real play
    uses — that identity is what makes the demo honest.
    """

    script: DemoScript
    max_loops: int = 0  # 0 = loop until interrupted
    frame_budget_ms: float = 16.7
    _interrupted: bool = field(default=False, init=False)
    _frames_shown: int = field(default=0, init=False)
    _overruns: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_loops < 0:
            raise AttractError("max_loops cannot be negative")
        if self.frame_budget_ms <= 0:
            raise AttractError("frame_budget_ms must be positive")

    def notify_input(self, event: Any = None) -> None:
        """A real player touched the controls: stop the demo, hand over."""
        self._interrupted = True

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    def run(
        self,
        step_fn: Callable[[Any, Any], Any],
        initial_state: Any,
    ) -> Iterator[DemoFrame]:
        """Replay the script through the real game loop, yielding frames.

        Stops when interrupted, or after ``max_loops`` full passes (if set).
        Each yielded frame reports whether the step overran the frame budget.
        """
        loop = 0
        while not self._interrupted:
            if self.max_loops and loop >= self.max_loops:
                break
            state = initial_state
            for idx, inputs in enumerate(self.script.frames):
                if self._interrupted:
                    break
                start = time.monotonic()
                state = step_fn(state, inputs)
                elapsed_ms = (time.monotonic() - start) * 1000.0
                over = elapsed_ms > self.frame_budget_ms
                self._frames_shown += 1
                if over:
                    self._overruns += 1
                yield DemoFrame(
                    frame_index=idx, loop=loop, state=state, over_budget=over
                )
            loop += 1

    def stats(self) -> Dict[str, Any]:
        return {
            "frames_shown": self._frames_shown,
            "budget_overruns": self._overruns,
            "interrupted": self._interrupted,
            "script_frames": len(self.script.frames),
            "frame_budget_ms": self.frame_budget_ms,
        }
