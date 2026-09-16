"""Study hall — autonomous sharpening cadence for baby Levi.

A study run = one growth cycle (harvest → reflect → consolidate →
journal) followed by a curriculum self-quiz. The quiz is deliberately
simple and rule-based: for a sample of curriculum lessons it generates
a recall question from the lesson text, retrieves the lesson by topic
cue (the only honest offline "recall" we have), and scores what
fraction of the lesson's key terms come back.

Be honest about what this is: a **crude recall proxy, not
understanding**. It measures whether taught material is still intact
and retrievable by topic — like a student reciting back — not whether
Levi *understands* it. Scores trend in the journal so Chauncey can see
the line over time.

Cadence: ``levi.daemon.heartbeat`` runs ``run_study`` on a regular
interval (default 4h) but ONLY when idle — no session/chat/automation
activity inside the window. The idle check is cheap: file mtimes only,
no file reads beyond a directory listing.

Safety rails (same as the growth cycle):
  * writes ONLY to the memory store (growth-tagged entries) and the
    journal — never tools, policy, identity, the charter.
  * study runs are logged as ``kind: "study"`` journal records.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from levi.growth import cycle as _cycle
from levi.growth import journal as _journal

# ---------------------------------------------------------------------------
# cadence config
# ---------------------------------------------------------------------------

ENV_STUDY_ENABLED = "LEVI_STUDY_ENABLED"
ENV_STUDY_INTERVAL_HOURS = "LEVI_STUDY_INTERVAL_HOURS"
ENV_QUIZ_SAMPLE = "LEVI_STUDY_QUIZ_SAMPLE"
DEFAULT_STUDY_INTERVAL_HOURS = 4
DEFAULT_QUIZ_SAMPLE = 5


def study_enabled() -> bool:
    return os.environ.get(ENV_STUDY_ENABLED, "1").strip() != "0"


def study_interval_hours() -> float:
    try:
        return float(
            os.environ.get(ENV_STUDY_INTERVAL_HOURS, "") or DEFAULT_STUDY_INTERVAL_HOURS
        )
    except (TypeError, ValueError):
        return float(DEFAULT_STUDY_INTERVAL_HOURS)


def quiz_sample_size() -> int:
    try:
        return max(1, int(os.environ.get(ENV_QUIZ_SAMPLE, "") or DEFAULT_QUIZ_SAMPLE))
    except (TypeError, ValueError):
        return DEFAULT_QUIZ_SAMPLE


# ---------------------------------------------------------------------------
# idle gating — cheap, honest: newest mtime among user-activity signals
# ---------------------------------------------------------------------------

# Substrings that mark a sessions dir as worth checking. Kept as names,
# not full paths, so the check stays cheap and HOME-agnostic.
_ACTIVITY_DIR_CANDIDATES = (
    "agent/sessions",  # levi agent chat sessions
    "automations",  # automation run registry / records
)


def _resolve_home(home: Optional[Path]) -> Path:
    return Path(home).expanduser() if home is not None else Path.home()


def activity_mtimes(home: Path) -> dict[str, float]:
    """Newest mtime per activity-signal location (cheap: stat only)."""
    home = Path(home)
    out: dict[str, float] = {}

    def _scan(label: str, directory: Path) -> None:
        try:
            if not directory.is_dir():
                return
            newest = 0.0
            for p in directory.iterdir():
                try:
                    if p.is_file():
                        newest = max(newest, p.stat().st_mtime)
                except OSError:
                    continue
            if newest:
                out[label] = newest
        except OSError:
            pass

    # chat/agent sessions honour LEVI_AGENT_SESSIONS_DIR (see levi.agent.chat)
    try:
        from levi.agent.chat import sessions_dir as _sessions_dir

        _scan("sessions", _sessions_dir())
    except Exception:  # noqa: BLE001 — best-effort activity probe
        pass

    levi_home = home / ".levi"
    for cand in _ACTIVITY_DIR_CANDIDATES:
        d = levi_home / cand
        _scan(cand, d)
    return out


def last_activity_ts(home: Optional[Path] = None) -> Optional[datetime]:
    """Most recent user-activity timestamp, or None when never."""
    mtimes = activity_mtimes(_resolve_home(home))
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes.values()), tz=timezone.utc)


def is_idle(
    home: Optional[Path] = None, *, window_hours: float = DEFAULT_STUDY_INTERVAL_HOURS
) -> bool:
    """True when no session/chat/automation activity inside the window."""
    last = last_activity_ts(home)
    if last is None:
        return True
    now = datetime.now(timezone.utc)
    return (now - last) > timedelta(hours=window_hours)


# ---------------------------------------------------------------------------
# curriculum access — contract first, torch-planted seed as fallback
# ---------------------------------------------------------------------------

#: Real contract: ``from levi.growth.curriculum import LESSONS`` — a list
#: of dicts with keys ``id``, ``topic``, ``kind``, ``text``,
#: ``taught_by``. The curriculum package ships founder-seed lessons plus
#: the blue-team track (``curriculum/blue_team.py``); the remaining
#: fallbacks are defensive only, in order.
SEED_FILE_NAME = "curriculum_seed.json"  # fallback when the module is absent


def _seed_lessons() -> list[dict[str, Any]]:
    """Lessons planted by ``levi torch read`` (fallback seed store)."""
    path = _journal.growth_dir() / SEED_FILE_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = raw.get("lessons", []) if isinstance(raw, dict) else []
    return [it for it in items if isinstance(it, dict) and it.get("text")]


def _clean(lessons: Any) -> list[dict[str, Any]]:
    if not isinstance(lessons, list):
        return []
    return [it for it in lessons if isinstance(it, dict) and it.get("text")]


def get_lessons() -> list[dict[str, Any]]:
    """Curriculum lessons: real contract first, then fallbacks."""
    try:
        from levi.growth.curriculum import LESSONS

        cleaned = _clean(LESSONS)
        if cleaned:
            return cleaned
    except Exception:  # noqa: BLE001 — curriculum package absent/unreadable
        pass
    # legacy lowercase-`lessons` contract from the original spec (defensive)
    try:
        from levi.growth.curriculum import lessons as _lessons  # type: ignore

        cleaned = _clean(_lessons() if callable(_lessons) else _lessons)
        if cleaned:
            return cleaned
    except Exception:  # noqa: BLE001
        pass
    return _seed_lessons()


# ---------------------------------------------------------------------------
# self-quiz — rule-based recall check
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    """
    a an the and or but if then else when while of at by for with about
    into through during before after above below to from up down in out on
    off over under again further once here there all any both each few more
    most other some such no nor not only own same so than too very can will
    just don should now is are was were be been being have has had having
    do does did doing would could ought you your yours he him his she her
    hers it its they them their theirs we us our ours this that these those
    as what which who whom whose why how because until while of s t
    """.split()
)

_WORD_RE = re.compile(r"[a-z][a-z0-9'-]*")


def extract_key_terms(text: str, top_n: int = 8) -> list[str]:
    """Key terms = frequent long content words. Crude, deterministic.

    Raises ValueError when ``top_n`` is not a positive int.
    """
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError(
            "extract_key_terms: top_n must be a positive int, got %r" % (top_n,)
        )
    words = _WORD_RE.findall((text or "").lower())
    counts = Counter(w for w in words if len(w) >= 5 and w not in _STOPWORDS)
    ranked = sorted(
        counts.items(), key=lambda kv: (kv[1] * len(kv[0]), kv[0]), reverse=True
    )
    return [w for w, _ in ranked[:top_n]]


def make_question(lesson: dict[str, Any]) -> dict[str, Any]:
    """Build a cloze-style recall question from the lesson text.

    Raises ValueError when ``lesson`` is not a dict.
    """
    if not isinstance(lesson, dict):
        raise ValueError(
            "make_question: lesson must be a dict, got %s" % type(lesson).__name__
        )
    topic = str(lesson.get("topic", "untitled"))
    text = str(lesson.get("text", ""))
    key_terms = extract_key_terms(text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    best = max(
        sentences,
        key=lambda s: sum(1 for t in key_terms if t in s.lower()),
        default=text[:200],
    )
    blank_term = next(
        (t for t in key_terms if t in best.lower()), key_terms[0] if key_terms else ""
    )
    if blank_term:
        pattern = re.compile(re.escape(blank_term), re.IGNORECASE)
        question_text = pattern.sub("_____", best, count=1)
    else:
        question_text = best
    return {
        "topic": topic,
        "question": "Complete the lesson idea on '%s': \"%s\"" % (topic, question_text),
        "answer_term": blank_term,
        "key_terms": key_terms,
    }


def recall_by_topic(
    lessons: list[dict[str, Any]], topic: str
) -> Optional[dict[str, Any]]:
    """Topic-cued recall: the only offline 'memory' available.

    Returns a pseudo-lesson whose text is the union of every lesson under
    the cued topic (case-insensitive), or None when the topic draws a
    blank. A removed or renamed topic scores 0; a partially-damaged topic
    scores partially — that is the honest signal this proxy carries.

    Raises ValueError when ``lessons`` is not a list.
    """
    if not isinstance(lessons, list):
        raise ValueError(
            "recall_by_topic: lessons must be a list, got %s" % type(lessons).__name__
        )
    if not isinstance(topic, str) or not topic.strip():
        return None
    cue = topic.strip().lower()
    texts = [
        str(lesson.get("text", ""))
        for lesson in lessons
        if str(lesson.get("topic", "")).strip().lower() == cue
    ]
    texts = [t for t in texts if t.strip()]
    if not texts:
        return None
    return {"topic": topic, "text": "\n".join(texts)}


def grade(
    question: dict[str, Any], recalled: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Score = fraction of key terms present in the recalled lesson text.

    This is a recall-integrity proxy, NOT a comprehension test.
    Raises ValueError when ``question`` is not a dict.
    """
    if not isinstance(question, dict):
        raise ValueError(
            "grade: question must be a dict, got %s" % type(question).__name__
        )
    if recalled is not None and not isinstance(recalled, dict):
        raise ValueError(
            "grade: recalled must be a dict or None, got %s" % type(recalled).__name__
        )
    key_terms = question.get("key_terms") or []
    if not key_terms or recalled is None:
        return {"score": 0.0, "matched": 0, "total": len(key_terms), "blank_hit": False}
    text = str(recalled.get("text", "")).lower()
    matched = sum(1 for t in key_terms if t in text)
    total = len(key_terms)
    blank = str(question.get("answer_term") or "").lower()
    return {
        "score": matched / total if total else 0.0,
        "matched": matched,
        "total": total,
        "blank_hit": bool(blank and blank in text),
    }


