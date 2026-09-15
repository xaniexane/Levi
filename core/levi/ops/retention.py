"""
User retention layer — local-first habits without dark patterns.

High-grade features that increase return *use* without manufactured urgency:
  morning loop, honest sessions, shelf resume, export pride,
  story quality feedback, LEVI register fit, life-pack continuity,
  weekly review, opt-in streak (never punishes absence), trust floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List
import json


def _root() -> Path:
    p = Path.home() / ".levi" / "retention.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class RetentionState:
    sessions: int = 0
    last_iso: str = ""
    stories_created: int = 0
    stories_rated: int = 0
    avg_story_score: float = 0.0
    register_uses: Dict[str, int] = field(default_factory=dict)
    last_story_id: str = ""
    notes: List[str] = field(default_factory=list)
    # retention+
    days_active: List[str] = field(default_factory=list)  # ISO dates, opt-in streak
    weekly_reviews: int = 0
    exports_done: int = 0
    resume_count: int = 0
    goals_set: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessions": self.sessions,
            "last_iso": self.last_iso,
            "stories_created": self.stories_created,
            "stories_rated": self.stories_rated,
            "avg_story_score": self.avg_story_score,
            "register_uses": dict(self.register_uses),
            "last_story_id": self.last_story_id,
            "notes": list(self.notes)[-30:],
            "days_active": list(self.days_active)[-90:],
            "weekly_reviews": self.weekly_reviews,
            "exports_done": self.exports_done,
            "resume_count": self.resume_count,
            "goals_set": self.goals_set,
        }

    @classmethod
    def load(cls) -> "RetentionState":
        path = _root()
        if not path.exists():
            return cls()
        try:
            d = json.loads(path.read_text())
            return cls(
                sessions=int(d.get("sessions") or 0),
                last_iso=str(d.get("last_iso") or ""),
                stories_created=int(d.get("stories_created") or 0),
                stories_rated=int(d.get("stories_rated") or 0),
                avg_story_score=float(d.get("avg_story_score") or 0),
                register_uses=dict(d.get("register_uses") or d.get("kai_uses") or {}),
                last_story_id=str(d.get("last_story_id") or ""),
                notes=list(d.get("notes") or []),
                days_active=list(d.get("days_active") or []),
                weekly_reviews=int(d.get("weekly_reviews") or 0),
                exports_done=int(d.get("exports_done") or 0),
                resume_count=int(d.get("resume_count") or 0),
                goals_set=int(d.get("goals_set") or 0),
            )
        except Exception:
            return cls()

    def save(self) -> None:
        _root().write_text(json.dumps(self.to_dict(), indent=2))


def touch_session() -> RetentionState:
    st = RetentionState.load()
    st.sessions += 1
    st.last_iso = datetime.now(timezone.utc).isoformat()
    today = date.today().isoformat()
    if today not in st.days_active:
        st.days_active.append(today)
    st.save()
    return st


def record_story(score: float | None = None, story_id: str = "") -> RetentionState:
    st = RetentionState.load()
    st.stories_created += 1
    if story_id:
        st.last_story_id = story_id
    if score is not None:
        st.stories_rated += 1
        if st.stories_rated == 1:
            st.avg_story_score = float(score)
        else:
            st.avg_story_score = (
                st.avg_story_score * (st.stories_rated - 1) + float(score)
            ) / st.stories_rated
    st.save()
    return st


def record_export() -> RetentionState:
    st = RetentionState.load()
    st.exports_done += 1
    st.save()
    return st


def record_resume() -> RetentionState:
    st = RetentionState.load()
    st.resume_count += 1
    st.save()
    return st


def record_weekly_review(note: str = "") -> RetentionState:
    st = RetentionState.load()
    st.weekly_reviews += 1
    if note:
        st.notes.append(f"review:{note[:200]}")
    st.save()
    return st


def streak_days(st: RetentionState | None = None) -> int:
    """Opt-in streak: consecutive days ending today or yesterday. Never punishes gaps in UI copy."""
    st = st or RetentionState.load()
    if not st.days_active:
        return 0
    days = sorted(set(st.days_active), reverse=True)
    streak = 0
    expect = date.today()
    for d in days:
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        if dd == expect or (
            streak == 0
            and dd == expect.replace(day=expect.day)
            and (expect - dd).days <= 1
        ):
            if streak == 0 and (expect - dd).days > 1:
                break
            if (expect - dd).days <= 1 or dd == expect:
                streak += 1
                expect = dd.fromordinal(dd.toordinal() - 1)
            else:
                break
        elif dd == expect:
            streak += 1
            expect = dd.fromordinal(dd.toordinal() - 1)
        else:
            # allow starting from yesterday
            if streak == 0 and (date.today() - dd).days == 1:
                streak = 1
                expect = dd.fromordinal(dd.toordinal() - 1)
            else:
                break
    return streak


def format_retention() -> str:
    st = RetentionState.load()
    sk = streak_days(st)
    lines = [
        "══ LEVI Retention+ (local · no dark patterns) ══",
        f"sessions={st.sessions}  last={st.last_iso or '—'}",
        f"days_logged={len(st.days_active)}  opt_in_streak≈{sk} (absence is never punished)",
        f"stories_created={st.stories_created}  rated={st.stories_rated}  avg_score={st.avg_story_score:.2f}",
        f"resumes={st.resume_count}  exports={st.exports_done}  weekly_reviews={st.weekly_reviews}",
        f"last_story_id={st.last_story_id or '—'}",
        "",
        "Retention features (respect the human):",
        "  1. Resume orbit — morning / continue / shelf",
        "  2. Honest session log — count showing up, no guilt UI",
        "  3. Opt-in streak — consecutive days; gaps do not shame",
        "  4. Story craft scores — improve writing, not addiction",
        "  5. Export pride — life-pack; continuity is yours",
        "  6. Trust floor — offline crisis · HITL · wit mute",
        "  7. Register fit — KAI match, not novelty churn",
        "  8. Weekly review — what worked · what to cut",
        "  9. Goal shelf — small reversible next moves",
        " 10. Quality feedback loop — stress / story rater",
        "",
        "Commands:",
        "  levi retention --touch",
        "  levi morning · levi continue · levi export",
        "  levi stress · levi voice",
    ]
    if st.register_uses:
        lines.append(
            "Register uses: "
            + ", ".join(f"{k}={v}" for k, v in sorted(st.register_uses.items()))
        )
    return "\n".join(lines)
