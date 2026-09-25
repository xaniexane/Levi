"""Metronome — the pacing daemon.

The perpetual supervisor runs three local services (heartbeat every 60
min, growth every 6 h, automation ticks every 5 min). Left alone they
thunder-herd: everything fires at the same wall-clock minute and the
machine spikes. The metronome assigns every recurring job a deterministic
slot inside its interval — ``phase = sha256(name) / 2**256`` — so jobs
spread evenly without any coordination protocol, and it is stable across
restarts because the phase is a pure function of the name.

:class:`Metronome` is the pure scheduler: given a tick map of
``job -> {"at", "grid"}`` and ``now``, :meth:`due` returns the jobs
whose slot has arrived, sorted by lateness, and :meth:`tick` claims the
due jobs and persists the new ticks to an owner-only JSON file. Clocks
are injected (``now`` is a float), so the logic never sleeps and the
tests never flake.

The three perpetual services ship pre-registered via
:func:`default_jobs`; ``run()`` is the long-run entry
(``python3 -m levi.daemon.metronome``) looping ``tick()`` once per
minute. :func:`spread_report` honestly measures how well the slots are
separated instead of claiming a perfect stagger.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "JobSpec",
    "Tick",
    "Metronome",
    "default_jobs",
    "phase_for",
    "slot_offset",
    "spread_report",
    "state_dir",
    "tick_path",
    "status",
    "tick",
    "run",
    "main",
]


# ------------------------------------------------------------------ home


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def state_dir() -> Path:
    return _home() / "metronome"


def tick_path() -> Path:
    return state_dir() / "ticks.json"


def _owner_only_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def _write_owner_only(path: Path, payload: Dict[str, Any]) -> None:
    _owner_only_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, path)


# -------------------------------------------------------------- scheduling


def phase_for(name: str) -> float:
    """Deterministic slot phase in [0, 1) — pure function of the job name."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest, "big") / 2**256


def slot_offset(name: str, interval_sec: float) -> float:
    """Seconds into the interval where this job's slot lands."""
    return phase_for(name) * interval_sec


def _grid_index(name: str, interval_sec: float, at: float) -> int:
    """Phase-shifted slot grid: the k-th slot lands at k*I + s."""
    return math.floor((at - slot_offset(name, interval_sec)) / interval_sec)


def _slot_time(name: str, interval_sec: float, k: int) -> float:
    return k * interval_sec + slot_offset(name, interval_sec)


@dataclass
class JobSpec:
    """One recurring job the metronome paces."""

    name: str
    interval_sec: float
    description: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("JobSpec needs a non-empty name")
        if self.interval_sec <= 0:
            raise ValueError("interval_sec must be positive")


@dataclass
class Tick:
    """A claimed slot: job ran (or was honestly skipped) at ``at``."""

    job: str
    at: float
    claimed: bool = True
    note: str = ""


def default_jobs() -> List[JobSpec]:
    """The three perpetual services, straight from docs/PERPETUAL.md."""
    return [
        JobSpec("levi-heartbeat", 3600, "periodic self-check"),
        JobSpec("levi-growth", 6 * 3600, "offline growth tick"),
        JobSpec("levi-automation", 300, "due SCHEDULE bot automations"),
    ]


