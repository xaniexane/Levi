# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Schoolmaster track tooling — SM-2 scheduler, Socratic drills, Feynman rubric, course tracks.

Companion machinery for the Schoolmaster wave agent
(core/levi/dynasty/wave/schoolmaster.py), which owns "infinite learning"
and states proudly that it never certifies: no degrees, no certificates,
ever. This module is the engine under that vow — spaced repetition that
schedules by review quality, Socratic interrogation, Feynman compression
checks, and prerequisite-ordered course tracks.

Stdlib only. No network. Review state lives under
<home>/dynasty/schoolmaster/ (srs.json, tracks.json); <home> resolves
from the LEVI_HOME environment variable, defaulting to ~/.levi.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, scrub_text

__all__ = [
    "DrillError",
    "TrackError",
    "schedule",
    "due_cards",
    "drill",
    "score_explanation",
    "create_track",
    "progress",
    "complete_lesson",
]


class DrillError(AgentError):
    """A drill, schedule, or Feynman score was refused."""


class TrackError(AgentError):
    """A course track was malformed or a lesson move was illegal."""


# ---------------------------------------------------------------------
# shared plumbing
# ---------------------------------------------------------------------

_MAX_TOPIC_LEN = 128
_MAX_EXPLANATION_WORDS = 4000
_MAX_NAME_LEN = 96

_lock = threading.Lock()


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base() -> Path:
    return _home() / "dynasty" / "schoolmaster"


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".track-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _read_store(path: Path, what: str) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DrillError(f"{what} store unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise DrillError(f"{what} store corrupt: not a dict")
    return data


