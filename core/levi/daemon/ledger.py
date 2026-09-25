"""LEVI daemon ledger — a local-first resource logbook for the machine.

The machine should be able to say, honestly, how hard it has been working.
The ledger daemon appends small JSONL samples (load averages, CPU count,
disk usage of the home dir) to ``~/.levi/daemon/ledger.jsonl`` and can
summarize any trailing window: averages plus honest threshold flags.

Everything is stdlib-only: :func:`os.getloadavg`, :func:`os.cpu_count`,
:func:`shutil.disk_usage`. No psutil, no syscalls beyond what the platform
guarantees. On platforms without load averages the load fields record
``null`` and the summary says so rather than inventing numbers.

Deny-closed: negative windows, unknown paths, and unparseable config are
refused with a named error, never coerced.

Usage::

    from levi.daemon.ledger import sample, summarize

    sample()                       # append one sample to the default ledger
    report = summarize(hours=6)     # windowed averages + threshold flags
    print(report.disk_pct_avg)

Run it: ``python -m levi.daemon.ledger sample`` / ``report --hours 6``
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "LedgerError",
    "Sample",
    "LedgerReport",
    "DEFAULT_LEDGER",
    "LOAD_FLAG_RATIO",
    "DISK_FLAG_PCT",
    "sample",
    "read_samples",
    "summarize",
]

#: Default append-only ledger path.
DEFAULT_LEDGER = Path.home() / ".levi" / "daemon" / "ledger.jsonl"

#: Flag load when the 1-minute average exceeds this fraction of cpu_count.
LOAD_FLAG_RATIO = 0.9

#: Flag disk when used percent reaches this.
DISK_FLAG_PCT = 90.0


class LedgerError(ValueError):
    """Raised when ledger inputs fail validation."""


@dataclass(frozen=True)
class Sample:
    """One resource snapshot."""

    ts: float
    load1: Optional[float]
    load5: Optional[float]
    load15: Optional[float]
    cpu_count: Optional[int]
    disk_used_gb: float
    disk_total_gb: float
    disk_pct: float

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "load1": self.load1,
            "load5": self.load5,
            "load15": self.load15,
            "cpu_count": self.cpu_count,
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "disk_pct": round(self.disk_pct, 1),
        }

    @staticmethod
    def from_dict(data: dict) -> "Sample":
        try:
            return Sample(
                ts=float(data["ts"]),
                load1=None if data.get("load1") is None else float(data["load1"]),
                load5=None if data.get("load5") is None else float(data["load5"]),
                load15=None if data.get("load15") is None else float(data["load15"]),
                cpu_count=None
                if data.get("cpu_count") is None
                else int(data["cpu_count"]),
                disk_used_gb=float(data["disk_used_gb"]),
                disk_total_gb=float(data["disk_total_gb"]),
                disk_pct=float(data["disk_pct"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerError(f"bad sample record: {exc}") from exc


def _probe_load() -> Dict[str, Optional[float]]:
    try:
        one, five, fifteen = os.getloadavg()
        return {"load1": one, "load5": five, "load15": fifteen}
    except (OSError, AttributeError):
        return {"load1": None, "load5": None, "load15": None}


def sample(ledger: Optional[Path] = None, path: Optional[Path] = None) -> Sample:
    """Take one snapshot and append it. Returns the sample."""
    target = Path(ledger) if ledger is not None else DEFAULT_LEDGER
    disk_root = Path(path) if path is not None else Path.home()
    if not disk_root.exists():
        raise LedgerError(f"disk path does not exist: {disk_root}")
    usage = shutil.disk_usage(disk_root)
    pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    loads = _probe_load()
    record = Sample(
        ts=time.time(),
        load1=loads["load1"],
        load5=loads["load5"],
        load15=loads["load15"],
        cpu_count=os.cpu_count(),
        disk_used_gb=usage.used / 1e9,
        disk_total_gb=usage.total / 1e9,
        disk_pct=pct,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return record


def read_samples(
    ledger: Optional[Path] = None,
    since: Optional[float] = None,
) -> List[Sample]:
    """Read samples (optionally newer than ``since``). Malformed lines are skipped honestly."""
    target = Path(ledger) if ledger is not None else DEFAULT_LEDGER
    if not target.exists():
        return []
    out: List[Sample] = []
    skipped = 0
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = Sample.from_dict(json.loads(line))
        except (json.JSONDecodeError, LedgerError):
            skipped += 1
            continue
        if since is not None and record.ts < since:
            continue
        out.append(record)
    out.sort(key=lambda s: s.ts)
    return out


@dataclass(frozen=True)
class LedgerReport:
    """Windowed summary over the ledger."""

    samples: int
    load1_avg: Optional[float] = None
    load5_avg: Optional[float] = None
    load15_avg: Optional[float] = None
    load_flagged: bool = False
    load_note: str = ""
    disk_pct_avg: Optional[float] = None
    disk_flagged: bool = False
    cpu_count: Optional[int] = None

    def flagged(self) -> bool:
        return self.load_flagged or self.disk_flagged


def _avg(values: List[Optional[float]]) -> Optional[float]:
    real = [v for v in values if v is not None]
    return sum(real) / len(real) if real else None


def summarize(
    hours: float = 24.0,
    ledger: Optional[Path] = None,
    now: Optional[float] = None,
) -> LedgerReport:
    """Summarize the trailing ``hours`` window. Refuses bad windows."""
    if isinstance(hours, bool) or not isinstance(hours, (int, float)):
        raise LedgerError(f"hours must be a number, got {hours!r}")
    if hours <= 0:
        raise LedgerError(f"hours must be > 0, got {hours}")
    moment = time.time() if now is None else float(now)
    records = read_samples(ledger, since=moment - hours * 3600.0)
    if not records:
        return LedgerReport(samples=0, load_note="no samples in window")

    load1 = _avg([r.load1 for r in records])
    load5 = _avg([r.load5 for r in records])
    load15 = _avg([r.load15 for r in records])
    disk_avg = _avg([r.disk_pct for r in records])
    cpu = records[-1].cpu_count

    load_flagged = False
    note = ""
    if load1 is None:
        note = "load averages unavailable on this platform"
    elif cpu and load1 > cpu * LOAD_FLAG_RATIO:
        load_flagged = True
        note = f"load1 {load1:.2f} exceeds {LOAD_FLAG_RATIO * 100:.0f}% of {cpu} cpus"
    disk_flagged = disk_avg is not None and disk_avg >= DISK_FLAG_PCT

    return LedgerReport(
        samples=len(records),
        load1_avg=load1,
        load5_avg=load5,
        load15_avg=load15,
        load_flagged=load_flagged,
        load_note=note,
        disk_pct_avg=disk_avg,
        disk_flagged=disk_flagged,
        cpu_count=cpu,
    )


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.daemon.ledger",
        description="Local-first resource logbook: sample the machine, report the window.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="append one resource sample to the ledger")
    rep = sub.add_parser("report", help="summarize the trailing window")
    rep.add_argument("--hours", type=float, default=24.0)
    args = ap.parse_args(argv)

    if args.cmd == "sample":
        record = sample()
        print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
        return 0
    report = summarize(hours=args.hours)
    print(f"samples: {report.samples}")
    if report.samples == 0:
        print(report.load_note)
        return 0
    print(f"load1 avg: {report.load1_avg}")
    print(f"load5 avg: {report.load5_avg}")
    print(f"load15 avg: {report.load15_avg}")
    print(f"disk used avg: {report.disk_pct_avg}%")
    if report.load_note:
        print(f"load note: {report.load_note}")
    print(f"flagged: {report.flagged()}")
    return 2 if report.flagged() else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