class Metronome:
    """Pure pacing scheduler. No I/O except where named otherwise."""

    def __init__(self, jobs: Optional[List[JobSpec]] = None) -> None:
        self.jobs: Dict[str, JobSpec] = {}
        for job in jobs or default_jobs():
            self.register(job)

    # -- registration -------------------------------------------------
    def register(self, job: JobSpec) -> None:
        if job.name in self.jobs:
            raise ValueError(f"job already registered: {job.name!r}")
        self.jobs[job.name] = job

    # -- ticks (I/O) --------------------------------------------------
    def load_ticks(self) -> Dict[str, Dict[str, float]]:
        """``{job: {"at": timestamp, "grid": slot index}}``; tolerates legacy floats."""
        path = tick_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        raw = data.get("ticks", {}) if isinstance(data, dict) else {}
        ticks: Dict[str, Dict[str, float]] = {}
        for name, value in raw.items():
            job = self.jobs.get(name)
            if job is None:
                continue
            if isinstance(value, dict) and "grid" in value:
                ticks[name] = {
                    "at": float(value.get("at", 0.0)),
                    "grid": int(value["grid"]),
                }
            elif isinstance(value, (int, float)):
                at = float(value)
                ticks[name] = {
                    "at": at,
                    "grid": _grid_index(name, job.interval_sec, at),
                }
        return ticks

    def save_ticks(self, ticks: Dict[str, Dict[str, float]]) -> None:
        _write_owner_only(tick_path(), {"ticks": ticks, "saved_at": time.time()})

    # -- scheduling ---------------------------------------------------
    def due_in(
        self, job: JobSpec, now: float, ticks: Dict[str, Dict[str, float]]
    ) -> float:
        """Seconds until this job's next slot (<= 0 means due now).

        Slots live on a phase-shifted grid: the k-th slot for a job with
        interval I and phase p lands at ``k*I + p*I``. The job is due when
        the current grid index has advanced past the last claimed one.
        A job never ticked is due immediately — on a fresh machine the
        first tick baselines everything onto its own slot.
        """
        last = ticks.get(job.name)
        if last is None:
            return 0.0
        cur = _grid_index(job.name, job.interval_sec, now)
        if cur > last["grid"]:
            return 0.0
        return _slot_time(job.name, job.interval_sec, last["grid"] + 1) - now

    def due(self, now: float, ticks: Dict[str, Dict[str, float]]) -> List[Tick]:
        """All due jobs, sorted by lateness (most overdue first)."""
        due: List[Tick] = []
        for name, job in self.jobs.items():
            if not job.enabled:
                continue
            remaining = self.due_in(job, now, ticks)
            if remaining <= 0:
                last = ticks.get(name)
                grid = _grid_index(job.name, job.interval_sec, now)
                overdue = (
                    0.0
                    if last is None
                    else max(0.0, now - _slot_time(job.name, job.interval_sec, grid))
                )
                due.append(
                    Tick(job=name, at=now, note=f"slot {grid}, overdue {overdue:.1f}s")
                )
        due.sort(key=lambda t: ticks.get(t.job, {}).get("at", 0.0))
        return due

    def tick(self, now: Optional[float] = None) -> List[Tick]:
        """Claim every due job and persist the new ticks. The loop body."""
        now = time.time() if now is None else now
        ticks = self.load_ticks()
        due = self.due(now, ticks)
        for t in due:
            job = self.jobs[t.job]
            ticks[t.job] = {
                "at": t.at,
                "grid": _grid_index(job.name, job.interval_sec, t.at),
            }
        if due:
            self.save_ticks(ticks)
        return due

    def status(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """One row per job: next slot in seconds, slot phase, enabled."""
        now = time.time() if now is None else now
        ticks = self.load_ticks()
        rows: List[Dict[str, Any]] = []
        for name, job in sorted(self.jobs.items()):
            remaining = self.due_in(job, now, ticks)
            rows.append(
                {
                    "job": name,
                    "enabled": job.enabled,
                    "interval_sec": job.interval_sec,
                    "slot_phase": round(phase_for(name), 4),
                    "due_in_sec": round(remaining, 1),
                    "state": "due" if remaining <= 0 else "waiting",
                    "description": job.description,
                }
            )
        return rows


def spread_report(jobs: Optional[List[JobSpec]] = None) -> Dict[str, Any]:
    """Honest measurement: how far apart are same-interval slots?

    Returns, per interval, the minimum pairwise gap between slot offsets
    as a fraction of the interval. Small numbers mean two jobs still
    collide; the report says so instead of claiming a perfect stagger.
    """
    jobs = jobs or default_jobs()
    by_interval: Dict[float, List[str]] = {}
    for job in jobs:
        by_interval.setdefault(job.interval_sec, []).append(job.name)
    gaps: Dict[str, float] = {}
    for interval, names in sorted(by_interval.items()):
        if len(names) < 2:
            gaps[str(interval)] = 1.0
            continue
        offsets = sorted(slot_offset(n, interval) for n in names)
        diffs = [b - a for a, b in zip(offsets, offsets[1:], strict=False)]
        diffs.append(offsets[0] + interval - offsets[-1])  # wraparound
        gaps[str(interval)] = round(min(diffs) / interval, 4)
    return {"intervals": gaps, "jobs": [asdict(j) for j in jobs]}


# ------------------------------------------------------------------ loop


def tick(now: Optional[float] = None) -> List[Dict[str, Any]]:
    """Claim due jobs; return the claimed ticks as dicts (loop body)."""
    return [asdict(t) for t in Metronome().tick(now)]


def status(now: Optional[float] = None) -> List[Dict[str, Any]]:
    """One status row per registered job (next slot, phase, state)."""
    return Metronome().status(now)


def run(poll_sec: float = 60.0, stop_after: Optional[int] = None) -> None:
    """Long-run entry: tick every ``poll_sec`` until interrupted."""
    metro = Metronome()
    count = 0
    while True:
        due = metro.tick()
        for t in due:
            print(f"[metronome] claimed slot: {t.job} ({t.note})", flush=True)
        count += 1
        if stop_after is not None and count >= stop_after:
            break
        time.sleep(poll_sec)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="levi.daemon.metronome", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="table of jobs and next slots")
    sub.add_parser("spread", help="honest slot-separation report")
    tick_p = sub.add_parser("tick", help="claim due jobs once")
    tick_p.add_argument("--dry-run", action="store_true")
    run_p = sub.add_parser("run", help="long-run loop (default 60s poll)")
    run_p.add_argument("--poll-sec", type=float, default=60.0)
    args = ap.parse_args(argv)

    metro = Metronome()
    if args.cmd == "status":
        for row in metro.status():
            print(
                f"{row['job']:18s} {row['state']:7s} "
                f"due_in={row['due_in_sec']:>9.1f}s phase={row['slot_phase']}"
            )
    elif args.cmd == "spread":
        print(json.dumps(spread_report(), indent=2))
    elif args.cmd == "tick":
        if args.dry_run:
            print(
                json.dumps(
                    [asdict(t) for t in metro.due(time.time(), metro.load_ticks())],
                    indent=2,
                )
            )
        else:
            for t in metro.tick():
                print(f"claimed: {t.job} ({t.note})")
    elif args.cmd == "run":
        run(args.poll_sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
