"""Due-runner for scheduled agent tasks.

``schedule_add`` (in :mod:`levi.agent.tools`) records automations with
``TriggerKind.SCHEDULE`` and a cron expression — but nothing ever fired
them. This module is the missing half: :func:`fire_due` scans the
automation registry, evaluates each cron expression with a stdlib-only
matcher, and executes every due task through the real step-level
agentic loop (:func:`levi.agent.loop.run_subtask`).

Laws:
1. A schedule fires at most once per matching minute (idempotent).
2. Overlapping runs of the same automation never execute concurrently
   (pid lock file; stale locks expire).
3. Every firing is receipted: ``last_run``, ``last_result`` and
   ``run_count`` are persisted on the automation record.
4. Failures are honest: a crashed task records its error, never a
   fake success. One bad automation never stops the tick.
5. The tick is bounded: at most ``max_tasks`` automations per call.

Stdlib only. No network except what the task's own tools use.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_TTL_SECONDS = 600  # a lock older than this is stale and cleared
DEFAULT_MAX_TASKS = 5


# ---------------------------------------------------------------------------
# Cron matching (stdlib only — no croniter dependency in the kernel)
# ---------------------------------------------------------------------------


def _parse_field(text: str, lo: int, hi: int) -> set[int] | None:
    """Parse one cron field into a set of matching values.

    Supports ``*``, ``*/n``, ``a-b``, ``a,b`` and plain values.
    Returns ``None`` when the field is malformed (never raises — a bad
    expression simply never matches, and the caller reports it).
    """
    text = text.strip()
    try:
        if text == "*":
            return set(range(lo, hi + 1))
        values: set[int] = set()
        for part in text.split(","):
            part = part.strip()
            if "/" in part:
                base, step_s = part.split("/", 1)
                step = int(step_s)
                if step < 1:
                    return None
                if base == "*":
                    start, end = lo, hi
                elif "-" in base:
                    a, b = base.split("-", 1)
                    start, end = int(a), int(b)
                else:
                    start, end = int(base), hi
                if start < lo or end > hi or start > end:
                    return None
                values.update(range(start, end + 1, step))
            elif "-" in part:
                a, b = part.split("-", 1)
                start, end = int(a), int(b)
                if start < lo or end > hi or start > end:
                    return None
                values.update(range(start, end + 1))
            else:
                v = int(part)
                if v < lo or v > hi:
                    return None
                values.add(v)
        return values
    except (ValueError, TypeError):
        return None


def cron_matches(expr: str, when: datetime | None = None) -> bool:
    """True when the 5-field cron expression matches ``when`` (UTC now).

    Malformed expressions return False — a schedule that can never be
    parsed can never fire, and :func:`fire_due` reports it as an error
    on the automation rather than raising.
    """
    when = when or datetime.now(timezone.utc)
    parts = expr.split()
    if len(parts) != 5:
        return False
    minute = _parse_field(parts[0], 0, 59)
    hour = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    month = _parse_field(parts[3], 1, 12)
    dow = _parse_field(parts[4], 0, 6)  # 0 = Sunday
    if None in (minute, hour, dom, month, dow):
        return False
    # Python: Monday=0..Sunday=6 → cron: Sunday=0..Saturday=6
    cron_dow = (when.weekday() + 1) % 7
    return (
        when.minute in minute
        and when.hour in hour
        and when.day in dom
        and when.month in month
        and cron_dow in dow
    )


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


@dataclass
class FiredTask:
    automation_id: str
    name: str
    ok: bool
    summary: str


@dataclass
class SchedulerReport:
    """Honest outcome of one :func:`fire_due` tick."""

    fired: list[FiredTask] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # "id: reason"
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"tick: {len(self.fired)} fired, {len(self.skipped)} skipped"]
        for f in self.fired:
            lines.append(f"  {'OK ' if f.ok else 'FAIL'} {f.name}: {f.summary[:100]}")
        for s in self.skipped:
            lines.append(f"  SKIP {s}")
        for e in self.errors:
            lines.append(f"  ERR {e}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------


def _locks_dir() -> Path:
    d = Path(
        os.environ.get("LEVI_SCHEDULER_LOCKS_DIR")
        or str(Path.home() / ".levi" / "agent_scheduler" / "locks")
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def _acquire_lock(automation_id: str) -> bool:
    """True when we now hold the lock. Stale locks (>TTL) are cleared."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in automation_id)
    path = _locks_dir() / f"{safe}.lock"
    now = time.time()
    if path.exists():
        try:
            stamp = float(path.read_text(encoding="utf-8").split(":")[0])
            if now - stamp < LOCK_TTL_SECONDS:
                return False  # held by a live run
        except (ValueError, OSError):
            pass  # unreadable lock counts as stale
    try:
        path.write_text(f"{now}:{os.getpid()}", encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock(automation_id: str) -> None:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in automation_id)
    try:
        (_locks_dir() / f"{safe}.lock").unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# The tick
