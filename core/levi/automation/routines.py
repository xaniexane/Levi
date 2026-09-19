"""LEVI-native routine learning — "watch me once".

The honest answer to always-on cloud agent minions (SpaceXAI's Grok Minion and
its kin): they give every agent its own cloud computer, sign into apps and
websites, and operate UIs like a human — even with no API or MCP. They
learn a routine by watching the user once, save it, run it independently,
coordinate in group chats, and only pull the user in for judgment calls.
Price: $120-200/month in subscription tiers. Open questions their own
docs admit: credential storage, data isolation — minion screens are "work
surfaces, not separate security boundaries".

LEVI does the one thing they refuse: local, user-owned routine learning.

- A routine is recorded from the growth loop's session harvest — the same
  session records every bloodstream turn already produces — or composed
  by hand. Nothing is watched that the user didn't already say to LEVI.
- Routines are plain data (JSON under ``~/.levi/automation/``), owned by
  the user, portable, inspectable. Never code, never credentials.
- Playback runs every step through the automation rail:
  Plan -> Preview -> Permission -> Execute -> Verify -> Receipt.
  A denied permission gate stops the routine fail-closed. With
  ``dry_run=False`` the execute step routes through
  :mod:`levi.automation.executor` (one adapter acts — webhook POST,
  device artifacts, or a LEVI-produced work product — or a clean
  refusal), and the verify step records the adapter's evidence.

Per the additions-not-rebuilds law this does NOT rebuild the cloud-agent
model: no signing into apps, no operating external UIs, no autonomous
execution, no subscription, no cloud computer.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "Routine",
    "RoutineStep",
    "RoutineRun",
    "match_minions_for_text",
    "record_routine",
    "record_from_session",
    "list_routines",
    "get_routine",
    "delete_routine",
    "play_routine",
    "store_path",
]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _levi_home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def store_path(home: Optional[Path] = None) -> Path:
    """Path of the user-owned round store.

    The store was ``routines.json``; on first read the old file is moved
    to ``rounds.json`` so no user data is orphaned.
    """
    base = home if home is not None else _levi_home()
    new = base / "automation" / "rounds.json"
    old = base / "automation" / "routines.json"
    if not new.exists() and old.exists():
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
        except OSError:
            pass
    return new


def _load_store(home: Optional[Path] = None) -> Dict[str, Any]:
    path = store_path(home)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"routines": []}
    if not isinstance(raw, dict) or not isinstance(raw.get("routines"), list):
        return {"routines": []}
    return raw


def _save_store(data: Dict[str, Any], home: Optional[Path] = None) -> Path:
    path = store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "routine"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RoutineStep:
    """One step of a routine.

    A step either runs a catalog minion (``minion_id`` set — must reference a
    complete, known minion) or is a note-only step (``minion_id`` None: an
    annotation the playback records but never gates or runs).
    """

    label: str
    minion_id: Optional[str] = None
    event_summary: str = ""
    event_payload: Dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RoutineStep":
        payload = raw.get("event_payload", {})
        return cls(
            label=str(raw.get("label", "")),
            minion_id=raw.get("minion_id"),
            event_summary=str(raw.get("event_summary", "")),
            event_payload=dict(payload) if isinstance(payload, dict) else {},
            note=str(raw.get("note", "")),
        )


@dataclass
class Routine:
    """A named, user-owned sequence of steps."""

    id: str
    name: str
    created_utc: str
    source: str  # "manual" or "session:<session-id>"
    steps: List[RoutineStep] = field(default_factory=list)
    playback_count: int = 0
    last_played_utc: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Routine":
        steps = raw.get("steps", [])
        return cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            created_utc=str(raw.get("created_utc", "")),
            source=str(raw.get("source", "manual")),
            steps=[RoutineStep.from_dict(s) for s in steps if isinstance(s, dict)],
            playback_count=int(raw.get("playback_count", 0) or 0),
            last_played_utc=raw.get("last_played_utc"),
        )


@dataclass
class RoutineRun:
    """The receipt of one playback: every step's rail receipt."""

    routine_id: str
    ok: bool
    note: str
    step_notes: List[str] = field(default_factory=list)
    receipts: List[Any] = field(default_factory=list)  # engine Receipts
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "the a an to me my and or of in on for with is it at i you please "
    "this that these those".split()
)


