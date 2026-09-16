"""Ivy Lee's six-task method: the daily planner with a capacity cap.

Origin: the 1918 productivity prescription attributed to consultant Ivy Lee —
each evening write at most six tasks for tomorrow, rank them by importance,
work them strictly in order; unfinished tasks roll to the next day's list.
(The Charles Schwab meeting and the alleged $25,000 payment are business
folklore, told with hedging even by promoters — the method's value does not
depend on the legend.)

What it is in LEVI: the ritual, enforced. Three constraints do the work — a
capacity cap (six, not sixty), a total order (the choice of what to do next
was made last night), and sequential execution (one thing at a time). The
assistant's job is hiding the other five: ``current()`` reveals only task
#1. ``complete``/``defer`` refuse out-of-order work — the discipline is in
the refusal.

Honesty label: LOAD-BEARING — cap + order + sequence is a concrete,
transferable mechanism.

Deny-closed inputs: more than six tasks, empty titles, duplicate titles,
orders that don't cover exactly the pending tasks, and completing a task
that isn't current are all rejected with ValueError.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional, Union

__all__ = ["Task", "IvyLeeDay", "MAX_TASKS"]

MAX_TASKS = 6

DateLike = Union[date, str]


def _parse_day(value: DateLike) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            y, m, d = value.split("-")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            pass
    raise ValueError(f"day: expected datetime.date or 'YYYY-MM-DD', got {value!r}")


@dataclass
class Task:
    id: str
    title: str
    notes: str = ""
    status: str = "pending"  # pending | done | deferred
    rolled: int = 0  # how many mornings this task has carried over
    defer_reason: str = ""


class IvyLeeDay:
    """One day's six-task plan, worked strictly in rank order."""

    def __init__(self, day: DateLike):
        self.day = _parse_day(day)
        self._tasks: dict[str, Task] = {}
        self._order: list[str] = []  # task ids, most important first

    # -- evening planning ------------------------------------------------
    def add_task(self, title: str, notes: str = "") -> Task:
        """Write down a task for the day. At most six — the cap is the method."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("task title must be a non-empty string")
        title = title.strip()
        if len(self._tasks) >= MAX_TASKS:
            raise ValueError(f"Ivy Lee cap: at most {MAX_TASKS} tasks per day")
        if any(t.title.lower() == title.lower() for t in self._tasks.values()):
            raise ValueError(f"duplicate task: {title!r}")
        task = Task(id=uuid.uuid4().hex[:12], title=title, notes=notes or "")
        self._tasks[task.id] = task
        self._order.append(task.id)  # insertion order until ranked
        return task

    def set_order(self, task_ids: list[str]) -> None:
        """Rank the day's tasks by importance, most important first.

        Must cover exactly the pending tasks, each once — a *total* order,
        so there is never a choice to make in the morning.
        """
        pending = [t.id for t in self._tasks.values() if t.status == "pending"]
        if sorted(task_ids) != sorted(pending) or len(set(task_ids)) != len(task_ids):
            raise ValueError(
                "order must list each pending task exactly once; "
                f"pending={[self._tasks[i].title for i in pending]}"
            )
        self._order = list(task_ids)

    # -- the working day ---------------------------------------------------
    def queue(self) -> list[Task]:
        """Pending tasks in rank order (the assistant normally hides these)."""
        return [
            self._tasks[i] for i in self._order if self._tasks[i].status == "pending"
        ]

    def current(self) -> Optional[Task]:
        """The single visible task: #1. Everything else stays hidden."""
        q = self.queue()
        return q[0] if q else None

    def _require_current(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"unknown task: {task_id!r}")
        cur = self.current()
        if cur is None or cur.id != task_id:
            raise ValueError(
                f"Ivy Lee rule: work strictly in order — current task is "
                f"{cur.title!r}, not {task.title!r}"
            )
        return task

    def complete(self, task_id: str) -> Task:
        """Finish the current task; #2 is revealed only now."""
        task = self._require_current(task_id)
        task.status = "done"
        return task

    def defer(self, task_id: str, reason: str = "") -> Task:
        """Deliberately set the current task aside (it will roll forward)."""
        task = self._require_current(task_id)
        task.status = "deferred"
        task.defer_reason = reason or ""
        return task

    # -- next morning -------------------------------------------------------
    def roll_forward(self, next_day: DateLike) -> "IvyLeeDay":
        """Carry unfinished tasks to tomorrow's list, preserving rank."""
        nxt = IvyLeeDay(next_day)
        if nxt.day <= self.day:
            raise ValueError("roll_forward requires a later day")
        for tid in self._order:
            task = self._tasks[tid]
            if task.status in ("pending", "deferred"):
                carried = Task(
                    id=task.id,
                    title=task.title,
                    notes=task.notes,
                    status="pending",
                    rolled=task.rolled + 1,
                    defer_reason=task.defer_reason,
                )
                nxt._tasks[carried.id] = carried
                nxt._order.append(carried.id)
        return nxt

    def chronic_rollers(self, threshold: int = 3) -> list[Task]:
        """Tasks that have rolled forward ``threshold``+ mornings.

        These are your real priorities, revealed — or tasks to admit you'll
        never do and delete instead of carrying forever.
        """
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        return [t for t in self.queue() if t.rolled >= threshold]

    def summary(self) -> dict:
        done = sum(1 for t in self._tasks.values() if t.status == "done")
        return {
            "day": self.day.isoformat(),
            "total": len(self._tasks),
            "done": done,
            "remaining": len(self.queue()),
            "current": self.current().title if self.current() else None,
        }
