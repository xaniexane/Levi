"""LEVI's ritual learner: IF puzzle automation that learns your solutions.

Studied from: games-hunt-20260916-0022/report.md [Find 1 — Interactive fiction].

The shape being studied: Hadean-Lands-style puzzle automation — once the
player has solved a fiddly ritual by hand, the game *learns the solution
and automates it*. The tedium compresses into a single command; the
player's demonstrated knowledge becomes a reusable tool.

``puzzle_automation`` rebuilds that shape from scratch, LEVI-native:

- ``Recorder`` — wraps any command-driven engine (anything with
  ``step(command) -> response``). You declare a goal predicate over the
  engine; every command fed through the recorder is logged, and when the
  goal trips, the successful command list is kept as a ``Routine``.
- ``Routine`` — a named, replayable command list with a success record.
- ``generalize`` — a heuristic merge: record the same ritual twice with
  one word different ("take brass key", "take iron key") and the differing
  token becomes a ``{slot}`` you fill in at replay time.
- ``Automator`` — replays a routine against an engine, substituting slot
  bindings, and reports exactly where a replay broke if it did.

Honest limits: "learning" here is verbatim recording plus one stated
heuristic (single-token-difference generalization). There is no semantic
understanding of the puzzle, no planning, and no guarantee a routine
replays in a changed world — the automator tells you the step where it
diverged instead of pretending it worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol


ORIGIN = "levi-revival/puzzle-automation"


class AutomationError(Exception):
    """Base class for puzzle-automation failures."""


class EngineLike(Protocol):
    def step(self, command: str) -> str: ...


@dataclass
class Routine:
    """A learned solution: replayable commands, optionally with slots."""

    name: str
    steps: List[str]
    slots: List[str] = field(default_factory=list)  # e.g. ["{0}"]
    recordings: int = 1
    replays_ok: int = 0
    replays_failed: int = 0

    def render(self, bindings: Optional[Dict[str, str]] = None) -> List[str]:
        """Fill ``{slot}`` placeholders; raises if a slot is unbound."""
        bindings = bindings or {}
        rendered = []
        for step in self.steps:
            try:
                rendered.append(step.format(**bindings))
            except KeyError as exc:
                raise AutomationError(
                    f"routine {self.name!r} needs a binding for slot {exc}"
                ) from exc
        return rendered

    def describe(self) -> str:
        slot_note = f" slots={self.slots}" if self.slots else ""
        return (
            f"{self.name}: {len(self.steps)} steps "
            f"({self.recordings} recordings, "
            f"{self.replays_ok} ok / {self.replays_failed} failed replays{slot_note})"
        )


class Recorder:
    """Watches commands flow into an engine and keeps the ones that worked.

    ``goal`` is a zero-argument predicate inspected after every command —
    typically a closure over engine state ("player now holds the lamp").
    """

    def __init__(self, engine: EngineLike):
        self.engine = engine
        self.routines: Dict[str, Routine] = {}
        self._active: Optional[str] = None
        self._active_steps: List[str] = []
        self._goal: Optional[Callable[[], bool]] = None

    def begin(self, name: str, goal: Callable[[], bool]) -> None:
        if self._active is not None:
            raise AutomationError(f"already recording {self._active!r}")
        self._active = name
        self._active_steps = []
        self._goal = goal

    def feed(self, command: str) -> str:
        """Send one command to the engine, recording it if armed.

        Returns the engine's response. If the goal trips, the recording
        finalizes into a routine automatically.
        """
        if self._active is None:
            raise AutomationError("no recording in progress — call begin() first")
        response = self.engine.step(command)
        self._active_steps.append(command)
        assert self._goal is not None
        if self._goal():
            name = self._active
            steps = list(self._active_steps)
            self._active = None
            self._active_steps = []
            self._goal = None
            self._store(name, steps)
        return response

    def cancel(self) -> None:
        self._active = None
        self._active_steps = []
        self._goal = None

    @property
    def recording(self) -> Optional[str]:
        return self._active

    def _store(self, name: str, steps: List[str]) -> Routine:
        if name in self.routines:
            merged = generalize([self.routines[name].steps, steps])
            self.routines[name] = Routine(
                name=name,
                steps=merged,
                slots=sorted({t for s in merged for t in _slots_in(s)}),
                recordings=self.routines[name].recordings + 1,
                replays_ok=self.routines[name].replays_ok,
                replays_failed=self.routines[name].replays_failed,
            )
        else:
            self.routines[name] = Routine(name=name, steps=list(steps))
        return self.routines[name]

    def get(self, name: str) -> Routine:
        try:
            return self.routines[name]
        except KeyError:
            raise AutomationError(f"no routine named {name!r}") from None


def _slots_in(step: str) -> List[str]:
    out, buf, in_slot = [], "", False
    for ch in step:
        if ch == "{" and not in_slot:
            in_slot, buf = True, ""
        elif ch == "}" and in_slot:
            in_slot = False
            out.append(buf)
        elif in_slot:
            buf += ch
    return out


def generalize(recordings: List[List[str]]) -> List[str]:
    """Merge same-length recordings into one slotted routine.

    Heuristic, stated plainly: recordings must have the same number of
    steps; at each position, if all recordings agree the token is kept,
    and if they differ in exactly the tokens at that position, the
    position becomes a ``{i}`` slot. Anything else (different lengths,
    multi-token divergence patterns we can't align) raises instead of
    guessing.
    """
    if not recordings:
        raise AutomationError("nothing to generalize")
    n = len(recordings[0])
    if any(len(r) != n for r in recordings):
        raise AutomationError("recordings have different lengths — cannot align")
    merged: List[str] = []
    for pos in range(n):
        tokenized = [r[pos].split() for r in recordings]
        width = len(tokenized[0])
        if any(len(t) != width for t in tokenized):
            raise AutomationError(
                f"step {pos}: recordings differ in word count — cannot align"
            )
        out_tokens = []
        for w in range(width):
            words = {t[w] for t in tokenized}
            # Named slots ({w0}) so Routine.render can fill them by keyword.
            out_tokens.append(words.pop() if len(words) == 1 else f"{{w{w}}}")
        merged.append(" ".join(out_tokens))
    return merged


@dataclass
class ReplayResult:
    routine: str
    ok: bool
    steps_run: int
    failed_at: Optional[int] = None
    failure: str = ""
    responses: List[str] = field(default_factory=list)


class Automator:
    """Replays routines against an engine, reporting honest outcomes."""

    def __init__(self, engine: EngineLike):
        self.engine = engine

    def replay(
        self,
        routine: Routine,
        bindings: Optional[Dict[str, str]] = None,
        stop_on: Optional[Callable[[str], bool]] = None,
    ) -> ReplayResult:
        """Run every rendered step. ``stop_on`` inspects each response and
        may declare the replay broken early (e.g. "I don't see that here").
        """
        steps = routine.render(bindings)
        responses: List[str] = []
        for i, cmd in enumerate(steps):
            try:
                resp = self.engine.step(cmd)
            except Exception as exc:  # noqa: BLE001 — report, don't crash
                routine.replays_failed += 1
                return ReplayResult(
                    routine.name,
                    False,
                    i,
                    failed_at=i,
                    failure=f"engine raised {type(exc).__name__}: {exc}",
                    responses=responses,
                )
            responses.append(resp)
            if stop_on is not None and stop_on(resp):
                routine.replays_failed += 1
                return ReplayResult(
                    routine.name,
                    False,
                    i + 1,
                    failed_at=i,
                    failure=f"stop condition tripped: {resp!r}",
                    responses=responses,
                )
        routine.replays_ok += 1
        return ReplayResult(routine.name, True, len(steps), responses=responses)