def match_minions_for_text(text: str) -> List[Any]:
    """Catalog minions matching free text. Whole-phrase substring first, then
    significant-word fallback (words >= 4 chars, stopwords dropped).
    No match -> []: the recorder skips, never guesses."""
    from .minions import search

    if not isinstance(text, str) or not text.strip():
        return []
    hits = [b for b in search(text) if not b.incomplete]
    if hits:
        return hits
    seen: List[Any] = []
    for word in re.findall(r"[a-z]{4,}", text.lower()):
        if word in _STOPWORDS:
            continue
        for minion in search(word):
            if minion.incomplete or minion in seen:
                continue
            seen.append(minion)
    return seen


def _validate_step(step: RoutineStep, minions: List[Any]) -> None:
    from .minions import find_minion

    if not isinstance(step.label, str) or not step.label.strip():
        raise ValueError("routine step needs a non-empty label")
    if step.minion_id is not None:
        minion = find_minion(minions, step.minion_id)
        if minion is None:
            raise ValueError(f"unknown minion id in routine step: {step.minion_id!r}")
        if minion.incomplete:
            raise ValueError(
                f"minion {step.minion_id!r} is an incomplete intake row — "
                "routines only run complete minions"
            )
        if not step.event_summary.strip():
            raise ValueError(
                f"routine step {step.label!r}: minion steps need an event_summary"
            )
    if not isinstance(step.event_payload, dict):
        raise ValueError(f"routine step {step.label!r}: event_payload must be a dict")


def record_routine(
    name: str,
    steps: List[RoutineStep],
    source: str = "manual",
    home: Optional[Path] = None,
) -> Routine:
    """Record a new routine (deny-closed). Returns the stored Routine."""
    from .minions import MINIONS

    if not isinstance(name, str) or not name.strip():
        raise ValueError("routine needs a non-empty name")
    if not steps:
        raise ValueError("routine needs at least one step")
    for step in steps:
        if not isinstance(step, RoutineStep):
            raise ValueError("steps must be RoutineStep instances")
        _validate_step(step, MINIONS)
    routine = Routine(
        id=f"{_slug(name)}-{uuid.uuid4().hex[:8]}",
        name=name.strip(),
        created_utc=_utc_now(),
        source=source,
        steps=list(steps),
    )
    data = _load_store(home)
    data["routines"].append(routine.to_dict())
    _save_store(data, home)
    return routine


def record_from_session(
    session_id: str,
    name: Optional[str] = None,
    sessions_dir: Optional[Path] = None,
    home: Optional[Path] = None,
    max_steps: int = 12,
) -> Routine:
    """Distill a routine from one growth-harvested chat session — "watch me
    once".

    Reads the session through the growth loop's public
    :func:`levi.growth.experience.harvest_sessions` API (the same records
    every bloodstream turn already produces). Each user utterance that
    matches a catalog minion becomes a candidate step; utterances with no
    catalog match are skipped, never guessed at. Assistant tool records
    become note-only steps so the playback shows what LEVI did.

    The result is a *draft*: every step still passes a permission gate at
    playback, and the user owns the stored JSON.
    """
    from levi.growth.experience import harvest_sessions

    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("record_from_session needs a non-empty session_id")
    session_id = session_id.strip()

    experiences, _ = harvest_sessions(sessions_dir=sessions_dir)
    mine = [e for e in experiences if e.source == session_id]
    if not mine:
        raise ValueError(f"no harvested records for session {session_id!r}")

    steps: List[RoutineStep] = []
    for exp in mine:
        if len(steps) >= max_steps:
            break
        if exp.kind == "user-said":
            hits = match_minions_for_text(exp.content)
            if not hits:
                continue
            best = hits[0]
            steps.append(
                RoutineStep(
                    label=f"user: {exp.content[:80]}",
                    minion_id=best.id,
                    event_summary=exp.content[:200],
                    event_payload={},
                    note=f"matched catalog minion '{best.id}' ({best.subcategory})",
                )
            )
        elif exp.kind == "levi-did":
            steps.append(
                RoutineStep(
                    label=f"levi did: {exp.content[:80]}",
                    minion_id=None,
                    note=exp.content[:200],
                )
            )
    if not steps:
        raise ValueError(
            f"session {session_id!r} produced no routine steps "
            "(no user utterances matched the minion catalog)"
        )
    return record_routine(
        name or f"routine from session {session_id}",
        steps,
        source=f"session:{session_id}",
        home=home,
    )


