"""LEVI decision journal with expiry — decisions that get revisited.

Every recorded decision carries a ``revisit`` date. When that date arrives,
:func:`check` / :meth:`DecisionJournal.check` surfaces the decision as a
CARD-grade signal asking "does this still hold?"

* ``reaffirm(id, note)`` — still holds; the reasoning is annotated, not
  rewritten.
* ``retire(id, why)`` — no longer holds. Retired decisions are *composted*:
  kept on the ledger with the reason, never deleted.

Grades are plain strings (``"SILENT"``/``"NUDGE"``/``"CARD"``/``"ESCALATE"``)
for the instincts engine to adopt without importing any signal package.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "DecisionError",
    "DecisionJournal",
    "check",
    "GRADES",
    "STATES",
]

GRADES = ("SILENT", "NUDGE", "CARD", "ESCALATE")
STATES = ("active", "retired")

DateLike = Union[None, str, date, datetime]


class DecisionError(Exception):
    """Raised for invalid decision operations (unknown id, bad state, ...)."""


def _levi_home() -> Path:
    """LEVI home, resolved at CALL time (never cached at import)."""
    env = os.environ.get("LEVI_HOME")
    if env and env.strip():
        return Path(env).expanduser()
    home = os.environ.get("HOME")
    if home and home.strip():
        return Path(home)
    return Path.home()


def _today(now: DateLike = None) -> date:
    if now is None:
        return datetime.now(timezone.utc).date()
    if isinstance(now, datetime):
        return now.date()
    if isinstance(now, date):
        return now
    raise DecisionError("now must be a date/datetime, got %r" % (now,))


def _parse_revisit(revisit: DateLike) -> str:
    """Normalize a revisit value to an ISO ``YYYY-MM-DD`` string."""
    if isinstance(revisit, datetime):
        return revisit.date().isoformat()
    if isinstance(revisit, date):
        return revisit.isoformat()
    if isinstance(revisit, str):
        text = revisit.strip()
        if not text:
            raise DecisionError("a decision needs a revisit date")
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            raise DecisionError(
                "revisit must be YYYY-MM-DD, got %r" % (revisit,)
            ) from None
    raise DecisionError("revisit must be a date/datetime/'YYYY-MM-DD'")


def _stamp(now: DateLike = None) -> str:
    """ISO timestamp; honors an injected ``now`` for hermetic tests."""
    if now is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(now, datetime):
        # Naive datetimes are local time, not UTC.
        dt = now if now.tzinfo else now.astimezone()
        return dt.isoformat()
    if isinstance(now, date):
        return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).isoformat()
    raise DecisionError("now must be a date/datetime, got %r" % (now,))


class DecisionJournal:
    """Persistent decision journal under the LEVI home."""

    def __init__(self, home: Optional[Union[str, Path]] = None) -> None:
        self.home = Path(home) if home is not None else _levi_home()
        self.path = self.home / ".levi" / "decisions" / "decisions.json"

    # -- persistence ------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"next_id": 1, "decisions": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DecisionError("decision journal unreadable: %s" % exc) from exc
        if not isinstance(data, dict) or "decisions" not in data:
            raise DecisionError("decision journal is corrupt (not a journal)")
        data.setdefault("next_id", len(data["decisions"]) + 1)
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    # -- lifecycle --------------------------------------------------------
    def decide(
        self, title: str, reasoning: str, revisit: DateLike, now: DateLike = None
    ) -> Dict[str, Any]:
        """Record a decision with a revisit date. Returns the decision dict."""
        title = (title or "").strip()
        if not title:
            raise DecisionError("a decision needs a title")
        data = self._load()
        did = "d%04d" % data["next_id"]
        data["next_id"] += 1
        decision = {
            "id": did,
            "title": title,
            "reasoning": (reasoning or "").strip(),
            "revisit": _parse_revisit(revisit),
            "state": "active",
            "created": _stamp(now),
            "reaffirmations": [],
            "retired_reason": "",
            "retired_at": None,
        }
        data["decisions"].append(decision)
        self._save(data)
        return dict(decision)

    def get(self, did: str) -> Dict[str, Any]:
        data = self._load()
        for d in data["decisions"]:
            if d["id"] == did:
                return dict(d)
        raise DecisionError("no decision with id %r" % (did,))

    def _mutate(self, did: str, **fields: Any) -> Dict[str, Any]:
        data = self._load()
        for d in data["decisions"]:
            if d["id"] == did:
                d.update(fields)
                self._save(data)
                return dict(d)
        raise DecisionError("no decision with id %r" % (did,))

    def reaffirm(self, did: str, note: str, now: DateLike = None) -> Dict[str, Any]:
        """Record that the decision still holds; note is appended."""
        d = self.get(did)
        if d["state"] != "active":
            raise DecisionError("decision %s is retired (cannot reaffirm)" % (did,))
        note = (note or "").strip()
        if not note:
            raise DecisionError("a reaffirmation needs a note — what still holds?")
        reaffirmations = list(d["reaffirmations"])
        reaffirmations.append({"note": note, "at": _stamp(now)})
        return self._mutate(did, reaffirmations=reaffirmations)

    def retire(self, did: str, why: str, now: DateLike = None) -> Dict[str, Any]:
        """Retire a decision — composted with the reason, never deleted."""
        d = self.get(did)
        if d["state"] != "active":
            raise DecisionError("decision %s is already retired" % (did,))
        why = (why or "").strip()
        if not why:
            raise DecisionError("a retired decision needs a reason — say why")
        return self._mutate(
            did, state="retired", retired_reason=why, retired_at=_stamp(now)
        )

    def list(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load()
        out = [dict(d) for d in data["decisions"]]
        if state is not None:
            if state not in STATES:
                raise DecisionError("unknown state %r" % (state,))
            out = [d for d in out if d["state"] == state]
        return out

    # -- expiry -----------------------------------------------------------
    def due_for_revisit(self, now: DateLike = None) -> List[Dict[str, Any]]:
        """Active decisions whose revisit date has arrived."""
        today = _today(now)
        return [
            d for d in self.list("active") if date.fromisoformat(d["revisit"]) <= today
        ]

    def status(self, now: DateLike = None) -> Dict[str, Any]:
        decisions = self.list()
        active = sum(1 for d in decisions if d["state"] == "active")
        retired = sum(1 for d in decisions if d["state"] == "retired")
        report: Dict[str, Any] = {
            "active": active,
            "retired": retired,
            "total": len(decisions),
            "due_for_revisit": len(self.due_for_revisit(now=now)),
        }
        if not decisions:
            report["note"] = "no decisions recorded yet — nothing to revisit."
        else:
            report["note"] = "%d active, %d retired; %d awaiting revisit." % (
                active,
                retired,
                report["due_for_revisit"],
            )
        return report

    # -- instincts integration surface ------------------------------------
    def check(self, now: DateLike = None) -> List[Dict[str, Any]]:
        """Revisit-due decisions as plain-grade CARD dicts.

        Each dict: ``{grade, tag, title, body}`` with grade one of
        "SILENT"/"NUDGE"/"CARD"/"ESCALATE" (plain strings — the instincts
        engine owns the real grade types).
        """
        signals: List[Dict[str, Any]] = []
        for d in self.due_for_revisit(now=now):
            title = d["title"]
            if len(title) > 90:
                title = title[:87] + "..."
            signals.append(
                {
                    "grade": "CARD",
                    "tag": "decisions:revisit",
                    "title": 'Revisit due — "%s"' % title,
                    "body": (
                        "Decision %s (revisit date %s): does this still hold? "
                        "Reasoning was: %s Reaffirm with a note, or retire it "
                        "with a reason."
                        % (
                            d["id"],
                            d["revisit"],
                            (d["reasoning"] + " ") if d["reasoning"] else "",
                        )
                    ),
                }
            )
        return signals


def check(
    home: Optional[Union[str, Path]] = None, now: DateLike = None
) -> List[Dict[str, Any]]:
    """Integration surface for the instincts engine: revisit-due signals."""
    return DecisionJournal(home=home).check(now=now)