def run_quiz(
    lessons: Optional[list[dict[str, Any]]] = None, *, sample_size: Optional[int] = None
) -> dict[str, Any]:
    """Quiz LEVI on a sample of curriculum lessons. Returns the result dict.

    Raises ValueError when ``lessons`` is not a list/None or
    ``sample_size`` is not a positive int.
    """
    if lessons is not None and not isinstance(lessons, list):
        raise ValueError(
            "run_quiz: lessons must be a list or None, got %s" % type(lessons).__name__
        )
    if sample_size is not None and (
        not isinstance(sample_size, int) or sample_size < 1
    ):
        raise ValueError(
            "run_quiz: sample_size must be a positive int, got %r" % (sample_size,)
        )
    all_lessons = lessons if lessons is not None else get_lessons()
    n = sample_size if sample_size is not None else quiz_sample_size()
    result: dict[str, Any] = {
        "sampled": 0,
        "total_lessons": len(all_lessons),
        "mean_score": None,
        "items": [],
        "reason": None,
    }
    if not all_lessons:
        result["reason"] = "no curriculum lessons available"
        return result

    # round-robin across runs so every lesson gets quizzed over time
    state = _journal.load_state()
    offset = (int(state.get("study_quiz_offset", 0)) or 0) % len(all_lessons)
    picked = [
        all_lessons[(offset + i) % len(all_lessons)]
        for i in range(min(n, len(all_lessons)))
    ]
    state["study_quiz_offset"] = offset + len(picked)
    _journal.save_state(state)

    scores = []
    for lesson in picked:
        q = make_question(lesson)
        recalled = recall_by_topic(all_lessons, q["topic"])
        g = grade(q, recalled)
        scores.append(g["score"])
        result["items"].append(
            {
                "topic": q["topic"],
                "kind": lesson.get("kind"),
                "taught_by": lesson.get("taught_by"),
                "score": round(g["score"], 3),
                "matched": g["matched"],
                "total": g["total"],
                "blank_hit": g["blank_hit"],
            }
        )
    result["sampled"] = len(picked)
    result["mean_score"] = round(sum(scores) / len(scores), 3) if scores else None
    return result


