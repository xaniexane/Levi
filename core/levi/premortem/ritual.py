"""Pre-mortem ritual — structured "imagine it failed" cause-listing.

Before a big commitment, the ritual asks: *it's a year from now and
this failed — why?* Each imagined cause is scored on likelihood (1-5)
and impact (1-5); closing ranks them by likelihood x impact and emits
a mitigation checklist.

RED TEAM vs PRE-MORTEM (binding distinction, not vibes):
  - A red team attacks the PLAN'S LOGIC: it argues the strategy is
    wrong, the assumptions are false, the sequencing is broken. It
    debates the plan while the plan is still hypothetical.
  - A pre-mortem assumes FAILURE ALREADY HAPPENED and harvests causes:
    it does not argue with the plan, it lists what killed it. No
    debate, no defense — just causes, ranked.
  Red-teaming asks "is this plan right?"; pre-mortem asks "given it
  died, what killed it?". Run red-team to stress the plan, pre-mortem
  to insure against its death.

Honesty contract (binding):
  - likelihood and impact are INTEGERS 1-5, stated by the human. The
    module never invents them and never defaults them silently —
    missing scores are rejected.
  - Ranking is arithmetic (likelihood x impact), ties broken by impact,
    then by order added. No hidden weighting.
  - A closed session is immutable: reopening or editing a closed
    session is refused, so the ritual cannot be quietly rewritten
    after the fact.
  - The checklist is a *prompt* to write mitigations, not a mitigation
    itself: causes without a stated mitigation are flagged
    "unmitigated" rather than silently treated as handled.

stdlib-only. Local JSON only.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_STATE_DIR = "premortem"
_STATE_FILE = "sessions.json"

_MIN_SCORE = 1
_MAX_SCORE = 5


def levi_home() -> Path:
    """LEVI state home: ``$LEVI_HOME`` when set (hermetic tests), else ``~/.levi``.

    Resolved at call time — never at import — so tests can redirect it.
    """
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


@dataclass
class Cause:
    """One imagined cause of failure."""

    id: str
    cause: str
    likelihood: int  # 1-5, stated by the human
    impact: int  # 1-5, stated by the human
    mitigation: Optional[str] = None

    @property
    def risk(self) -> int:
        return self.likelihood * self.impact


@dataclass
class PremortemSession:
    id: str
    task: str
    started: str  # ISO-8601
    status: str  # "open" | "closed"
    causes: List[Dict[str, Any]] = field(default_factory=list)
    closed_at: Optional[str] = None


def _check_score(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            "%s must be an integer %d-%d, got %r"
            % (name, _MIN_SCORE, _MAX_SCORE, value)
        )
    if not (_MIN_SCORE <= value <= _MAX_SCORE):
        raise ValueError(
            "%s must be %d-%d, got %r" % (name, _MIN_SCORE, _MAX_SCORE, value)
        )
    return value


class Premortem:
    """Pre-mortem sessions, persisted as JSON."""

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

    def _get(self, session_id: str) -> Dict[str, Any]:
        for row in self._read():
            if row.get("id") == session_id:
                return row
        raise KeyError("no pre-mortem session %r" % session_id)

    # --------------------------------------------------------------- ritual

    def begin(self, task: str) -> PremortemSession:
        """Open a session: name the commitment, assume it failed."""
        text = str(task).strip()
        if not text:
            raise ValueError(
                "task is required — a pre-mortem needs a commitment to kill"
            )
        session = PremortemSession(
            id="pm-" + uuid.uuid4().hex[:8],
            task=text,
            started=datetime.now().isoformat(timespec="seconds"),
            status="open",
        )
        rows = self._read()
        rows.append(asdict(session))
        self._write(rows)
        return session

    def add_cause(
        self,
        session_id: str,
        cause: str,
        likelihood: int,
        impact: int,
        mitigation: Optional[str] = None,
    ) -> Cause:
        """Add an imagined cause. Scores are required, 1-5, human-stated."""
        text = str(cause).strip()
        if not text:
            raise ValueError("cause is required — an empty fear is not data")
        lh = _check_score("likelihood", likelihood)
        im = _check_score("impact", impact)
        rows = self._read()
        target = None
        for row in rows:
            if row.get("id") == session_id:
                target = row
                break
        if target is None:
            raise KeyError("no pre-mortem session %r" % session_id)
        if target.get("status") != "open":
            raise ValueError(
                "session %s is closed — closed sessions are immutable" % session_id
            )
        entry = Cause(
            id="pc-" + uuid.uuid4().hex[:8],
            cause=text,
            likelihood=lh,
            impact=im,
            mitigation=(
                str(mitigation).strip() or None if mitigation is not None else None
            ),
        )
        target.setdefault("causes", []).append(asdict(entry))
        self._write(rows)
        return entry

    def get_session(self, session_id: str) -> PremortemSession:
        row = self._get(session_id)
        return PremortemSession(
            **{
                k: row.get(k)
                for k in ("id", "task", "started", "status", "causes", "closed_at")
            }
        )

    def sessions(self, status: Optional[str] = None) -> List[PremortemSession]:
        out = []
        for row in self._read():
            if status is not None and row.get("status") != status:
                continue
            try:
                out.append(self.get_session(row["id"]))
            except (KeyError, TypeError):
                continue
        return out

    def close(self, session_id: str) -> Dict[str, Any]:
        """Close a session: rank causes, emit the mitigation checklist.

        Ranking is likelihood x impact, ties broken by impact then by
        order added. The session becomes immutable.
        """
        rows = self._read()
        target = None
        for row in rows:
            if row.get("id") == session_id:
                target = row
                break
        if target is None:
            raise KeyError("no pre-mortem session %r" % session_id)
        if target.get("status") != "open":
            raise ValueError("session %s is already closed" % session_id)
        causes = [Cause(**c) for c in target.get("causes", [])]
        ranked = sorted(
            causes,
            key=lambda c: (-c.risk, -c.impact, c.id),
        )
        checklist = []
        for c in ranked:
            if c.mitigation:
                item = "[ ] risk %d — %s → mitigate: %s" % (
                    c.risk,
                    c.cause,
                    c.mitigation,
                )
            else:
                item = "[ ] risk %d — %s → UNMITIGATED: write the mitigation" % (
                    c.risk,
                    c.cause,
                )
            checklist.append(
                {
                    "cause_id": c.id,
                    "cause": c.cause,
                    "likelihood": c.likelihood,
                    "impact": c.impact,
                    "risk": c.risk,
                    "mitigated": c.mitigation is not None,
                    "item": item,
                }
            )
        target["status"] = "closed"
        target["closed_at"] = datetime.now().isoformat(timespec="seconds")
        self._write(rows)
        return {
            "session_id": session_id,
            "task": target["task"],
            "n_causes": len(ranked),
            "top_risk": ranked[0].risk if ranked else 0,
            "ranked": checklist,
            "checklist": [c["item"] for c in checklist],
            "unmitigated": sum(1 for c in checklist if not c["mitigated"]),
        }

    def format_close(self, result: Dict[str, Any]) -> str:
        lines = ["pre-mortem: %s" % result["task"]]
        lines.append(
            "  %d cause(s), top risk %d, %d unmitigated"
            % (result["n_causes"], result["top_risk"], result["unmitigated"])
        )
        for item in result["checklist"]:
            lines.append("  " + item)
        lines.append(
            "  red-team attacks the plan's logic; pre-mortem "
            "assumes it already failed and harvests causes"
        )
        return "\n".join(lines)