# ---------------------------------------------------------------------------


def _registry(data_dir: str | Path | None = None):
    override = os.environ.get("LEVI_AUTOMATIONS_DIR")
    from levi.daemon.automation import AutomationRegistry

    if data_dir is not None:
        return AutomationRegistry(data_dir=Path(data_dir))
    if override:
        return AutomationRegistry(data_dir=Path(override))
    return AutomationRegistry()


def fire_due(
    *,
    now: datetime | None = None,
    data_dir: str | Path | None = None,
    provider: Any = None,
    consent: bool = True,
    max_steps: int = 10,
    max_tasks: int = DEFAULT_MAX_TASKS,
    workspace_root: str | Path | None = None,
) -> SchedulerReport:
    """Fire every due scheduled automation exactly once for this minute.

    Each due automation's ``task`` (from its trigger config) runs through
    :func:`levi.agent.loop.run_subtask` with the default tool registry.
    Results persist on the automation record. ``consent`` pre-grants the
    human-in-the-loop gates for these runs — the caller owns that
    decision (Chauncey's personal agent runs with his standing consent;
    other callers should pass ``consent=False`` and a confirm callback
    path of their own).
    """
    from levi.daemon.automation import AutomationStatus, TriggerKind

    report = SchedulerReport()
    when = now or datetime.now(timezone.utc)
    minute_key = when.strftime("%Y-%m-%dT%H:%M")

    try:
        reg = _registry(data_dir)
    except Exception as exc:
        report.errors.append(f"registry unavailable: {exc}")
        return report

    try:
        items = reg.list()
    except Exception as exc:
        report.errors.append(f"registry list failed: {exc}")
        return report

    due: list[Any] = []
    for auto in items:
        try:
            if auto.status != AutomationStatus.ACTIVE:
                continue
            if auto.trigger != TriggerKind.SCHEDULE:
                continue
            cfg = auto.trigger_config or {}
            cron = str(cfg.get("cron") or "").strip()
            task = str(cfg.get("task") or "").strip()
            if not cron:
                report.skipped.append(f"{auto.id}: no cron expression")
                continue
            if not task:
                report.skipped.append(f"{auto.id}: empty task")
                continue
            if not cron_matches(cron, when):
                continue
            if (auto.last_run or "")[:16] == minute_key[:16]:
                report.skipped.append(f"{auto.id}: already fired this minute")
                continue
            due.append(auto)
        except Exception as exc:  # one bad record never stops the tick
            report.errors.append(f"{getattr(auto, 'id', '?')}: scan error: {exc}")

    for auto in due[:max_tasks]:
        if not _acquire_lock(auto.id):
            report.skipped.append(f"{auto.id}: another run holds the lock")
            continue
        try:
            task = str((auto.trigger_config or {}).get("task") or "")
            outcome = _run_task(task, provider=provider, consent=consent,
                               max_steps=max_steps, workspace_root=workspace_root)
            auto.last_run = when.isoformat()
            auto.last_result = outcome[:500]
            auto.run_count = (auto.run_count or 0) + 1
            try:
                reg._persist()
            except Exception as exc:
                report.errors.append(f"{auto.id}: persist failed: {exc}")
            report.fired.append(
                FiredTask(
                    automation_id=auto.id,
                    name=auto.name,
                    ok=outcome.startswith("OK:"),
                    summary=outcome[3:],
                )
            )
        except Exception as exc:
            report.errors.append(f"{auto.id}: fired but crashed: {exc}")
        finally:
            _release_lock(auto.id)

    if len(due) > max_tasks:
        report.skipped.append(
            f"{len(due) - max_tasks} due automation(s) over the per-tick cap"
        )
    return report


def _run_task(task: str, *, provider: Any, consent: bool, max_steps: int,
              workspace_root: str | Path | None = None) -> str:
    """Run one scheduled task through the agentic loop. Returns 'OK: ...'
    or 'FAIL: ...' — never raises."""
    try:
        from levi.agent.loop import run_subtask
        from levi.agent.tools import build_default_registry

        registry = build_default_registry(
            workspace_root=Path(workspace_root) if workspace_root else None,
            consent=consent,
        )
        transcript = run_subtask(
            task,
            provider=provider,
            registry=registry,
            consent=consent,
            max_steps=max_steps,
        )
        status = "OK" if transcript.ok else "FAIL"
        final = (transcript.final or "").strip().replace("\n", " ")
        return f"{status}: {final[:400]}"
    except Exception as exc:
        return f"FAIL: {exc}"
