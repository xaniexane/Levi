"""LEVI promise tracker — LEVI holds itself accountable for promises it makes.

A promise is a commitment LEVI itself uttered to the user, across sessions.
The tracker records fulfillment honestly:

* ``pending`` — made, not yet resolved.
* ``kept`` — fulfilled, with evidence attached.
* ``broken`` — missed. A broken promise is recorded, never deleted: the
  failure is part of the ledger, compost for the growth loop to learn from.

Ledger grades exposed through :func:`check` / :meth:`PromiseStore.check`
use plain strings (``"SILENT"``/``"NUDGE"``/``"CARD"``/``"ESCALATE"``) so
the instincts engine can adopt them without importing any signal package.

Escalation rule: a pending promise past its due date surfaces as CARD. If
it stays unresolved past *twice its original lead time* (days between
creation and due, minimum 2-day grace), it becomes ESCALATE.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "PromiseError",
    "PromiseStore",
    "check",
    "GRADES",
    "STATES",
    "ESCALATION_MULTIPLE",
]

GRADES = ("SILENT", "NUDGE", "CARD", "ESCALATE")
STATES = ("pending", "kept", "broken")

#: Overdue a promise past (lead time × this) → ESCALATE instead of CARD.
ESCALATION_MULTIPLE = 2

#: Minimum grace in days before an overdue promise can escalate.
MIN_ESCALATION_DAYS = 2

DateLike = Union[None, str, date, datetime]


class PromiseError(Exception):
    """Raised for invalid promise operations (unknown id, bad state, ...)."""


def _levi_home() -> Path:
    """LEVI home, resolved at CALL time (never cached at import).

    Honors ``LEVI_HOME`` first, then ``HOME``; falls back to
    :func:`pathlib.Path.home` for exotic platforms.
    """
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
    raise PromiseError("now must be a date/datetime, got %r" % (now,))


def _parse_due(due: DateLike) -> Optional[str]:
    """Normalize a due value to an ISO ``YYYY-MM-DD`` string (or None)."""
    if due is None:
        return None
    if isinstance(due, datetime):
        return due.date().isoformat()
    if isinstance(due, date):
        return due.isoformat()
    if isinstance(due, str):
        text = due.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            raise PromiseError("due must be YYYY-MM-DD, got %r" % (due,)) from None
    raise PromiseError("due must be a date/datetime/'YYYY-MM-DD'/None")


def _stamp(now: DateLike = None) -> str:
    """ISO timestamp; honors an injected ``now`` for hermetic tests."""
    if now is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(now, datetime):
        dt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(now, date):
        return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).isoformat()
    raise PromiseError("now must be a date/datetime, got %r" % (now,))


class PromiseStore:
    """Persistent promise ledger under the LEVI home."""

    def __init__(self, home: Optional[Union[str, Path]] = None) -> None:
        self.home = Path(home) if home is not None else _levi_home()
        self.path = self.home / ".levi" / "promises" / "promises.json"

    # -- persistence ------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"next_id": 1, "promises": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PromiseError("promise ledger unreadable: %s" % exc) from exc
        if not isinstance(data, dict) or "promises" not in data:
            raise PromiseError("promise ledger is corrupt (not a ledger)")
        data.setdefault("next_id", len(data["promises"]) + 1)
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    # -- lifecycle --------------------------------------------------------
    def make(
        self, text: str, due: DateLike = None, actor: str = "levi", now: DateLike = None
    ) -> Dict[str, Any]:
        """Record a new promise. Returns the promise dict."""
        text = (text or "").strip()
        if not text:
            raise PromiseError("a promise needs text")
        if not actor or not actor.strip():
            raise PromiseError("a promise needs an actor")
        data = self._load()
        pid = "p%04d" % data["next_id"]
        data["next_id"] += 1
        promise = {
            "id": pid,
            "text": text,
            "due": _parse_due(due),
            "actor": actor.strip(),
            "state": "pending",
            "created": _stamp(now),
            "evidence": "",
            "why_broken": "",
            "resolved_at": None,
        }
        data["promises"].append(promise)
        self._save(data)
        return dict(promise)

    def get(self, pid: str) -> Dict[str, Any]:
        data = self._load()
        for p in data["promises"]:
            if p["id"] == pid:
                return dict(p)
        raise PromiseError("no promise with id %r" % (pid,))

    def _mutate(self, pid: str, **fields: Any) -> Dict[str, Any]:
        data = self._load()
        for p in data["promises"]:
            if p["id"] == pid:
                p.update(fields)
                self._save(data)
                return dict(p)
        raise PromiseError("no promise with id %r" % (pid,))

    def fulfill(
        self, pid: str, evidence: str = "", now: DateLike = None
    ) -> Dict[str, Any]:
        """Mark a promise kept, with evidence of fulfillment."""
        p = self.get(pid)
        if p["state"] != "pending":
            raise PromiseError(
                "promise %s is already %s (cannot fulfill)" % (pid, p["state"])
            )
        return self._mutate(
            pid,
            state="kept",
            evidence=(evidence or "").strip(),
            resolved_at=_stamp(now),
        )

    def break_promise(self, pid: str, why: str, now: DateLike = None) -> Dict[str, Any]:
        """Record a promise as broken — kept on the ledger with the reason.

        Honest naming on purpose: a broken promise is compost, not deletion.
        """
        p = self.get(pid)
        if p["state"] != "pending":
            raise PromiseError(
                "promise %s is already %s (cannot break)" % (pid, p["state"])
            )
        why = (why or "").strip()
        if not why:
            raise PromiseError("a broken promise needs a reason — say why")
        return self._mutate(
            pid, state="broken", why_broken=why, resolved_at=_stamp(now)
        )

    def list(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load()
        out = [dict(p) for p in data["promises"]]
        if state is not None:
            if state not in STATES:
                raise PromiseError("unknown state %r" % (state,))
            out = [p for p in out if p["state"] == state]
        return out

    # -- reporting --------------------------------------------------------
    def overdue(self, now: DateLike = None) -> List[Dict[str, Any]]:
        """Pending promises whose due date has passed."""
        today = _today(now)
        return [
            p
            for p in self.list("pending")
            if p["due"] and date.fromisoformat(p["due"]) < today
        ]

    def status(self, now: DateLike = None) -> Dict[str, Any]:
        """Fulfillment report: kept/pending/broken counts + rate."""
        promises = self.list()
        kept = sum(1 for p in promises if p["state"] == "kept")
        pending = sum(1 for p in promises if p["state"] == "pending")
        broken = sum(1 for p in promises if p["state"] == "broken")
        resolved = kept + broken
        report: Dict[str, Any] = {
            "kept": kept,
            "pending": pending,
            "broken": broken,
            "total": len(promises),
            "fulfillment_rate": (kept / resolved) if resolved else None,
            "overdue": len(self.overdue(now=now)),
        }
        if not promises:
            report["note"] = "no promises recorded yet — nothing to report."
        elif not resolved:
            report["note"] = (
                "promises recorded but none resolved yet — "
                "fulfillment rate not computable."
            )
        else:
            report["note"] = "%d of %d resolved promises kept (%.0f%%)." % (
                kept,
                resolved,
                100.0 * kept / resolved,
            )
        return report

    # -- instincts integration surface -----------------------------------
    def check(self, now: DateLike = None) -> List[Dict[str, Any]]:
        """Overdue-promise signals as plain-grade dicts.

        Each dict: ``{grade, tag, title, body}`` with grade one of
        "SILENT"/"NUDGE"/"CARD"/"ESCALATE" (plain strings — the instincts
        engine owns the real grade types).
        """
        today = _today(now)
        signals: List[Dict[str, Any]] = []
        for p in self.overdue(now=today):
            due = date.fromisoformat(p["due"])
            overdue_days = (today - due).days
            created = datetime.fromisoformat(p["created"]).date()
            lead_days = (due - created).days
            threshold = max(lead_days * ESCALATION_MULTIPLE, MIN_ESCALATION_DAYS)
            grade = "ESCALATE" if overdue_days > threshold else "CARD"
            text = p["text"]
            if len(text) > 90:
                text = text[:87] + "..."
            signals.append(
                {
                    "grade": grade,
                    "tag": "promises:overdue",
                    "title": 'Overdue promise — "%s"' % text,
                    "body": (
                        "Promise %s (by %s) was due %s — %d day(s) overdue. "
                        "Fulfill it or record it broken with a reason; "
                        "broken promises stay on the ledger."
                        % (p["id"], p["actor"], p["due"], overdue_days)
                    ),
                }
            )
        return signals


def check(
    home: Optional[Union[str, Path]] = None, now: DateLike = None
) -> List[Dict[str, Any]]:
    """Integration surface for the instincts engine: overdue-promise signals.

    ``home`` resolves via LEVI_HOME/HOME when omitted; ``now`` is injectable
    for tests. Returns a list of ``{grade, tag, title, body}`` dicts.
    """
    return PromiseStore(home=home).check(now=now)
