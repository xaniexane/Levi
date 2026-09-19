"""Academy remediation — the "extra help" layer.

When a learner struggles, the academy answers with structure, not shame:

- **Help tickets**: any learner can ask for help on a session
  (:func:`request_help`); tickets live under ``~/.levi/academy/help/``.
- **Auto-remediation**: after grading, a failed gate or a mastery score
  below 0.70 generates a remedial micro-session plan — a Feynman re-drill
  on each missed objective plus spaced-repetition reviews scheduled through
  :mod:`levi.academy.methods` (:func:`auto_remediate`).
- **Escalation**: the third failure on the same objective is not a study
  problem anymore — the ticket escalates to a human counselor note so a
  person looks at it.

Instructional-design grounding (remix law — studied, rebuilt natively, in
our own words):

- Objectives for remedial plans follow Bloom's revised taxonomy
  (Anderson & Krathwohl): the re-drill targets the cognitive level the
  learner missed (Remember/Understand before Apply/Analyze), and every
  plan ends in an observable behavior — never "understand it better".
  (Ref: Bloom's taxonomy verb tables — teachfloor.com, valamis.com.)
- The review schedule uses the academy's own decay model
  (:func:`levi.academy.methods.next_review`): reviews land just before the
  predicted forgetting point, not on a fixed calendar.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy import methods as _methods

# Below this, a struggle is real enough to need structure.
MASTERY_HELP_THRESHOLD = 0.70
# The third strike on the same objective goes to a human.
ESCALATION_FAILURES = 3

FAILURE_KEYWORDS = ("fail", "stuck", "confus", "struggl", "lost", "behind", "help")


def _help_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (
        (Path(home) if home is not None else Path(base).expanduser())
        / "academy"
        / "help"
    )
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _failures_dir(home: Optional[Path] = None) -> Path:
    d = _help_dir(home) / "failures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _safe(learner_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in learner_id)


# ---------------------------------------------------------------------------
# Help tickets
# ---------------------------------------------------------------------------


def request_help(
    learner_id: str,
    session_id: str,
    reason: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Open a help ticket: a learner asking for a hand, on the record.

    Asking for help is data, not failure. The ticket pins the reason to a
    session so the tutor knows exactly where the learner got stuck.
    """
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not session_id or not session_id.strip():
        raise ValueError("session_id must be non-empty")
    if not reason or not reason.strip():
        raise ValueError("reason must be non-empty — say where it hurts")
    ticket_id = uuid.uuid4().hex[:12]
    ticket = {
        "ticket_id": ticket_id,
        "learner_id": learner_id,
        "session_id": session_id,
        "reason": reason.strip(),
        "status": "open",
        "opened_at": _utcnow(now),
        "resolved_at": None,
        "resolution": None,
        "escalated": False,
    }
    _write_json(_help_dir(home) / f"{_safe(learner_id)}-{ticket_id}.json", ticket)
    return ticket


