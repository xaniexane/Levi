"""Coroner — the crash-digest daemon for the perpetual supervisor.

The supervisor (``levi.perpetual.supervise``) persists one CrashReport JSON
per child crash under ``~/.levi/perpetual/crashes/``::

    {"child": "levi-heartbeat", "exc_type": "ValueError",
     "message": "...", "traceback": "...",
     "at": <epoch float>, "at_iso": "<iso>",
     "restart_count": <int>}

Coroner rolls those reports into a digest the operator can act on:

- per-service crash counts, last crash time, last error class
- repeat offenders: >= 3 crashes inside the trailing 24 hours
- restart-limit notice: a service whose latest report is at the
  supervisor's give-up intensity (default 5 restarts / 300 s) is one the
  supervisor stopped honestly instead of spinning

Deny-closed on the report files: a file that is not JSON, or JSON that
lacks the report shape, is *counted as skipped* — never as a crash and
never as a fatal error. A corrupt report must not crash the crash reader.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.coroner`` inside the perpetual supervisor
(one_for_one child), or a plain ``run_once()`` call from cron.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CRASH_DIR = Path.home() / ".levi" / "perpetual" / "crashes"

#: Supervisor's default give-up intensity (matches supervise.build_supervisor).
RESTART_LIMIT = 5
REPEAT_THRESHOLD = 3
REPEAT_WINDOW = timedelta(hours=24)


class CoronerError(ValueError):
    """Deny-closed input to the coroner itself (bad directory, bad window)."""


@dataclass
class ServiceDigest:
    """What the coroner knows about one service's crashes."""

    service: str
    crashes: int = 0
    last_at_iso: str = ""
    last_exc: str = ""
    at_restart_limit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "crashes": self.crashes,
            "last_at_iso": self.last_at_iso,
            "last_exc": self.last_exc,
            "at_restart_limit": self.at_restart_limit,
        }


@dataclass
class CrashDigest:
    """The whole digest: what crashed, how often, who is chronic."""

    total_reports: int = 0
    skipped_files: int = 0
    services: Dict[str, ServiceDigest] = field(default_factory=dict)
    repeat_offenders: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_reports": self.total_reports,
            "skipped_files": self.skipped_files,
            "services": {k: v.to_dict() for k, v in self.services.items()},
            "repeat_offenders": list(self.repeat_offenders),
        }


def _looks_like_report(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("child"), str)
        and payload["child"]
        and isinstance(payload.get("at"), (int, float))
    )


def load_reports(
    crashes_dir: "str | os.PathLike[str] | None" = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Load crash reports; returns (reports, skipped_file_count).

    Corrupt or misshapen files are skipped and counted, never fatal.
    """
    directory = Path(crashes_dir) if crashes_dir else DEFAULT_CRASH_DIR
    if not directory.is_dir():
        raise CoronerError(f"coroner: crash directory '{directory}' is not a directory")
    reports: List[Dict[str, Any]] = []
    skipped = 0
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or entry.suffix != ".json":
            continue
        try:
            payload = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped += 1
            continue
        if _looks_like_report(payload):
            reports.append(payload)
        else:
            skipped += 1
    return reports, skipped


def digest_reports(
    reports: List[Dict[str, Any]],
    skipped: int = 0,
    now: Optional[datetime] = None,
) -> CrashDigest:
    """Roll raw reports into a CrashDigest."""
    moment = now or datetime.now(timezone.utc)
    digest = CrashDigest(total_reports=len(reports), skipped_files=skipped)
    window_start = moment - REPEAT_WINDOW
    window_counts: Dict[str, int] = {}
    for rep in reports:
        name = rep["child"]
        svc = digest.services.get(name)
        if svc is None:
            svc = ServiceDigest(service=name)
            digest.services[name] = svc
        svc.crashes += 1
        at_iso = rep.get("at_iso") or ""
        if at_iso >= svc.last_at_iso:
            svc.last_at_iso = at_iso
            svc.last_exc = str(rep.get("exc_type") or "unknown")
            try:
                svc.at_restart_limit = (
                    int(rep.get("restart_count") or 0) >= RESTART_LIMIT
                )
            except (TypeError, ValueError):
                svc.at_restart_limit = False
        try:
            at = datetime.fromtimestamp(float(rep["at"]), timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        if at >= window_start:
            window_counts[name] = window_counts.get(name, 0) + 1
            if (
                window_counts[name] == REPEAT_THRESHOLD
                and name not in digest.repeat_offenders
            ):
                digest.repeat_offenders.append(name)
    digest.repeat_offenders.sort()
    return digest


def render_digest(digest: CrashDigest) -> str:
    """Render the digest as a plain-text card."""
    lines = ["Crash digest", "============"]
    lines.append(
        f"reports: {digest.total_reports}  skipped files: {digest.skipped_files}"
    )
    if not digest.services:
        lines.append("no crashes on record — the supervisor is quiet")
        return "\n".join(lines)
    for name in sorted(digest.services):
        svc = digest.services[name]
        flag = "  [AT RESTART LIMIT — supervisor stopped this one honestly]"
        lines.append(
            f"- {name}: {svc.crashes} crash(es), last {svc.last_at_iso or 'n/a'} "
            f"({svc.last_exc})" + (flag if svc.at_restart_limit else "")
        )
    if digest.repeat_offenders:
        lines.append(
            "repeat offenders (>= %d in 24h): %s"
            % (REPEAT_THRESHOLD, ", ".join(digest.repeat_offenders))
        )
    return "\n".join(lines)


def run_once(crashes_dir: "str | os.PathLike[str] | None" = None) -> int:
    """One digest pass: load, digest, print. Returns 0."""
    reports, skipped = load_reports(crashes_dir)
    digest = digest_reports(reports, skipped)
    print(render_digest(digest))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: ``python -m levi.daemon.coroner [--crash-dir DIR]``."""
    parser = argparse.ArgumentParser(
        description="Digest perpetual-supervisor crash reports."
    )
    parser.add_argument("--crash-dir", default=None, help="Crash report directory")
    args = parser.parse_args(argv)
    return run_once(args.crash_dir)


if __name__ == "__main__":
    raise SystemExit(main())