# ---------------------------------------------------------------------------
# Listing / deletion
# ---------------------------------------------------------------------------


def list_routines(home: Optional[Path] = None) -> List[Routine]:
    data = _load_store(home)
    return [Routine.from_dict(r) for r in data["routines"] if isinstance(r, dict)]


def get_routine(routine_id: str, home: Optional[Path] = None) -> Optional[Routine]:
    for routine in list_routines(home):
        if routine.id == routine_id:
            return routine
    return None


def delete_routine(routine_id: str, home: Optional[Path] = None) -> bool:
    """Delete a routine. Returns True when something was deleted."""
    data = _load_store(home)
    before = len(data["routines"])
    data["routines"] = [
        r
        for r in data["routines"]
        if not (isinstance(r, dict) and r.get("id") == routine_id)
    ]
    if len(data["routines"]) == before:
        return False
    _save_store(data, home)
    return True


# ---------------------------------------------------------------------------
# Playback — every step through the rail, permission-gated
# ---------------------------------------------------------------------------


def play_routine(
    routine_id: str,
    responder: Any = None,
    dry_run: bool = True,
    home: Optional[Path] = None,
) -> RoutineRun:
    """Play a routine back. Every minion step runs through
    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt with the
    given ``responder`` at the permission gate. A denied gate stops the
    routine fail-closed — no later step runs.

    ``dry_run`` defaults True; with False each step executes for real
    through :mod:`levi.automation.executor` after its permission gate —
    a denied gate still stops the routine fail-closed before anything
    executes.
    """
    from .minions import MINIONS, find_minion
    from .engine import TriggerEvent, run_minion
    from .hitl import auto_approve

    routine = get_routine(routine_id, home)
    if routine is None:
        raise KeyError(f"unknown routine id: {routine_id!r}")
    respond = responder if responder is not None else auto_approve

    run = RoutineRun(routine_id=routine.id, ok=True, note="", dry_run=dry_run)
    for idx, step in enumerate(routine.steps, start=1):
        if step.minion_id is None:
            run.step_notes.append(f"step {idx} [note]: {step.label}")
            continue
        minion = find_minion(MINIONS, step.minion_id)
        if minion is None or minion.incomplete:
            run.ok = False
            run.note = (
                f"step {idx} ({step.label!r}): minion {step.minion_id!r} no longer "
                "available — routine stopped fail-closed"
            )
            break
        event = TriggerEvent(
            kind="routine",
            summary=step.event_summary or step.label,
            payload=dict(step.event_payload),
        )
        receipt = run_minion(minion, event, responder=respond, dry_run=dry_run)
        run.receipts.append(receipt)
        if not receipt.ok:
            run.ok = False
            run.note = (
                f"step {idx} ({step.label!r}): {receipt.note} — "
                "routine stopped fail-closed"
            )
            break
        run.step_notes.append(
            f"step {idx} [{minion.id}]: ok (receipt {receipt.receipt_id})"
        )
    if run.ok:
        run.note = (
            f"routine '{routine.name}' completed: {len(run.receipts)} minion step(s)"
        )
        routine.playback_count += 1
        routine.last_played_utc = _utc_now()
        data = _load_store(home)
        for raw in data["routines"]:
            if isinstance(raw, dict) and raw.get("id") == routine.id:
                raw["playback_count"] = routine.playback_count
                raw["last_played_utc"] = routine.last_played_utc
        _save_store(data, home)
    return run
