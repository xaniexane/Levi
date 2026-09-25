"""Energy-aware scheduling — learn peak hours from shipped deep work.

Learns when the user's *deep* work actually ships, then recommends time
windows for hard tasks. Everything is local JSON under the LEVI home;
nothing leaves the machine.

Honesty contract (binding):
  - ``peak_hours()`` refuses to claim peaks under ``min_sessions``
    shipped deep sessions (default 8): it returns ``enough_data: False``
    and says exactly how many more sessions are needed.
  - ``suggest_slot()`` labels every recommendation with its ``basis``:
    ``"learned"`` (from real session data) or ``"heuristic"`` (a stated
    fallback, never dressed up as learned).
  - Hours are the user's *local* hours. Sessions are recorded in local
    time on purpose: converting to UTC would silently relocate a 9am
    peak to somewhere meaningless.
  - Only *shipped* deep sessions teach the model. Sitting at a desk is
    not evidence of a peak; shipping is.

stdlib-only. Advisory: it recommends windows; it never books, blocks,
or nudges anyone but the owner.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Minimum shipped deep sessions before peaks may be claimed.
MIN_PEAK_SESSIONS = 8

# Session kinds that count toward peak learning. Deep work ships at peaks;
# admin work ships whenever.
PEAK_KINDS = ("deep",)

_STATE_DIR = "energy"
_STATE_FILE = "sessions.json"

_HARD_WEIGHTS = ("hard", "deep")
_LIGHT_WEIGHTS = ("light", "admin", "normal")


def levi_home() -> Path:
    """LEVI state home: ``$LEVI_HOME`` when set (hermetic tests), else ``~/.levi``.

    Resolved at call time — never at import — so tests can redirect it.
    """
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


@dataclass
class Session:
    """One recorded work session."""

    id: str
    start: str  # ISO-8601, local time
    end: str  # ISO-8601, local time
    kind: str  # e.g. "deep", "admin"
    shipped: bool  # did the session produce its outcome?
    duration_min: float


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(
            f"bad datetime {value!r}: use ISO-8601 like 2026-09-15T09:00"
        ) from exc


class EnergyLog:
    """Local JSON log of work sessions plus peak learning."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = Path(home).expanduser() if home is not None else levi_home()
        self._path = self.home / _STATE_DIR / _STATE_FILE

    # ------------------------------------------------------------------ I/O

    def _read(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, rows: List[Dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    # -------------------------------------------------------------- sessions

    def log_session(
        self,
        start: Any,
        end: Any,
        kind: str,
        shipped: bool,
    ) -> Session:
        """Record a session. ``shipped`` = did it produce its outcome?

        Raises ``ValueError`` on bad datetimes or a non-positive span.
        """
        s = _parse_dt(start)
        e = _parse_dt(end)
        if e <= s:
            raise ValueError("end must be after start")
        if not str(kind).strip():
            raise ValueError("kind is required (e.g. 'deep', 'admin')")
        minutes = (e - s).total_seconds() / 60.0
        session = Session(
            id="es-" + uuid.uuid4().hex[:8],
            start=s.isoformat(timespec="seconds"),
            end=e.isoformat(timespec="seconds"),
            kind=str(kind).strip().lower(),
            shipped=bool(shipped),
            duration_min=round(minutes, 2),
        )
        rows = self._read()
        rows.append(asdict(session))
        self._write(rows)
        return session

    def sessions(
        self,
        kind: Optional[str] = None,
        shipped: Optional[bool] = None,
    ) -> List[Session]:
        rows = self._read()
        out = []
        for r in rows:
            if kind is not None and r.get("kind") != kind:
                continue
            if shipped is not None and bool(r.get("shipped")) != shipped:
                continue
            try:
                out.append(
                    Session(
                        **{
                            k: r[k]
                            for k in (
                                "id",
                                "start",
                                "end",
                                "kind",
                                "shipped",
                                "duration_min",
                            )
                        }
                    )
                )
            except (KeyError, TypeError):
                continue
        return out

    # ----------------------------------------------------------- peak model

    @staticmethod
    def _hour_minutes(sessions: List[Session]) -> List[float]:
        """Spread each session's minutes across the local hours it touches."""
        scores = [0.0] * 24
        for s in sessions:
            cur = _parse_dt(s.start)
            end = _parse_dt(s.end)
            while cur < end:
                nxt = cur.replace(minute=0, second=0, microsecond=0) + timedelta(
                    hours=1
                )
                seg_end = min(nxt, end)
                scores[cur.hour] += (seg_end - cur).total_seconds() / 60.0
                cur = seg_end
        return scores

    def peak_hours(
        self,
        min_sessions: int = MIN_PEAK_SESSIONS,
        window_hours: int = 3,
    ) -> Dict[str, Any]:
        """Learn peak windows from shipped deep sessions.

        Returns ``enough_data: False`` (with ``need`` = sessions still
        missing) below ``min_sessions`` — it never claims a peak it has
        not earned.
        """
        deep = [
            s
            for s in self.sessions()
            if s.kind in PEAK_KINDS and s.shipped and s.duration_min > 0
        ]
        n = len(deep)
        if n < min_sessions:
            return {
                "enough_data": False,
                "n_deep_shipped": n,
                "min_sessions": min_sessions,
                "need": min_sessions - n,
                "windows": [],
                "note": (
                    "not enough data — log %d more shipped deep "
                    "session(s) before peaks are claimed" % (min_sessions - n)
                ),
            }
        scores = self._hour_minutes(deep)
        total = sum(scores) or 1.0
        windows: List[Dict[str, Any]] = []
        used = [False] * 24
        width = max(1, min(int(window_hours), 12))
        for rank in range(3):
            best = None
            best_key = None
            for h in range(0, 24 - width + 1):
                if any(used[h : h + width]):
                    continue
                score = sum(scores[h : h + width])
                # Tie-break: prefer the window that *starts* on the energy
                # (first-hour score), then the earliest start. A peak that
                # begins where your energy actually is beats one that
                # merely overlaps it.
                key = (score, scores[h])
                if best_key is None or key > best_key:
                    best, best_key = h, key
            if best is None or best_key[0] <= 0:
                break
            for h in range(best, best + width):
                used[h] = True
            windows.append(
                {
                    "start_hour": best,
                    "end_hour": best + width,
                    "minutes": round(best_key[0], 1),
                    "share": round(best_key[0] / total, 3),
                    "rank": rank + 1,
                }
            )
        return {
            "enough_data": True,
            "n_deep_shipped": n,
            "min_sessions": min_sessions,
            "windows": windows,
            "note": ("learned from %d shipped deep sessions" % n),
        }

    # ------------------------------------------------------------ suggestion

    def suggest_slot(
        self,
        task_weight: str,
        now: Optional[Any] = None,
        duration_min: float = 60,
    ) -> Dict[str, Any]:
        """Recommend a time window for a task of the given weight.

        ``task_weight``: "hard" | "deep" | "normal" | "admin" | "light".
        Every recommendation carries ``basis``: "learned" or "heuristic".
        """
        weight = str(task_weight).strip().lower()
        if weight not in _HARD_WEIGHTS + _LIGHT_WEIGHTS:
            raise ValueError(
                "task_weight must be one of: hard, deep, normal, admin, light"
            )
        moment = _parse_dt(now) if now is not None else datetime.now()
        peaks = self.peak_hours()
        if weight in _HARD_WEIGHTS and peaks["enough_data"]:
            win = peaks["windows"][0]
            start = moment.replace(
                hour=win["start_hour"], minute=0, second=0, microsecond=0
            )
            if start <= moment:
                start = start + timedelta(days=1)
            return {
                "task_weight": weight,
                "when": start.isoformat(timespec="minutes"),
                "until": (start + timedelta(minutes=duration_min)).isoformat(
                    timespec="minutes"
                ),
                "window": win,
                "basis": "learned",
                "rationale": (
                    "peak window %02d:00-%02d:00 from %d shipped deep "
                    "sessions (%.0f%% of your shipped deep minutes land "
                    "there)"
                    % (
                        win["start_hour"],
                        win["end_hour"],
                        peaks["n_deep_shipped"],
                        win["share"] * 100,
                    )
                ),
            }
        if weight in _HARD_WEIGHTS:
            start = moment.replace(hour=8, minute=0, second=0, microsecond=0)
            if start <= moment:
                start = start + timedelta(days=1)
            return {
                "task_weight": weight,
                "when": start.isoformat(timespec="minutes"),
                "until": (start + timedelta(minutes=duration_min)).isoformat(
                    timespec="minutes"
                ),
                "window": {"start_hour": 8, "end_hour": 11},
                "basis": "heuristic",
                "rationale": (
                    "morning fallback — log %d more shipped deep session(s) "
                    "to personalize" % peaks["need"]
                ),
            }
        return {
            "task_weight": weight,
            "when": moment.isoformat(timespec="minutes"),
            "until": (moment + timedelta(minutes=duration_min)).isoformat(
                timespec="minutes"
            ),
            "window": None,
            "basis": "heuristic",
            "rationale": "light work rides any hour — no peak needed",
        }

    # ---------------------------------------------------------------- format

    def format_peaks(self, min_sessions: int = MIN_PEAK_SESSIONS) -> str:
        peaks = self.peak_hours(min_sessions=min_sessions)
        lines = ["LEVI energy peaks"]
        if not peaks["enough_data"]:
            lines.append(
                "  not enough data: %d/%d shipped deep sessions"
                % (peaks["n_deep_shipped"], peaks["min_sessions"])
            )
            lines.append("  log %d more to earn a peak claim" % peaks["need"])
            return "\n".join(lines)
        for w in peaks["windows"]:
            lines.append(
                "  #%d %02d:00-%02d:00  %.0f min shipped (%.0f%%)"
                % (
                    w["rank"],
                    w["start_hour"],
                    w["end_hour"],
                    w["minutes"],
                    w["share"] * 100,
                )
            )
        lines.append("  basis: " + peaks["note"])
        return "\n".join(lines)