# ---------------------------------------------------------------------------
# one study run: cycle + quiz, journaled
# ---------------------------------------------------------------------------


def run_study(
    *,
    use_model: bool = False,
    dry_run: bool = False,
    home: Optional[Path] = None,
    store: Any = None,
    sample_size: Optional[int] = None,
) -> dict[str, Any]:
    """Run one study cycle: growth cycle (rules by default) + self-quiz.

    Returns a report dict; appends a ``kind: "study"`` journal record
    unless ``dry_run``.
    """
    cycle_report = _cycle.run_cycle(use_model=use_model, dry_run=dry_run, store=store)
    quiz = run_quiz(sample_size=sample_size)

    report: dict[str, Any] = {
        "cycle_id": cycle_report["cycle_id"],
        "dry_run": dry_run,
        "experiences": cycle_report["experiences"],
        "mode": cycle_report["mode"],
        "learnings_proposed": cycle_report["learnings_proposed"],
        "consolidation": cycle_report["consolidation"],
        "quiet": cycle_report["quiet"],
        "quiz": quiz,
    }

    if not dry_run:
        trend_scores = [
            e.get("quiz", {}).get("mean_score")
            for e in _journal.read_entries(limit=10)
            if e.get("kind") == "study"
            and e.get("quiz", {}).get("mean_score") is not None
        ]
        _journal.append_entry(
            {
                "id": cycle_report["cycle_id"],
                "kind": "study",
                "experiences": report["experiences"],
                "mode": report["mode"],
                "accepted": report["consolidation"]["accepted"],
                "corroborated": report["consolidation"]["corroborated"],
                "quiet": report["quiet"],
                "quiz": quiz,
                "quiz_trend_avg": (
                    round(sum(trend_scores) / len(trend_scores), 3)
                    if trend_scores
                    else None
                ),
                "quiz_trend_runs": len(trend_scores),
            }
        )
    return report


