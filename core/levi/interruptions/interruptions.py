"""LEVI interruption ledger — every interruption weighed against its value.

Every system interruption LEVI produces is logged with a value verdict:

* ``"useful"`` — the interruption delivered value (alert worth acting on).
* ``"noise"`` — the interruption delivered nothing.
* ``"mixed"`` — some value, some noise.

:func:`noise_roi` computes a weekly noise report: counts, noise ratio, the
noisiest sources, and a one-line verdict. The verdict is honest about empty
data: with nothing logged it says so, instead of presenting zeros as
insight.

``check()`` surfaces a weekly NUDGE-grade card dict for the instincts
engine (plain-string grade, no import of any signal package).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "InterruptionError",
    "InterruptionLedger",
    "noise_roi",
    "check",
    "VALUES",
]

VALUES = ("useful", "noise", "mixed")


class InterruptionError(Exception):
    """Raised for invalid interruption operations (bad value, bad window)."""


def _levi_home() -> Path:
    """LEVI home, resolved at CALL time (never cached at import)."""
    env = os.environ.get("LEVI_HOME")
    if env and env.strip():
        return Path(env).expanduser()
    home = os.environ.get("HOME")
    if home and home.strip():
        return Path(home)
    return Path.home()


def _stamp(at: Optional[datetime] = None) -> str:
    dt = at if at is not None else datetime.now(timezone.utc)
    if dt.tzinfo is None:
        # Naive datetimes are local time, not UTC.
        dt = dt.astimezone()
    return dt.isoformat()


def _parse_at(at: Optional[datetime]) -> datetime:
    if at is None:
        return datetime.now(timezone.utc)
    if not isinstance(at, datetime):
        raise InterruptionError("at must be a datetime, got %r" % (at,))
    if at.tzinfo is None:
        # Naive datetimes are local time, not UTC.
        return at.astimezone()
    return at


class InterruptionLedger:
    """Persistent interruption ledger under the LEVI home."""

    def __init__(self, home: Optional[Union[str, Path]] = None) -> None:
        self.home = Path(home) if home is not None else _levi_home()
        self.path = self.home / ".levi" / "interruptions" / "interruptions.jsonl"

    # -- persistence ------------------------------------------------------
    def _read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue  # skip corrupt lines, never crash the ledger
        return entries

    def _append(self, entry: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")

    # -- logging ----------------------------------------------------------
    def log(
        self, source: str, summary: str, value: str, at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Log one interruption. ``value`` is useful/noise/mixed."""
        source = (source or "").strip()
        summary = (summary or "").strip()
        value = (value or "").strip().lower()
        if not source:
            raise InterruptionError("an interruption needs a source")
        if not summary:
            raise InterruptionError("an interruption needs a summary")
        if value not in VALUES:
            raise InterruptionError("value must be one of %s, got %r" % (VALUES, value))
        entry = {
            "source": source,
            "summary": summary,
            "value": value,
            "at": _stamp(_parse_at(at)),
        }
        self._append(entry)
        return dict(entry)

    def entries(
        self, days: Optional[int] = None, now: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """All entries, or those within the last ``days``."""
        all_entries = self._read_all()
        if days is None:
            return all_entries
        if days <= 0:
            raise InterruptionError("days must be positive")
        cutoff = _parse_at(now) - timedelta(days=days)
        return [e for e in all_entries if datetime.fromisoformat(e["at"]) >= cutoff]

    # -- ROI --------------------------------------------------------------
    def noise_roi(
        self, days: int = 7, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Weekly (default) noise report: counts, ratio, noisiest, verdict.

        Empty state is honest: the verdict says nothing was logged instead
        of presenting zeros as insight.
        """
        if days <= 0:
            raise InterruptionError("days must be positive")
        now_dt = _parse_at(now)
        start = now_dt - timedelta(days=days)
        rows = self.entries(days=days, now=now_dt)

        counts = {"useful": 0, "noise": 0, "mixed": 0}
        per_source: Dict[str, Dict[str, int]] = {}
        for e in rows:
            counts[e["value"]] += 1
            bucket = per_source.setdefault(
                e["source"], {"useful": 0, "noise": 0, "mixed": 0}
            )
            bucket[e["value"]] += 1

        total = len(rows)
        noise_ratio = (counts["noise"] / total) if total else None

        noisy = sorted(
            (
                (s, b["noise"], b["useful"] + b["mixed"] + b["noise"])
                for s, b in per_source.items()
                if b["noise"] > 0
            ),
            key=lambda t: (-t[1], t[0]),
        )
        top_noisy_sources = [
            {"source": s, "noise": n, "total": t} for s, n, t in noisy[:5]
        ]

        report: Dict[str, Any] = {
            "days": days,
            "window_start": start.isoformat(),
            "window_end": now_dt.isoformat(),
            "counts": counts,
            "total": total,
            "noise_ratio": noise_ratio,
            "top_noisy_sources": top_noisy_sources,
        }

        if total == 0:
            report["verdict"] = (
                "nothing logged in the last %d day(s) — no verdict possible." % days
            )
        elif noise_ratio is not None and noise_ratio >= 0.5:
            top = top_noisy_sources[0]["source"]
            report["verdict"] = (
                "noisy: %d%% of interruptions were pure noise; "
                "'%s' is the loudest source — consider muting it."
                % (round(100 * noise_ratio), top)
            )
        elif noise_ratio is not None and noise_ratio >= 0.2:
            report["verdict"] = (
                "mixed: %d%% noise — mostly pulling its weight, "
                "some sources worth throttling." % round(100 * noise_ratio)
            )
        else:
            report["verdict"] = (
                "quiet: only %d%% noise — interruptions are earning "
                "their keep." % round(100 * (noise_ratio or 0.0))
            )
        return report

    # -- instincts integration surface ------------------------------------
    def check(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Weekly noise card as a plain-grade dict for the instincts engine.

        Always a single NUDGE-grade card: ``{grade, tag, title, body}``.
        """
        report = self.noise_roi(days=7, now=now)
        counts = report["counts"]
        if report["total"] == 0:
            body = (
                "No interruptions logged in the last 7 days — the "
                "ledger is empty. No verdict possible; this is a fact, "
                "not a problem."
            )
        else:
            top = (
                ", ".join(
                    "%s (%dx noise)" % (s["source"], s["noise"])
                    for s in report["top_noisy_sources"][:3]
                )
                or "none"
            )
            body = (
                "Last 7 days: %d useful · %d noise · %d mixed "
                "(noise ratio %d%%). Noisiest sources: %s. Verdict: %s"
                % (
                    counts["useful"],
                    counts["noise"],
                    counts["mixed"],
                    round(100 * (report["noise_ratio"] or 0.0)),
                    top,
                    report["verdict"],
                )
            )
        return [
            {
                "grade": "NUDGE",
                "tag": "interruptions:weekly-noise",
                "title": "Weekly noise check — interruption ROI",
                "body": body,
            }
        ]


def noise_roi(
    home: Optional[Union[str, Path]] = None,
    days: int = 7,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Module-level integration surface: weekly noise report."""
    return InterruptionLedger(home=home).noise_roi(days=days, now=now)


def check(
    home: Optional[Union[str, Path]] = None, now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Module-level integration surface for the instincts engine."""
    return InterruptionLedger(home=home).check(now=now)