def resolve_help(
    learner_id: str,
    ticket_id: str,
    resolution: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Close a ticket with what actually helped. Unknown ticket -> KeyError."""
    path = _help_dir(home) / f"{_safe(learner_id)}-{ticket_id}.json"
    if not path.exists():
        raise KeyError(f"no help ticket {ticket_id!r} for learner {learner_id!r}")
    ticket = json.loads(path.read_text(encoding="utf-8"))
    if not resolution or not resolution.strip():
        raise ValueError("resolution must be non-empty")
    ticket["status"] = "resolved"
    ticket["resolution"] = resolution.strip()
    ticket["resolved_at"] = _utcnow(now)
    _write_json(path, ticket)
    return ticket


def open_tickets(
    learner_id: Optional[str] = None, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """All open (or escalated) tickets, optionally for one learner."""
    out = []
    for path in sorted(_help_dir(home).glob("*.json")):
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if ticket.get("status") not in ("open", "escalated"):
            continue
        if learner_id is not None and ticket.get("learner_id") != learner_id:
            continue
        out.append(ticket)
    return out


def help_stats(
    learner_id: Optional[str] = None, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Ticket counts: open, escalated, resolved. Asking is healthy."""
    counts = {"open": 0, "escalated": 0, "resolved": 0}
    for path in _help_dir(home).glob("*.json"):
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if learner_id is not None and ticket.get("learner_id") != learner_id:
            continue
        status = ticket.get("status")
        if status == "escalated":
            counts["escalated"] += 1
        elif status in counts:
            counts[status] += 1
    counts["total"] = counts["open"] + counts["escalated"] + counts["resolved"]
    return counts


# ---------------------------------------------------------------------------
# Failure tracking + escalation
# ---------------------------------------------------------------------------


def _load_failures(learner_id: str, home: Optional[Path] = None) -> Dict[str, int]:
    path = _failures_dir(home) / f"{_safe(learner_id)}.json"
    if not path.exists():
        return {}
    try:
        return {str(k): int(v) for k, v in json.loads(path.read_text()).items()}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def record_failure(learner_id: str, objective: str, home: Optional[Path] = None) -> int:
    """Bump the failure count for one objective. Returns the new count."""
    failures = _load_failures(learner_id, home)
    failures[objective] = failures.get(objective, 0) + 1
    _write_json(_failures_dir(home) / f"{_safe(learner_id)}.json", failures)
    return failures[objective]


def failure_count(learner_id: str, objective: str, home: Optional[Path] = None) -> int:
    """How many times this objective has beaten this learner."""
    return _load_failures(learner_id, home).get(objective, 0)


def escalate(
    learner_id: str,
    session_id: str,
    objective: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Escalate to a human counselor note.

    The third failure on the same objective stops being a study problem —
    a person needs to look at it. The ticket says so plainly.
    """
    ticket = request_help(
        learner_id,
        session_id,
        f"ESCALATED — {ESCALATION_FAILURES} failures on objective: {objective}. "
        "Human counselor review requested: the study plan is not landing; "
        "a person should check whether the objective, the material, or the "
        "learner's framing needs to change.",
        home=home,
        now=now,
    )
    ticket["status"] = "escalated"
    ticket["escalated"] = True
    _write_json(
        _help_dir(home) / f"{_safe(learner_id)}-{ticket['ticket_id']}.json", ticket
    )
    return ticket


# ---------------------------------------------------------------------------
# Auto-remediation
# ---------------------------------------------------------------------------


def _missed(session: Dict[str, Any]) -> Dict[str, List[str]]:
    return {
        "objectives": list(session.get("missed_objectives") or []),
        "questions": list(session.get("missed_questions") or []),
    }


def auto_remediate(
    learner_id: str,
    session_record: Dict[str, Any],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Build a remedial micro-session plan when the learner is struggling.

    Triggers on a failed gate or a mastery score below 0.70. Returns None
    when the learner is doing fine — no plan, no noise.

    The plan is Bloom-shaped: each missed objective gets a Feynman re-drill
    (teach it back at the level it was missed) plus a spaced-repetition
    review scheduled just before the decay model says it would be
    forgotten. Objectives hitting their third failure escalate to a human
    counselor ticket.
    """
    gate_passed = bool(session_record.get("gate_passed", True))
    mastery = float(session_record.get("mastery_score", 1.0) or 0.0)
    struggling = (not gate_passed) or (mastery < MASTERY_HELP_THRESHOLD)
    if not struggling:
        return None

    sid = str(session_record.get("session") or session_record.get("session_id") or "?")
    missed = _missed(session_record)
    objectives = missed["objectives"] or ["(objectives unlisted — re-drill the lesson)"]

    drills = []
    reviews = []
    escalations = []
    for i, objective in enumerate(objectives):
        count = record_failure(learner_id, objective, home=home)
        if count >= ESCALATION_FAILURES:
            ticket = escalate(learner_id, sid, objective, home=home, now=now)
            escalations.append(
                {"ticket_id": ticket["ticket_id"], "objective": objective}
            )
        drills.append(
            _methods.feynman_drill(
                objective,
                [
                    objective,
                    f"session {sid}: say it back in your own words, then apply it once",
                ],
            )
        )
        reviews.append(
            _methods.next_review(
                learner_id,
                f"remediation:{sid}:objective-{i}",
                threshold=0.8,
                home=home,
                now=now,
            )
        )

    plan = {
        "learner_id": learner_id,
        "session_id": sid,
        "trigger": "gate_failed" if not gate_passed else "low_mastery",
        "mastery_score": round(mastery, 3),
        "missed_objectives": missed["objectives"],
        "missed_questions": missed["questions"],
        "feynman_redrills": drills,
        "spaced_reviews": reviews,
        "escalations": escalations,
        "guidance": (
            "Work the re-drills in order: teach each missed objective back "
            "in your own words, then run one concrete application. Reviews "
            "are scheduled just before the decay model predicts forgetting — "
            "do them when they come due, not before. Asking for help is "
            "data, not failure: open a ticket any time."
        ),
        "created_at": _utcnow(now),
    }
    return plan


def attach_remediation(
    result: Dict[str, Any],
    learner_id: str = "levi",
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Additive hook for :func:`levi.academy.run_session.run_one_session`.

    Calls :func:`auto_remediate` and sets ``result["remediation"]`` (a plan
    or None). The existing record shape is never altered — only this one
    key is added, so progress.json and the journal keep working.
    """
    try:
        result["remediation"] = auto_remediate(learner_id, result, home=home, now=now)
    except Exception as exc:  # remediation must never break a session
        result["remediation"] = {"error": f"remediation failed safely: {exc}"}
    return result
