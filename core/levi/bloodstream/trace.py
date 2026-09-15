"""Decision traces — the self-sufficiency corpus, one JSONL line per turn.

Traces record the decision path of every bloodstream turn: which stages
ran, what each decided, which provider/model answered (or that the
deterministic offline fallback did), which skills fired, and the policy
receipt id. This is the beginning of the observability gap fill: minimal,
append-only, local-first.

Location: ``~/.levi/traces/YYYY-MM-DD.jsonl`` (or ``data_dir/traces/`` when
a TurnContext overrides the home directory, e.g. in tests).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def default_traces_dir() -> Path:
    return Path.home() / ".levi" / "traces"


class TraceWriter:
    """Append-only JSONL writer. Never raises into the turn pipeline."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else default_traces_dir()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # write() will report the failure; never raise into the turn

    def _path_for(self, day: Optional[str] = None) -> Path:
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.base_dir / f"{day}.jsonl"

    def write(self, trace: Dict[str, Any]) -> Optional[Path]:
        """Append one trace record. Returns the file path, or None on failure."""
        record = dict(trace)
        record.setdefault("trace_id", new_trace_id())
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        try:
            path = self._path_for()
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
            return path
        except OSError:
            return None

    def read_day(self, day: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read back one day's traces (for tests / inspection)."""
        path = self._path_for(day)
        out: List[Dict[str, Any]] = []
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except OSError:
            pass
        return out


# Required trace fields — every turn must supply all of these.
TRACE_FIELDS = (
    "trace_id",
    "ts",
    "session_id",
    "text_excerpt",
    "stages",            # [{stage, decision, detail}]
    "provider",          # provider/model actually used, or "deterministic-fallback"
    "skills_invoked",    # [skill ids]
    "policy_receipt_id",  # None when no consequential act ran
    "risk_level",        # int 0-4
    "route",             # RouteKind value
    "outcome",           # "replied" | "awaiting_permission" | "governed" | "failed"
    "error",             # None or short error string
    "composted",         # failure compost record or None
)