def _parse_iso(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DrillError(f"{field} must be an ISO-8601 timestamp string")
    try:
        stamp = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise DrillError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _check_topic(topic: Any) -> str:
    if not isinstance(topic, str) or not topic.strip():
        raise DrillError("topic must be a non-empty string")
    clean = scrub_text(topic.strip())
    if len(clean) > _MAX_TOPIC_LEN:
        raise DrillError(f"topic too long (>{_MAX_TOPIC_LEN} chars)")
    return clean


# ---------------------------------------------------------------------
# SM-2 spaced repetition
# ---------------------------------------------------------------------

_SM2_INITIAL_EASINESS = 2.5
_SM2_MIN_EASINESS = 1.3


def _check_card_id(card_id: Any) -> str:
    if not isinstance(card_id, str) or not card_id.strip():
        raise DrillError("card_id must be a non-empty string")
    return card_id.strip()


def _check_quality(quality: Any) -> int:
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise DrillError("quality must be an int in 0..5")
    if not 0 <= quality <= 5:
        raise DrillError(f"quality {quality} out of range 0..5")
    return quality


def _sm2_update(
    easiness: float, repetitions: int, interval_days: float, quality: int
) -> Dict[str, Any]:
    """Pure SM-2 step. quality<3 resets the repetition count and the
    interval back to one day; easiness never drops below 1.3."""
    ef = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef = max(_SM2_MIN_EASINESS, ef)
    if quality < 3:
        return {"easiness": round(ef, 4), "repetitions": 0, "interval_days": 1.0}
    repetitions += 1
    if repetitions == 1:
        interval = 1.0
    elif repetitions == 2:
        interval = 6.0
    else:
        interval = interval_days * ef
    return {
        "easiness": round(ef, 4),
        "repetitions": repetitions,
        "interval_days": round(interval, 1),
    }


def _srs_path() -> Path:
    return _base() / "srs.json"


def schedule(
    card_id: str, quality: int, now_iso: Optional[str] = None
) -> Dict[str, Any]:
    """Record one SM-2 review of a card.

    quality is 0..5 (anything else raises DrillError); quality<3 resets
    the repetition streak. Unknown cards are enrolled on first schedule
    with the SM-2 defaults. Returns {card_id, interval_days, easiness,
    repetitions, due_at_iso}. now_iso is an optional override for the
    review instant (tests); otherwise the current UTC time is used.
    """
    card_id = _check_card_id(card_id)
    quality = _check_quality(quality)
    now = (
        _parse_iso(now_iso, "now_iso")
        if now_iso is not None
        else datetime.now(timezone.utc)
    )
    with _lock:
        data = _read_store(_srs_path(), "SRS")
        cards = data.setdefault("cards", {})
        entry = cards.get(card_id)
        if entry is None:
            entry = {
                "easiness": _SM2_INITIAL_EASINESS,
                "repetitions": 0,
                "interval_days": 1.0,
                "reviews": 0,
            }
        step = _sm2_update(
            float(entry.get("easiness", _SM2_INITIAL_EASINESS)),
            int(entry.get("repetitions", 0)),
            float(entry.get("interval_days", 1.0)),
            quality,
        )
        due_at = now + timedelta(days=step["interval_days"])
        entry.update(step)
        entry["reviews"] = int(entry.get("reviews", 0)) + 1
        entry["due_at"] = due_at.isoformat(timespec="seconds")
        entry["last_quality"] = quality
        cards[card_id] = entry
        _atomic_write_json(_srs_path(), data)
    return {
        "card_id": card_id,
        "interval_days": step["interval_days"],
        "easiness": step["easiness"],
        "repetitions": step["repetitions"],
        "due_at_iso": entry["due_at"],
    }


def due_cards(now_iso: str) -> List[Dict[str, Any]]:
    """Every card whose due date is at or before now_iso, oldest first."""
    now = _parse_iso(now_iso, "now_iso")
    with _lock:
        data = _read_store(_srs_path(), "SRS")
        cards = data.get("cards", {})
    due = []
    for card_id, entry in cards.items():
        try:
            due_at = _parse_iso(entry.get("due_at", ""), "due_at")
        except DrillError:
            continue
        if due_at <= now:
            due.append(
                {
                    "card_id": card_id,
                    "due_at_iso": entry["due_at"],
                    "interval_days": entry.get("interval_days"),
                    "repetitions": entry.get("repetitions"),
                    "easiness": entry.get("easiness"),
                }
            )
    due.sort(key=lambda item: item["due_at_iso"])
    return due


# ---------------------------------------------------------------------
# Socratic drill
# ---------------------------------------------------------------------

_SOCRATIC_MOVES = ("clarify", "assumption", "evidence", "implication", "viewpoint")
_SOCRATIC_TEMPLATES = {
    "clarify": (
        "Strip it bare: what does {topic} actually claim, in your own plainest words?"
    ),
    "assumption": (
        "What must already be true for {topic} to hold — and what if it isn't?"
    ),
    "evidence": "What single observation would force you to throw {topic} out?",
    "implication": ("{topic} is true — now what follows that nobody has named yet?"),
    "viewpoint": (
        "Who looks at {topic} and sees it backwards, and what are they seeing?"
    ),
}
_MAX_DEPTH = 25


def drill(topic: str, depth: int = 3) -> List[Dict[str, str]]:
    """A Socratic question sequence for a topic.

    HONEST GENERATION NOTE: no model is involved. Questions are
    instantiated from fixed pedagogical templates (one per move in
    [clarify, assumption, evidence, implication, viewpoint]) with the
    topic string spliced in; depth cycles through the moves in order.
    The value is the interrogation order, not novelty.
    """
    clean = _check_topic(topic)
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise DrillError("depth must be an int")
    if not 1 <= depth <= _MAX_DEPTH:
        raise DrillError(f"depth must be 1..{_MAX_DEPTH}")
    questions = []
    for i in range(depth):
        move = _SOCRATIC_MOVES[i % len(_SOCRATIC_MOVES)]
        text = _SOCRATIC_TEMPLATES[move].replace("{topic}", clean)
        questions.append({"move": move, "text": text})
    return questions


# ---------------------------------------------------------------------
# Feynman rubric
# ---------------------------------------------------------------------

_ANALOGY_PATTERNS = (
    re.compile(r"\blike\b", re.IGNORECASE),
    re.compile(r"\bas if\b", re.IGNORECASE),
    re.compile(r"\bas\b.{1,40}?\bas\b", re.IGNORECASE),
    re.compile(r"\bthink of\b", re.IGNORECASE),
    re.compile(r"\bimagine\b", re.IGNORECASE),
    re.compile(r"\bmetaphor\b", re.IGNORECASE),
)
_GAP_PHRASES = (
    "i don't know",
    "don't know",
    "not sure",
    "unsure",
    "unclear",
    "gap in",
    "can't explain",
    "cannot explain",
    "don't understand",
    "confused",
    "no idea",
)
_WORD_RE = re.compile(r"[A-Za-z']+")


def score_explanation(text: str) -> Dict[str, Any]:
    """Score an explanation against the Feynman bar.

    HEURISTIC — documented limits:
    - simple_language (0..2): jargon penalty via average word length
      (<=4.7 chars scores 2, <=6.0 scores 1, else 0). Short words are a
      proxy for plain speech, nothing more: terse jargon ("qubit",
      "eigen") scores well and plain long words score badly.
    - analogy_present (bool): matches 'like'/'as' patterns and a few
      cue words (think of, imagine, metaphor). Misses analogies phrased
      without those cues, and false-positives on "I like X".
    - gaps_flagged (0..2): counts explicit uncertainty phrases ("I don't
      know", "not sure", ...). Silent gaps are invisible to it.
    verdict: total = simple_language + analogy + gaps_flagged (0..5);
      >=3 "compressed", 1..2 "workable", 0 "rework".
    """
    if not isinstance(text, str) or not text.strip():
        raise DrillError("score_explanation needs a non-empty explanation")
    words = _WORD_RE.findall(text)
    if not words:
        raise DrillError("explanation holds no words to score")
    if len(words) > _MAX_EXPLANATION_WORDS:
        raise DrillError("explanation too long to score")
    avg_len = sum(len(w) for w in words) / len(words)
    simple_language = 2 if avg_len <= 4.7 else (1 if avg_len <= 6.0 else 0)
    lowered = text.lower()
    analogy_present = any(p.search(lowered) for p in _ANALOGY_PATTERNS)
    gap_hits = sum(lowered.count(phrase) for phrase in _GAP_PHRASES)
    gaps_flagged = min(2, gap_hits)
    total = simple_language + (1 if analogy_present else 0) + gaps_flagged
    verdict = "compressed" if total >= 3 else ("workable" if total >= 1 else "rework")
    return {
        "simple_language": simple_language,
        "analogy_present": analogy_present,
        "gaps_flagged": gaps_flagged,
        "verdict": verdict,
        "words": len(words),
    }


# ---------------------------------------------------------------------
# Course tracks (prerequisite DAG)
# ---------------------------------------------------------------------


def _tracks_path() -> Path:
    return _base() / "tracks.json"


def _check_track_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise TrackError("track name must be a non-empty string")
    clean = scrub_text(name.strip())
    if len(clean) > _MAX_NAME_LEN:
        raise TrackError(f"track name too long (>{_MAX_NAME_LEN} chars)")
    return clean


def _check_user(user: Any) -> str:
    if not isinstance(user, str) or not user.strip():
        raise TrackError("user must be a non-empty string")
    return scrub_text(user.strip())


def _normalize_lessons(lessons: Any) -> List[Dict[str, Any]]:
    """Validate lesson specs and prove the prerequisite graph is a DAG.

    Raises TrackError on: non-list input, missing/duplicate titles,
    unknown prerequisites, non-list prerequisites, cycles (incl. self-loops).
    """
    if not isinstance(lessons, list) or not lessons:
        raise TrackError("lessons must be a non-empty list")
    titles: List[str] = []
    specs: List[Dict[str, Any]] = []
    for idx, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            raise TrackError(f"lesson {idx} must be a dict")
        title = lesson.get("title")
        if not isinstance(title, str) or not title.strip():
            raise TrackError(f"lesson {idx} needs a non-empty title")
        clean_title = scrub_text(title.strip())
        if clean_title in titles:
            raise TrackError(f"duplicate lesson title: {clean_title!r}")
        prereqs = lesson.get("prerequisites", [])
        if not isinstance(prereqs, list) or any(
            not isinstance(p, str) for p in prereqs
        ):
            raise TrackError(
                f"lesson {clean_title!r}: prerequisites must be a list of titles"
            )
        specs.append(
            {"title": clean_title, "prerequisites": [p.strip() for p in prereqs]}
        )
        titles.append(clean_title)
    known = set(titles)
    for spec in specs:
        for prereq in spec["prerequisites"]:
            if prereq not in known:
                raise TrackError(
                    f"lesson {spec['title']!r}: unknown prerequisite {prereq!r}"
                )
    # Cycle check: iterative DFS with colors.
    graph = {spec["title"]: spec["prerequisites"] for spec in specs}
    visiting: set = set()
    visited: set = set()

    def visit(node: str, trail: List[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle = " -> ".join(trail + [node])
            raise TrackError(f"prerequisite cycle: {cycle}")
        visiting.add(node)
        for parent in graph[node]:
            visit(parent, trail + [node])
        visiting.discard(node)
        visited.add(node)

    for title in titles:
        visit(title, [])
    return specs


def create_track(name: str, lessons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Declare a course track. lessons is a list of
    {title, prerequisites:[...]}. Raises TrackError unless the
    prerequisites form a DAG over existing titles."""
    clean_name = _check_track_name(name)
    specs = _normalize_lessons(lessons)
    with _lock:
        try:
            data = _read_store(_tracks_path(), "tracks")
        except DrillError as exc:
            raise TrackError(str(exc)) from exc
        tracks = data.setdefault("tracks", {})
        if clean_name in tracks:
            raise TrackError(f"track {clean_name!r} already exists")
        tracks[clean_name] = {
            "name": clean_name,
            "lessons": specs,
            "created_at": _utc_now(),
        }
        data.setdefault("progress", {})
        _atomic_write_json(_tracks_path(), data)
    return {"name": clean_name, "lessons": specs}


def _load_tracks() -> Dict[str, Any]:
    with _lock:
        try:
            data = _read_store(_tracks_path(), "tracks")
        except DrillError as exc:
            raise TrackError(str(exc)) from exc
    data.setdefault("tracks", {})
    data.setdefault("progress", {})
    return data


def _resolve_track(data: Dict[str, Any], track: Optional[str]) -> str:
    tracks = data["tracks"]
    if track is not None:
        clean = _check_track_name(track)
        if clean not in tracks:
            raise TrackError(f"unknown track: {clean!r}")
        return clean
    if not tracks:
        raise TrackError("no tracks declared yet")
    if len(tracks) > 1:
        raise TrackError(
            "track is ambiguous — name one of: " + ", ".join(sorted(tracks))
        )
    return next(iter(tracks))


def _track_progress(data: Dict[str, Any], user: str, track: str) -> Dict[str, Any]:
    spec = data["tracks"][track]
    completed = list(data["progress"].get(user, {}).get(track, []))
    done = set(completed)
    next_available = [
        lesson["title"]
        for lesson in spec["lessons"]
        if lesson["title"] not in done
        and all(p in done for p in lesson["prerequisites"])
    ]
    return {"track": track, "completed": completed, "next_available": next_available}


def progress(user: str, track: Optional[str] = None) -> Dict[str, Any]:
    """Where a user stands. With a single declared track (or a named
    one), returns {track, completed, next_available}; with several
    tracks and no name, returns {track_name: {...}} for each."""
    clean_user = _check_user(user)
    data = _load_tracks()
    if track is not None or len(data["tracks"]) == 1:
        name = _resolve_track(data, track)
        return _track_progress(data, clean_user, name)
    return {
        name: _track_progress(data, clean_user, name) for name in sorted(data["tracks"])
    }


def complete_lesson(
    user: str, lesson: str, track: Optional[str] = None
) -> Dict[str, Any]:
    """Mark a lesson complete. The lesson must be currently available
    (all prerequisites completed); completing it unlocks its dependents.
    Raises TrackError otherwise."""
    clean_user = _check_user(user)
    if not isinstance(lesson, str) or not lesson.strip():
        raise TrackError("lesson must be a non-empty string")
    clean_lesson = scrub_text(lesson.strip())
    data = _load_tracks()
    name = _resolve_track(data, track)
    status = _track_progress(data, clean_user, name)
    if clean_lesson not in [
        lesson["title"] for lesson in data["tracks"][name]["lessons"]
    ]:
        raise TrackError(f"unknown lesson {clean_lesson!r} in track {name!r}")
    if clean_lesson in status["completed"]:
        raise TrackError(f"lesson {clean_lesson!r} already completed")
    if clean_lesson not in status["next_available"]:
        raise TrackError(
            f"lesson {clean_lesson!r} is locked — finish its prerequisites first"
        )
    with _lock:
        data = _read_store(_tracks_path(), "tracks")
        user_tracks = data.setdefault("progress", {}).setdefault(clean_user, {})
        done = user_tracks.setdefault(name, [])
        if clean_lesson not in done:
            done.append(clean_lesson)
        try:
            _atomic_write_json(_tracks_path(), data)
        except DrillError as exc:
            raise TrackError(str(exc)) from exc
    return _track_progress(data, clean_user, name)
