"""TraceStore — the append-only decision-trace corpus.

Layout: ``<base_dir>/traces-YYYY-MM-DD.jsonl``, one JSON object per line,
rotated by date (UTC). Default ``base_dir`` is ``~/.levi/observability``,
created owner-only (``0o700``); trace files are created ``0o600``.

Writes never raise into the turn pipeline: :meth:`append` returns the
file path or ``None`` on failure. Reads skip corrupt lines individually —
one bad line never aborts a query.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from levi.observability.schema import TurnTrace

_DAY_RE = re.compile(r"^traces-(\d{4}-\d{2}-\d{2})\.jsonl$")


def default_store_dir() -> Path:
    return Path.home() / ".levi" / "observability"


class TraceStore:
    """Append-only JSONL store + query surface for TurnTrace records."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else default_store_dir()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            # mkdir's mode is masked by umask; enforce owner-only explicitly.
            os.chmod(self.base_dir, 0o700)
        except OSError:
            pass  # append() reports failure; never raise into the turn

    # -- writes --------------------------------------------------------

    def _path_for(self, day: Optional[str] = None) -> Path:
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.base_dir / f"traces-{day}.jsonl"

    def append(self, trace: TurnTrace) -> Optional[Path]:
        """Append one trace. Returns the file path, or None on failure."""
        if not isinstance(trace, TurnTrace):
            return None
        path = self._path_for()
        line = json.dumps(trace.to_dict(), default=str) + "\n"
        try:
            # O_CREAT with 0o600: brand-new files are owner-only even when
            # the process umask is permissive. Existing files keep mode.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                with os.fdopen(fd, "a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError:
                os.close(fd)
                raise
            return path
        except OSError:
            return None

    # -- reads ---------------------------------------------------------

    def read_day(self, day: Optional[str] = None) -> List[TurnTrace]:
        """All traces for one day (UTC), oldest first. Skips bad lines."""
        path = self._path_for(day)
        out: List[TurnTrace] = []
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        try:
                            out.append(TurnTrace.from_dict(record))
                        except (TypeError, ValueError):
                            continue
        except OSError:
            pass
        return out

    def days(self) -> List[str]:
        """Day labels present in the store, oldest first."""
        found: List[str] = []
        try:
            for entry in self.base_dir.iterdir():
                m = _DAY_RE.match(entry.name)
                if m and entry.is_file():
                    found.append(m.group(1))
        except OSError:
            pass
        return sorted(found)

    def _scan(self, limit: Optional[int] = None) -> List[TurnTrace]:
        """All traces, newest first (across day files)."""
        traces: List[TurnTrace] = []
        for day in reversed(self.days()):
            day_traces = self.read_day(day)
            traces.extend(reversed(day_traces))  # newest line first
            if limit is not None and len(traces) >= limit:
                break
        return traces[:limit] if limit is not None else traces

    def recent(self, limit: int = 20) -> List[TurnTrace]:
        """Newest ``limit`` traces across all days, newest first."""
        return self._scan(limit=limit)

    def get(self, turn_id: str) -> Optional[TurnTrace]:
        """Fetch one trace by turn id (scans newest-first)."""
        for trace in self._scan():
            if trace.turn_id == turn_id:
                return trace
        return None

    def filter(
        self,
        *,
        outcome: Optional[str] = None,
        min_risk: Optional[int] = None,
        route: Optional[str] = None,
        limit: int = 50,
    ) -> List[TurnTrace]:
        """Query the corpus. All filters are ANDed; newest first."""
        out: List[TurnTrace] = []
        for trace in self._scan():
            if outcome is not None and trace.outcome != outcome:
                continue
            if min_risk is not None and trace.risk_ceiling < min_risk:
                continue
            if route is not None and trace.route != route:
                continue
            out.append(trace)
            if len(out) >= limit:
                break
        return out

    def stats(self) -> dict:
        """Corpus census: days, total traces, outcome/risk breakdowns."""
        by_outcome: dict = {}
        by_risk: dict = {}
        total = 0
        for trace in self._scan():
            total += 1
            by_outcome[trace.outcome] = by_outcome.get(trace.outcome, 0) + 1
            key = str(trace.risk_ceiling)
            by_risk[key] = by_risk.get(key, 0) + 1
        return {
            "days": self.days(),
            "total": total,
            "by_outcome": by_outcome,
            "by_risk": by_risk,
        }
