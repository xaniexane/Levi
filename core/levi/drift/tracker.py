"""Goal-drift instrument engine.

Model
-----
* A *goal* is a statement plus the activity *tags* that count as
  working toward it, e.g. ``tags=["deep-work", "study"]``.
* An *activity* is a timestamped log entry with tags and a free note.

The weekly card
---------------
``weekly_card(now)`` looks at the trailing ``WINDOW_DAYS`` (14) of
activity and, per goal, computes the share of activities carrying at
least one of that goal's tags. A goal is *drifting* when:

1. at least ``MIN_ACTIVITIES`` (5) activities were logged in the window
   (too little data → stay honest and SILENT, never claim drift on
   silence), and
2. the goal's tag-share is below ``DRIFT_THRESHOLD`` (0.2), while
3. some other tag — not claimed by any goal — absorbed at least
   ``MIN_ACTIVITIES`` entries (the behavior went somewhere concrete).

Return contract: a CARD-grade dict
``{"grade": "CARD", "tag": "[drift]", "title": ..., "body": ...}``
whose body carries the actual evidence (counts, examples), or ``None``
for SILENT.

Home is resolved at call time from ``LEVI_HOME`` or ``~/.levi``;
``now`` is injectable for hermetic tests.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"
WINDOW_DAYS = 14
DRIFT_THRESHOLD = 0.2
MIN_ACTIVITIES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


class DriftTracker:
    """Local JSON drift instrument."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.home = _resolve_home(home)
        self.root = self.home / "drift"
        self.root.mkdir(parents=True, exist_ok=True)
        self._goals_path = self.root / "goals.json"
        self._activity_path = self.root / "activity.jsonl"

    # -- persistence ------------------------------------------------------

    def _load_goals(self) -> Dict[str, Dict[str, Any]]:
        if not self._goals_path.exists():
            return {}
        try:
            return json.loads(self._goals_path.read_text(encoding=ENC))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_goals(self, goals: Dict[str, Dict[str, Any]]) -> None:
        self._goals_path.write_text(
            json.dumps(goals, indent=2, sort_keys=True) + "\n", encoding=ENC
        )

    def _load_activity(self) -> List[Dict[str, Any]]:
        out = []
        if not self._activity_path.exists():
            return out
        with self._activity_path.open(encoding=ENC) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # -- API --------------------------------------------------------------

    def set_goal(
        self,
        goal_id: str,
        statement: str,
        tags: "List[str] | tuple | None" = None,
    ) -> Dict[str, Any]:
        """Define (or redefine) a goal and the tags that count toward it."""
        if not goal_id or not goal_id.strip():
            raise ValueError("goal_id must not be empty")
        goals = self._load_goals()
        goal = {
            "id": goal_id,
            "statement": statement,
            "tags": sorted({str(t).strip() for t in (tags or []) if str(t).strip()}),
            "set_at": _now().isoformat(timespec="seconds"),
        }
        goals[goal_id] = goal
        self._save_goals(goals)
        return goal

    def drop_goal(self, goal_id: str) -> bool:
        goals = self._load_goals()
        if goal_id not in goals:
            return False
        del goals[goal_id]
        self._save_goals(goals)
        return True

    def log_activity(
        self,
        tags: "List[str] | tuple",
        note: str,
        *,
        ts: "datetime | str | None" = None,
    ) -> Dict[str, Any]:
        """Log one activity with tags (e.g. ["deep-work", "novelty"])."""
        clean_tags = sorted({str(t).strip() for t in tags if str(t).strip()})
        if not clean_tags:
            raise ValueError("at least one tag is required")
        if isinstance(ts, datetime):
            ts_iso = ts.isoformat(timespec="seconds")
        else:
            ts_iso = str(ts) if ts else _now().isoformat(timespec="seconds")
        entry = {"ts": ts_iso, "tags": clean_tags, "note": note}
        with self._activity_path.open("a", encoding=ENC) as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def _window(self, now: datetime) -> List[Dict[str, Any]]:
        cutoff = now - timedelta(days=WINDOW_DAYS)
        out = []
        for entry in self._load_activity():
            try:
                ts = datetime.fromisoformat(entry["ts"])
            except (KeyError, ValueError):
                continue
            if ts.tzinfo is None:
                # Naive stored timestamps are local time, not UTC.
                ts = ts.astimezone()
            if ts >= cutoff:
                out.append(entry)
        return out

    def weekly_card(self, now: "datetime | None" = None) -> Optional[Dict[str, Any]]:
        """Return a CARD-grade dict on real divergence, else None (SILENT)."""
        moment = now or _now()
        if moment.tzinfo is None:
            # Naive datetimes are local time, not UTC.
            moment = moment.astimezone()
        goals = self._load_goals()
        window = self._window(moment)

        if not goals or len(window) < MIN_ACTIVITIES:
            return None  # honest silence: too little to claim anything

        all_goal_tags = {t for g in goals.values() for t in g["tags"]}

        drifting = []
        for goal in goals.values():
            gtags = set(goal["tags"])
            matched = [a for a in window if gtags & set(a["tags"])]
            share = len(matched) / len(window)
            if share < DRIFT_THRESHOLD:
                drifting.append((goal, matched, share))

        # Behavior that went somewhere concrete: tags claimed by NO goal,
        # with enough volume to name them honestly.
        claimed_by_none: Dict[str, List[Dict[str, Any]]] = {}
        for entry in window:
            for tag in entry["tags"]:
                if tag not in all_goal_tags:
                    claimed_by_none.setdefault(tag, []).append(entry)
        significant_elsewhere = {
            t: es for t, es in claimed_by_none.items() if len(es) >= MIN_ACTIVITIES
        }

        if not drifting or not significant_elsewhere:
            return None

        sections = []
        for goal, matched, share in drifting:
            sections.append(
                f"- goal '{goal['id']}': {goal['statement']}\n"
                f"  {len(matched)} of {len(window)} activities "
                f"({share:.0%}) carried its tags {sorted(goal['tags'])}."
            )
        sections.append("where the time actually went (tags no goal claims):")
        examples = []
        for tag, entries in sorted(
            significant_elsewhere.items(), key=lambda kv: -len(kv[1])
        ):
            sections.append(f"- [{tag}]: {len(entries)} activities")
            examples.append(f"[{tag}] {entries[0]['note']}")
        body = (
            f"Trailing {WINDOW_DAYS} days: {len(window)} activities logged.\n\n"
            + "\n".join(sections)
            + "\n\nexamples:\n"
            + "\n".join(f"  {e}" for e in examples[:5])
            + "\n\nThis is evidence, not a verdict — adjust the goal or the week."
        )
        return {
            "grade": "CARD",
            "tag": "[drift]",
            "title": "Goal drift: behavior and stated goals diverged",
            "body": body,
            "drifting_goals": [g["id"] for g, _, _ in drifting],
            "window_days": WINDOW_DAYS,
            "activity_count": len(window),
        }


# -- module-level convenience wrappers (home resolved at call time) --------


def set_goal(
    goal_id: str,
    statement: str,
    tags: "List[str] | tuple | None" = None,
) -> Dict[str, Any]:
    return DriftTracker().set_goal(goal_id, statement, tags)


def log_activity(
    tags: "List[str] | tuple",
    note: str,
    *,
    ts: "datetime | str | None" = None,
) -> Dict[str, Any]:
    return DriftTracker().log_activity(tags, note, ts=ts)


def weekly_card(now: "datetime | None" = None) -> Optional[Dict[str, Any]]:
    return DriftTracker().weekly_card(now)
