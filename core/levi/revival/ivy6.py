"""The six-task method: capacity cap, total order, strictly sequential work.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #16)

Three constraints do all the work:

1. **Capacity cap** — at most six tasks. Seven is refused, not squeezed.
2. **Total order** — ranked once, at the planning moment. No choosing
   what to do next during the day; the choice was made last night.
3. **Sequential execution** — the system reveals ONLY the current task.
   Task #2 stays hidden until #1 is done or deliberately deferred.

The planning moment and the working moment are separate phases:
:meth:`IvyLeeDay.plan` (evening) vs :meth:`IvyLeeDay.current` /
:meth:`IvyLeeDay.complete` (the day). :meth:`IvyLeeDay.end_day` returns
the unfinished tasks in order — the roll-forward candidates for
tomorrow's planning.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is the cap, the order, and the
sequential reveal. Not revived: any claim about the method's origin
story — the value is in the constraints, not the legend.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


ORIGIN = "levi-revival/ivy6"

MAX_TASKS = 6


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IvyLeeError(Exception):
    """Base class for six-task failures."""


class PhaseError(IvyLeeError):
    """An action was attempted in the wrong phase."""


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """One of the six: a title and whether it got done."""

    title: str
    done: bool = False
    deferred: bool = False
    completed_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "done": self.done,
            "deferred": self.deferred,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            data["title"],
            data.get("done", False),
            data.get("deferred", False),
            data.get("completed_at"),
        )


# ---------------------------------------------------------------------------
# The day
# ---------------------------------------------------------------------------


class IvyLeeDay:
    """One day under the six-task discipline. Phases: ``plan`` (rank up to
    six tasks) -> ``work`` (exactly one visible task at a time) -> ``done``
    (queue exhausted). :meth:`end_day` closes the day and returns the
    roll-forward list."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.phase: str = "plan"
        self._tasks: list[Task] = []
        self._cursor: int = 0
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "ivy6.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.phase = data.get("phase", "plan")
        self._cursor = int(data.get("cursor", 0))
        self._tasks = [Task.from_dict(d) for d in data.get("tasks", [])]

    def save(self) -> Path:
        """Persist the day. Only meaningful when constructed with a path."""
        if self.path is None:
            raise IvyLeeError("no path: this day is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "phase": self.phase,
                    "cursor": self._cursor,
                    "tasks": [t.to_dict() for t in self._tasks],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- the planning moment ---------------------------------------------------
    def plan(self, titles: list[str]) -> list[str]:
        """The evening ritual: rank tomorrow's tasks, most important first.
        At most six; at least one; blanks refused. Planning closes the
        moment work begins — it cannot be re-done mid-day."""
        if self.phase != "plan":
            raise PhaseError(f"cannot plan during the {self.phase!r} phase")
        cleaned = [t.strip() for t in titles if t and t.strip()]
        if not cleaned:
            raise ValueError("plan at least one task")
        if len(cleaned) > MAX_TASKS:
            raise ValueError(f"at most {MAX_TASKS} tasks — {len(cleaned)} refused")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("duplicate tasks refused")
        self._tasks = [Task(title=t) for t in cleaned]
        self._cursor = 0
        self.phase = "work"
        return [t.title for t in self._tasks]

    # -- the working moment: exactly one visible task ---------------------------
    def _require_work(self) -> None:
        if self.phase != "work":
            raise PhaseError(f"no current task in the {self.phase!r} phase")

    def current(self) -> str | None:
        """The ONLY task the system reveals. Everything else stays hidden
        until this one is done or deliberately deferred."""
        if self.phase == "done":
            return None
        self._require_work()
        return self._tasks[self._cursor].title

    def complete(self) -> str | None:
        """Finish the current task and advance. Returns the next revealed
        task, or None when the queue is exhausted."""
        self._require_work()
        task = self._tasks[self._cursor]
        task.done = True
        task.completed_at = time.time()
        self._advance()
        return self.current() if self.phase == "work" else None

    def defer(self) -> str | None:
        """Deliberately set the current task aside — it rolls to tomorrow's
        planning, it doesn't vanish. Returns the next revealed task."""
        self._require_work()
        self._tasks[self._cursor].deferred = True
        self._advance()
        return self.current() if self.phase == "work" else None

    def _advance(self) -> None:
        self._cursor += 1
        if self._cursor >= len(self._tasks):
            self.phase = "done"

    def is_done(self) -> bool:
        return self.phase == "done"

    def remaining(self) -> int:
        """How many tasks are still unrevealed — a count, not the tasks."""
        if self.phase != "work":
            return 0
        return len(self._tasks) - self._cursor

    # -- the day's end ------------------------------------------------------------
    def end_day(self) -> dict:
        """Close the day. Returns completed and unfinished titles in the
        original ranked order — the unfinished are tomorrow's
        roll-forward candidates. The day resets to the planning phase."""
        if self.phase == "plan":
            raise PhaseError("nothing to end: the day was never planned")
        completed = [t.title for t in self._tasks if t.done]
        unfinished = [t.title for t in self._tasks if not t.done]
        report = {"completed": completed, "unfinished": unfinished}
        self.phase = "plan"
        self._tasks = []
        self._cursor = 0
        return report

    def roll_forward(
        self, carried: list[str], extra: list[str] | None = None
    ) -> list[str]:
        """Start tomorrow's planning pre-filled with carried tasks (kept in
        order), topped up with new ones. The cap still applies."""
        titles = list(carried) + list(extra or [])
        return self.plan(titles)


__all__ = [
    "ORIGIN",
    "MAX_TASKS",
    "IvyLeeError",
    "PhaseError",
    "Task",
    "IvyLeeDay",
]
