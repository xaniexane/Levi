"""Meetup safety — opt-in first-meetup check-in system for the dating side.

Chauncey's order: first-meetup safety measures — opt-in tracking /
check-in until the user is comfortable. Privacy-first, consistent with
the airtight doctrine:

- Everything is OFF by default: no plan exists until the user creates
  one; no check-ins run until a plan is active.
- The user chooses trusted contacts and writes the meetup plan
  (who / where / when, check-in cadence, which contacts escalate).
- Check-in prompts are deadline-driven: the user checks in; if they go
  silent past the deadline, escalation fires — a sealed escalation
  record naming the user's chosen contacts and ONLY the disclosure the
  user pre-authorized. Nothing is shared beyond who they authorize.
- The user ends the plan when comfortable.

Honest limits: there is no live GPS and no real notification rail — the
escalation record is the handoff (sealed on the SI track), ready for the
user's device or a daemon to act on. Check-in cadence is the tracking;
silence past the deadline is the trigger. Escalation fires once per
plan and never repeats.

Both tracks use this module (``track="si"`` / ``track="ai"``): the SI
side is gate-locked with bounds-checked text and sealed records; the AI
side is open with SFW-checked text and plain local records. The tracks
never merge — per-track stores, asserted by test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator.store import (
    ai_read_all,
    ai_update,
    ai_write,
    si_read_all,
    si_update,
    si_write,
)

_TRACKS = (TRACK_SI, TRACK_AI)


class SafetyError(ValueError):
    """A safety operation was invalid."""


class SafetyDeniedError(PermissionError):
    """The caller is not the plan/contact owner."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_when(when_at: str) -> datetime:
    try:
        dt = datetime.fromisoformat(when_at)
    except Exception as exc:
        raise SafetyError("when_at must be ISO-8601: %s" % exc) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _check_track(track: str) -> None:
    if track not in _TRACKS:
        raise SafetyError("track must be one of %r" % (_TRACKS,))


def _guard_and_clean(track: str, home: Optional[Path], *texts: str) -> List[str]:
    """Per-track entry guard: SI → gate + bounds; AI → SFW rules."""
    if track == TRACK_SI:
        from levi.plaiground.bounds import check_bounds
        from levi.plaiground.gate import require_adult

        require_adult(home)
        return [check_bounds(t or "", home) for t in texts]
    from levi.creator.ai.rules import check_sfw

    return [check_sfw(t or "", home) for t in texts]


def _read_all(track: str, home: Optional[Path], kind: str) -> List[Dict[str, Any]]:
    return si_read_all(home, kind) if track == TRACK_SI else ai_read_all(home, kind)


def _write(track: str, home: Optional[Path], kind: str, record: Dict[str, Any]) -> Dict[str, Any]:
    return si_write(home, kind, record) if track == TRACK_SI else ai_write(home, kind, record)