def study_trend(limit: int = 10) -> list[dict[str, Any]]:
    """Score history for the trend view: chronological, oldest first.

    Raises ValueError when ``limit`` is not a positive int.
    """
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("study_trend: limit must be a positive int, got %r" % (limit,))
    entries = [
        e for e in _journal.read_entries(limit=limit) if e.get("kind") == "study"
    ]
    out = []
    for e in reversed(entries):
        q = e.get("quiz") or {}
        out.append(
            {
                "id": e.get("id"),
                "ts": e.get("ts"),
                "mean_score": q.get("mean_score"),
                "sampled": q.get("sampled"),
                "total_lessons": q.get("total_lessons"),
                "accepted": e.get("accepted"),
                "corroborated": e.get("corroborated"),
                "quiet": e.get("quiet"),
            }
        )
    return out


def format_trend(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "No study runs yet — run `levi growth study run` to begin."
    lines = ["study trend (oldest → newest):"]
    for r in runs:
        score = r["mean_score"]
        score_s = "%.2f" % score if isinstance(score, (int, float)) else "n/a"
        lines.append(
            "  %s  score=%s  quizzed=%s/%s  accepted=%s corroborated=%s%s"
            % (
                r["ts"] or "?",
                score_s,
                r["sampled"],
                r["total_lessons"],
                r["accepted"],
                r["corroborated"],
                " (quiet)" if r["quiet"] else "",
            )
        )
    scores = [
        r["mean_score"] for r in runs if isinstance(r["mean_score"], (int, float))
    ]
    if scores:
        lines.append(
            "  avg=%.2f over %d scored run(s)"
            % (sum(scores) / len(scores), len(scores))
        )
    return "\n".join(lines)


def format_study_report(report: dict[str, Any]) -> str:
    lines = [
        "study run %s:" % report["cycle_id"],
        "  experiences=%d mode=%s accepted=%d corroborated=%d%s"
        % (
            report["experiences"],
            report["mode"],
            report["consolidation"]["accepted"],
            report["consolidation"]["corroborated"],
            " (quiet)" if report["quiet"] else "",
        ),
    ]
    q = report["quiz"]
    if q.get("mean_score") is None:
        lines.append("  quiz: skipped — %s" % (q.get("reason") or "no lessons"))
    else:
        lines.append(
            "  quiz: mean=%.2f over %d/%d lessons (recall proxy, not understanding)"
            % (q["mean_score"], q["sampled"], q["total_lessons"])
        )
        for item in q["items"]:
            lines.append(
                "    - %-28s score=%.2f (%d/%d terms)%s"
                % (
                    str(item["topic"])[:28],
                    item["score"],
                    item["matched"],
                    item["total"],
                    " blank✓" if item["blank_hit"] else " blank✗",
                )
            )
    return "\n".join(lines)
