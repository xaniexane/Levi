"""Academy workforce — the people-shaped help behind the program.

Roles, not identities: lead_instructor, tutor, grader, drill_sergeant,
counselor. Nobody here is a real person and nothing is borrowed —
staffers are role titles plus callsigns, assigned deterministically so
the same session always gets the same crew.

The roster is data-driven: ``academy/data/staff.json`` holds the seed
roster; :func:`add_staff` / :func:`remove_staff` manage it at runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

ROLES = ("lead_instructor", "tutor", "grader", "drill_sergeant", "counselor")

ROLE_JOBS = {
    "lead_instructor": "Owns the lesson: briefs the session, teaches the dense layers, answers the hard questions.",
    "tutor": "Sits beside the learner: re-explains, runs Feynman re-drills, opens help tickets with them.",
    "grader": "Holds the bar: scores exercises and mastery checks, never moves the standard.",
    "drill_sergeant": "Runs pressure drills: time-boxed, no hand-holding, honest scores.",
    "counselor": "Catches the human: takes escalated tickets, checks the learner not just the lesson.",
}

_PKG = Path(__file__).resolve().parent
SEED_PATH = _PKG / "data" / "staff.json"


def _staff_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (
        (Path(home) if home is not None else Path(base).expanduser())
        / "academy"
        / "staff"
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def _roster_path(home: Optional[Path] = None) -> Path:
    if home is not None:
        return _staff_dir(home) / "roster.json"
    return SEED_PATH


def _write_json(path: Path, record: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _roster_path(home)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [r for r in data if r.get("role") in ROLES and r.get("callsign")]


def _save(entries: List[Dict[str, Any]], home: Optional[Path] = None) -> None:
    _write_json(_roster_path(home), entries)


def roster(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every staffer on the books: callsign, role, and job."""
    out = []
    for r in _load(home):
        out.append(
            {
                "callsign": r["callsign"],
                "role": r["role"],
                "job": ROLE_JOBS[r["role"]],
                "notes": r.get("notes", ""),
            }
        )
    return out


def add_staff(
    callsign: str, role: str, notes: str = "", home: Optional[Path] = None
) -> Dict[str, Any]:
    """Put a staffer on the roster. Role titles and callsigns only."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r} — must be one of {ROLES}")
    if not callsign or not callsign.strip():
        raise ValueError("callsign must be non-empty")
    callsign = callsign.strip()
    entries = _load(home)
    if any(r["callsign"].lower() == callsign.lower() for r in entries):
        raise ValueError(f"callsign {callsign!r} already on the roster")
    entry = {"callsign": callsign, "role": role, "notes": notes}
    entries.append(entry)
    _save(entries, home)
    return entry


def remove_staff(callsign: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Take a staffer off the roster. Unknown callsign -> KeyError."""
    entries = _load(home)
    for r in entries:
        if r["callsign"].lower() == callsign.lower():
            entries.remove(r)
            _save(entries, home)
            return r
    raise KeyError(f"no staffer with callsign {callsign!r}")


def assign_staff(
    session_id: str, needs: List[str], home: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """Pick one staffer per required role — deterministically.

    The same session id always draws the same crew: the assignment hashes
    ``session_id + role`` and walks the role's bench. Unknown role ->
    ValueError; an empty bench for a required role -> LookupError.
    """
    if not session_id:
        raise ValueError("session_id must be non-empty")
    by_role: Dict[str, List[Dict[str, Any]]] = {r: [] for r in ROLES}
    for r in _load(home):
        by_role[r["role"]].append(r)
    crew: Dict[str, Dict[str, Any]] = {}
    for role in needs:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r} — must be one of {ROLES}")
        bench = by_role[role]
        if not bench:
            raise LookupError(f"no staffer on the bench for role {role!r}")
        digest = hashlib.sha256(f"{session_id}:{role}".encode()).hexdigest()
        pick = bench[int(digest, 16) % len(bench)]
        crew[role] = {
            "callsign": pick["callsign"],
            "role": role,
            "job": ROLE_JOBS[role],
        }
    return crew