def _update(
    track: str, home: Optional[Path], kind: str, record_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    return (
        si_update(home, kind, record_id, updates)
        if track == TRACK_SI
        else ai_update(home, kind, record_id, updates)
    )


# -- Trusted contacts ---------------------------------------------------


def add_contact(
    user_id: str,
    name: str,
    contact_ref: str,
    track: str,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Add a trusted contact. Visible only to the owning user."""
    _check_track(track)
    name, contact_ref = _guard_and_clean(track, home, name, contact_ref)
    if not user_id or not user_id.strip():
        raise SafetyError("user_id is required")
    return _write(
        track,
        home,
        "safety_contacts",
        {
            "track": track,
            "user_id": user_id.strip(),
            "name": name,
            "contact_ref": contact_ref,
            "created_at": _utcnow(),
        },
    )


def list_contacts(
    user_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The user's own trusted contacts. Nobody else's."""
    _check_track(track)
    _guard_and_clean(track, home)  # gate/rules still apply to reads
    return [
        c
        for c in _read_all(track, home, "safety_contacts")
        if c["user_id"] == user_id
    ]


# -- Meetup plans --------------------------------------------------------


def create_plan(
    user_id: str,
    who: str,
    where: str,
    when_at: str,
    check_in_minutes: int,
    contact_ids: List[str],
    track: str,
    disclosure: str = "",
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a meetup plan. Opt-in; nothing is shared by creating it.

    ``contact_ids`` must be the user's own trusted contacts.
    ``disclosure`` is the exact note revealed to contacts on escalation
    (in addition to who/where/when and the missed check-in fact).
    """
    _check_track(track)
    who, where = _guard_and_clean(track, home, who, where)
    # Disclosure is optional — guard it only when the user wrote one.
    disclosure = (
        _guard_and_clean(track, home, disclosure)[0]
        if (disclosure or "").strip()
        else ""
    )
    if not user_id or not user_id.strip():
        raise SafetyError("user_id is required")
    when = _parse_when(when_at)
    if not isinstance(check_in_minutes, int) or check_in_minutes < 5:
        raise SafetyError("check_in_minutes must be an int >= 5")
    contacts = {c["id"] for c in list_contacts(user_id, track, home)}
    chosen = list(contact_ids or [])
    if not chosen:
        raise SafetyError("at least one trusted contact is required")
    unknown = [c for c in chosen if c not in contacts]
    if unknown:
        raise SafetyError("not your trusted contacts: %r" % (unknown,))
    now = datetime.now(timezone.utc)
    return _write(
        track,
        home,
        "safety_plans",
        {
            "track": track,
            "user_id": user_id.strip(),
            "who": who,
            "where": where,
            "when_at": when.isoformat(),
            "check_in_minutes": check_in_minutes,
            "contact_ids": chosen,
            "disclosure": disclosure,
            "status": "active",
            "last_checkin_at": None,
            "next_due_at": (now + timedelta(minutes=check_in_minutes)).isoformat(),
            "created_at": _utcnow(),
        },
    )


def _get_plan(plan_id: str, user_id: str, track: str, home: Optional[Path]) -> Dict[str, Any]:
    plan = next(
        (p for p in _read_all(track, home, "safety_plans") if p["id"] == plan_id), None
    )
    if plan is None:
        raise SafetyError("unknown plan %r" % plan_id)
    if plan["user_id"] != user_id:
        raise SafetyDeniedError("this plan is not yours")
    return plan


def plan_status(
    plan_id: str, user_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Owner-only status: active/ended/escalated, next due, missed?"""
    _check_track(track)
    _guard_and_clean(track, home)
    plan = _get_plan(plan_id, user_id, track, home)
    now = datetime.now(timezone.utc)
    due = datetime.fromisoformat(plan["next_due_at"])
    return {
        "id": plan["id"],
        "status": plan["status"],
        "who": plan["who"],
        "where": plan["where"],
        "when_at": plan["when_at"],
        "next_due_at": plan["next_due_at"],
        "missed": plan["status"] == "active" and due <= now,
        "last_checkin_at": plan["last_checkin_at"],
    }


def check_in(
    plan_id: str, user_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Check in: resets the silence timer. Owner only, active plans only."""
    _check_track(track)
    _guard_and_clean(track, home)
    plan = _get_plan(plan_id, user_id, track, home)
    if plan["status"] != "active":
        raise SafetyError("plan is %s — check-in closed" % plan["status"])
    now = datetime.now(timezone.utc)
    return _update(
        track,
        home,
        "safety_plans",
        plan_id,
        {
            "last_checkin_at": now.isoformat(),
            "next_due_at": (now + timedelta(minutes=plan["check_in_minutes"])).isoformat(),
        },
    )


def end_plan(
    plan_id: str, user_id: str, track: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """End the plan — the user is comfortable. Owner only."""
    _check_track(track)
    _guard_and_clean(track, home)
    plan = _get_plan(plan_id, user_id, track, home)
    if plan["status"] == "ended":
        return plan
    return _update(
        track, home, "safety_plans", plan_id, {"status": "ended", "ended_at": _utcnow()}
    )


# -- Escalation ----------------------------------------------------------


def run_escalation_check(
    track: str,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Fire escalation for active plans past their check-in deadline.

    For each newly-escalated plan this writes a sealed (SI) / local (AI)
    escalation record containing ONLY what the user pre-authorized: the
    chosen contacts, who/where/when, the missed check-in fact, and the
    user's disclosure note. It fires once per plan and never repeats.
    No notification rail exists — the record is the handoff.

    This is a keeper/daemon operation, not a per-user call: it scans the
    track's plans. It reveals nothing about plans that are not escalating.
    """
    _check_track(track)
    _guard_and_clean(track, home)
    now = now or datetime.now(timezone.utc)
    contacts = {c["id"]: c for c in _read_all(track, home, "safety_contacts")}
    fired = []
    for plan in _read_all(track, home, "safety_plans"):
        if plan["status"] != "active":
            continue
        if datetime.fromisoformat(plan["next_due_at"]) > now:
            continue
        _update(
            track,
            home,
            "safety_plans",
            plan["id"],
            {"status": "escalated", "escalated_at": now.isoformat()},
        )
        disclosed_contacts = [
            {
                "name": contacts[cid]["name"],
                "contact_ref": contacts[cid]["contact_ref"],
            }
            for cid in plan["contact_ids"]
            if cid in contacts
        ]
        record = _write(
            track,
            home,
            "safety_escalations",
            {
                "track": track,
                "plan_id": plan["id"],
                "user_id": plan["user_id"],
                "missed_checkin_at": plan["next_due_at"],
                "who": plan["who"],
                "where": plan["where"],
                "when_at": plan["when_at"],
                "disclosure": plan["disclosure"],
                "contacts": disclosed_contacts,
                "delivery": "pending",  # no notification rail; handoff record
                "fired_at": now.isoformat(),
            },
        )
        fired.append(record)
    return fired


def list_escalations(
    user_id: str, track: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """The user's own escalation records. Owner only."""
    _check_track(track)
    _guard_and_clean(track, home)
    return [
        e
        for e in _read_all(track, home, "safety_escalations")
        if e["user_id"] == user_id
    ]
