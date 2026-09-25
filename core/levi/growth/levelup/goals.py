"""Daily question goals: N questions/day across subjects, with progression (L6, L7).

Subject rotation (the SOXI teaching rotation, 11 subjects):
    arithmetic, algebra, geometry, trigonometry, grammar, chemistry,
    physics, history, government, civics, logic puzzles

Planning is deterministic (L6): quota N for a date is split
round-robin over the rotation, offset by the date's ordinal — same
date + same quota => same subject assignment, always.

Progression (L7): each subject carries a monotone topic counter
(`topics.json`). When a goal is materialized, each question is issued
a topic id like ``arithmetic:014`` and the counter advances. The same
topic is never retaught; counters only move forward on issuance.

Answering: ``answer_question`` awards EXP for the steps and marks the
question answered. When the day's full quota is answered, a flat +50
``daily-complete`` bonus is awarded (no intensity multiplier).
"""

from __future__ import annotations

import json
from datetime import date as _date

from . import intensity as _intensity
from .multistep import award_question
from .receipts import award_exp, check_entity, levelup_dir

SUBJECTS: tuple[str, ...] = (
    "arithmetic",
    "algebra",
    "geometry",
    "trigonometry",
    "grammar",
    "chemistry",
    "physics",
    "history",
    "government",
    "civics",
    "logic puzzles",
)

DAILY_COMPLETE_BONUS = 50


def _goals_path():
    return levelup_dir() / "goals.json"


def _topics_path():
    return levelup_dir() / "topics.json"


def _load_json(path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return data if isinstance(data, dict) else default


def _save_json(path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def check_date(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("date must be an ISO date string, got %r" % (value,))
    try:
        _date.fromisoformat(value)
    except ValueError:
        raise ValueError("date must be YYYY-MM-DD, got %r" % (value,))
    return value


def plan_subjects(date_iso: str, quota: int) -> list[str]:
    """Deterministic subject assignment for a date + quota (L6)."""
    check_date(date_iso)
    if not isinstance(quota, int) or isinstance(quota, bool) or quota < 1:
        raise ValueError("quota must be a positive int, got %r" % (quota,))
    offset = _date.fromisoformat(date_iso).toordinal() % len(SUBJECTS)
    return [SUBJECTS[(offset + i) % len(SUBJECTS)] for i in range(quota)]


def next_topic(subject: str) -> str:
    """Issue the next topic id for a subject, advancing the counter (L7)."""
    if subject not in SUBJECTS:
        raise ValueError("unknown subject %r" % (subject,))
    path = _topics_path()
    counters = _load_json(path, {})
    n = counters.get(subject, 0)
    if not isinstance(n, int) or n < 0:
        n = 0
    topic_id = "%s:%03d" % (subject, n)
    counters[subject] = n + 1
    _save_json(path, counters)
    return topic_id


def topic_counter(subject: str) -> int:
    """Current (next-to-issue) topic counter for a subject."""
    if subject not in SUBJECTS:
        raise ValueError("unknown subject %r" % (subject,))
    counters = _load_json(_topics_path(), {})
    n = counters.get(subject, 0)
    return n if isinstance(n, int) and n >= 0 else 0


def ensure_goal(date_iso: str, quota: int) -> dict:
    """Materialize (or fetch, idempotently) the day's question goal."""
    date_iso = check_date(date_iso)
    goals = _load_json(_goals_path(), {})
    if date_iso in goals:
        return goals[date_iso]
    subjects = plan_subjects(date_iso, quota)
    assignments = []
    for i, subject in enumerate(subjects):
        assignments.append(
            {
                "id": "%s#%d" % (date_iso, i + 1),
                "subject": subject,
                "topic_id": next_topic(subject),
                "status": "open",
            }
        )
    goal = {"date": date_iso, "quota": quota, "assignments": assignments}
    goals[date_iso] = goal
    _save_json(_goals_path(), goals)
    return goal


def get_goal(date_iso: str) -> dict | None:
    return _load_json(_goals_path(), {}).get(check_date(date_iso))


def answer_question(
    date_iso: str,
    qid: str,
    entity: str,
    correctness: list,
    intensity_level: int = 1,
) -> dict:
    """Record one answered question: award EXP, mark answered.

    Returns {"receipt": ..., "goal_complete": bool, "bonus_receipt": ...|None}.
    Raises ValueError on unknown qid, double-answer, or bad inputs.
    """
    date_iso = check_date(date_iso)
    check_entity(entity)
    goals = _load_json(_goals_path(), {})
    goal = goals.get(date_iso)
    if goal is None:
        raise ValueError("no goal for %s — call ensure_goal first" % date_iso)
    assignment = next(
        (a for a in goal["assignments"] if a["id"] == qid), None
    )
    if assignment is None:
        raise ValueError("unknown question id %r for %s" % (qid, date_iso))
    if assignment["status"] != "open":
        raise ValueError("question %r already answered" % qid)
    meta = {
        "qid": qid,
        "date": date_iso,
        "subject": assignment["subject"],
        "topic_id": assignment["topic_id"],
    }
    receipt = award_question(entity, list(correctness), intensity_level, meta)
    assignment["status"] = "answered"
    assignment["intensity"] = intensity_level
    assignment["intensity_name"] = _intensity.name(intensity_level)
    bonus_receipt = None
    if all(a["status"] == "answered" for a in goal["assignments"]):
        if not goal.get("complete_bonus_awarded"):
            bonus_receipt = award_exp(
                entity,
                "daily-complete",
                DAILY_COMPLETE_BONUS,
                {"date": date_iso, "quota": goal["quota"]},
            )
            goal["complete_bonus_awarded"] = True
    goals[date_iso] = goal
    _save_json(_goals_path(), goals)
    return {
        "receipt": receipt,
        "goal_complete": all(a["status"] == "answered" for a in goal["assignments"]),
        "bonus_receipt": bonus_receipt,
    }
