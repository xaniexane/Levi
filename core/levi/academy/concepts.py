"""Concept registry and spaced repetition for LEVI Boot Camp.

Mass knowledge overload is only useful if it is retained. This module is
the retention machinery:

- Every concept taught gets an ID, track, day introduced, and review
  schedule: next block (+1 session), next day (+4), +28, +56 sessions.
- Reviews are RETRIEVAL drills — never re-reading. The drill measures
  whether the system's durable memory (offline corpus + journal) can
  reconstruct the concept. The first review (next block) is open-book
  (consolidation); later reviews are closed-book (true retention: the
  concept's own introductory records are excluded).
- Forgetting is expected: a drill score below the threshold is logged
  honestly in the journal and the concept is re-queued.
- Weekly assessments and the graduation crucible sample the WEAKEST
  concepts first (per-concept scores are tracked).
- Sparring blocks interleave concepts across tracks.

State lives in ``concepts.json`` under ``LEVI_ACADEMY_DIR``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REVIEW_OFFSETS = [1, 4, 28, 56]  # in sessions: next block, next day, +28, +56
MAX_REVIEWS_PER_SESSION = 6
FORGET_THRESHOLD = 0.6
ASSESSMENT_REVIEWS = 10


def _data_dir() -> Path:
    return Path(os.environ.get("LEVI_ACADEMY_DIR", Path.home() / ".levi" / "academy"))


def registry_path() -> Path:
    return _data_dir() / "concepts.json"


def load_registry() -> dict:
    path = registry_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("concepts", {})
            return data
        except json.JSONDecodeError:
            pass
    return {"concepts": {}}


def save_registry(data: dict) -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)
    registry_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _slug(text: str, limit: int = 6) -> str:
    words = re.findall(r"[a-z]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "from", "that", "this"}
    return "".join(w[:4] for w in words if w not in stop)[:limit] or "concept"


def extract_concepts(
    day: int, block: int, track: str, entry: dict, research: dict, session_n: int
) -> list[dict]:
    """Concepts taught by one session: objectives + researched vocabulary."""
    from levi.academy.synthesize import content_words

    concepts: list[dict] = []
    for i, obj in enumerate(entry["objectives"], 1):
        cid = f"{track}D{day:02d}B{block}O{i}"
        concepts.append(
            {
                "id": cid,
                "name": obj,
                "kind": "objective",
                "track": track,
                "day": day,
                "block": block,
                "session": session_n,
                "content_words": content_words(obj),
                "reviews": [
                    {
                        "due_session": session_n + off,
                        "done": False,
                        "score": None,
                        "forgotten": False,
                    }
                    for off in REVIEW_OFFSETS
                    if session_n + off <= 120
                ],
                "scores": [],
                "strength": 0.8,
                "status": "active",
            }
        )
    for i, term in enumerate(research.get("key_terms", [])[:6], 1):
        cid = f"{track}D{day:02d}B{block}T{i}"
        concepts.append(
            {
                "id": cid,
                "name": term,
                "kind": "term",
                "track": track,
                "day": day,
                "block": block,
                "session": session_n,
                "content_words": content_words(term),
                "reviews": [
                    {
                        "due_session": session_n + off,
                        "done": False,
                        "score": None,
                        "forgotten": False,
                    }
                    for off in REVIEW_OFFSETS
                    if session_n + off <= 120
                ],
                "scores": [],
                "strength": 0.8,
                "status": "active",
            }
        )
    return concepts


def register_session(
    day: int,
    block: int,
    track: str,
    entry: dict,
    research: dict,
    session_n: int,
    mastery_score: float = 1.0,
    waived: bool = False,
) -> int:
    """Register a session's concepts POST-mastery. Returns count added."""
    data = load_registry()
    added = 0
    for c in extract_concepts(day, block, track, entry, research, session_n):
        if c["id"] in data["concepts"]:
            continue
        # Waived gates start weaker: they are sampled first by assessments.
        c["strength"] = 0.5 if waived else min(1.0, 0.5 + 0.5 * mastery_score)
        c["waived"] = waived
        data["concepts"][c["id"]] = c
        added += 1
    save_registry(data)
    return added


def due_concepts(
    session_n: int,
    limit: int = MAX_REVIEWS_PER_SESSION,
    tracks: tuple[str, ...] | None = None,
) -> list[dict]:
    """Concepts with a pending review due at this session.

    Weakest and most overdue first — forgetting gets attention before
    comfort.
    """
    data = load_registry()
    due: list[tuple[int, float, dict, int]] = []
    for c in data["concepts"].values():
        if c.get("status") != "active":
            continue
        if tracks and c["track"] not in tracks:
            continue
        for idx, rev in enumerate(c["reviews"]):
            if not rev["done"] and rev["due_session"] <= session_n:
                overdue = session_n - rev["due_session"]
                due.append((overdue, c["strength"], c, idx))
                break  # one pending review per concept per session
    due.sort(key=lambda t: (-t[0], t[1]))
    out = []
    for _, _, c, idx in due[:limit]:
        c = dict(c)
        c["_review_idx"] = idx
        out.append(c)
    return out


def sample_weakest(track: str, k: int) -> list[dict]:
    """Weakest active concepts of a track — for cumulative assessments."""
    data = load_registry()
    pool = [
        c
        for c in data["concepts"].values()
        if c.get("status") == "active" and c["track"] == track
    ]
    pool.sort(key=lambda c: (c["strength"], c["session"]))
    return pool[:k]


def recent_concepts(exclude_track: str, k: int = 3) -> list[dict]:
    """Most recent concepts from other tracks — lesson cross-links.

    Teaching in dense layers means every session is woven into the others:
    new material explicitly revisits prior cross-track concepts.
    """
    data = load_registry()
    pool = [
        c
        for c in data["concepts"].values()
        if c.get("status") == "active" and c["track"] != exclude_track
    ]
    pool.sort(key=lambda c: c["session"], reverse=True)
    seen: set[str] = set()
    out = []
    for c in pool:
        if c["name"] in seen:
            continue
        seen.add(c["name"])
        out.append(c)
        if len(out) >= k:
            break
    return out


def interleave_concepts(session_n: int, k: int = 2) -> list[dict]:
    """Concepts from other tracks to interleave into sparring drills.

    Due reviews first (weakest, most overdue); falls back to the weakest
    concepts overall so sparring always mixes tracks.
    """
    due = due_concepts(session_n, limit=k, tracks=("A", "B", "C"))
    if len(due) >= k:
        return due
    have = {c["id"] for c in due}
    data = load_registry()
    pool = [
        c
        for c in data["concepts"].values()
        if c.get("status") == "active"
        and c["track"] in ("A", "B", "C")
        and c["id"] not in have
    ]
    pool.sort(key=lambda c: (c["strength"], c["session"]))
    return due + pool[: k - len(due)]


def record_review(concept_id: str, session_n: int, score: float) -> dict:
    """Record a drill result; re-queue on forgetting. Returns the update."""
    data = load_registry()
    c = data["concepts"].get(concept_id)
    if not c:
        return {"ok": False}
    forgotten = score < FORGET_THRESHOLD
    # mark the earliest pending due review done
    for rev in c["reviews"]:
        if not rev["done"] and rev["due_session"] <= session_n:
            rev["done"] = True
            rev["score"] = round(score, 3)
            rev["forgotten"] = forgotten
            break
    c["scores"].append(round(score, 3))
    # strength: exponential moving average, pulled down harder by forgetting
    alpha = 0.5 if forgotten else 0.3
    c["strength"] = round((1 - alpha) * c["strength"] + alpha * score, 3)
    if forgotten:
        # re-queue: an extra review 4 sessions out (if inside the program)
        due = session_n + 4
        if due <= 120 and not any(
            r["due_session"] == due and not r["done"] for r in c["reviews"]
        ):
            c["reviews"].append(
                {
                    "due_session": due,
                    "done": False,
                    "score": None,
                    "forgotten": False,
                    "requeue": True,
                }
            )
            c["reviews"].sort(key=lambda r: r["due_session"])
    save_registry(data)
    return {"ok": True, "forgotten": forgotten, "strength": c["strength"]}


def retention_stats() -> dict:
    """Per-track retention: concepts, reviewed count, hit rate.

    Hit rate = mean of latest drill scores (strength is the EMA of those).
    Completion without retention is failure — this is the number that says
    whether the overload actually stuck.
    """
    data = load_registry()
    stats: dict[str, dict] = {}
    for track in ("A", "B", "C", "S"):
        pool = [
            c
            for c in data["concepts"].values()
            if c.get("status") == "active" and c["track"] == track
        ]
        reviewed = [c for c in pool if c["scores"]]
        hit = (
            round(sum(c["scores"][-1] for c in reviewed) / len(reviewed), 3)
            if reviewed
            else 0.0
        )
        stats[track] = {
            "concepts": len(pool),
            "reviewed": len(reviewed),
            "hit_rate": hit,
        }
    return stats


# ------------------------------------------------------------ the drill
def _memory_records() -> list[tuple[str, str]]:
    """Durable memory as (text, session_id) pairs: corpus + journal."""
    from levi.academy import corpus_ingest as aci

    records: list[tuple[str, str]] = []
    cpath = aci.corpus_path()
    if cpath.exists():
        with open(cpath, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = f"d{rec.get('day', 0)}b{rec.get('block', 0)}"
                records.append((rec.get("text", ""), sid))
    try:
        from levi.growth import journal as gjournal

        for e in gjournal.read_entries(limit=400):
            if e.get("kind") not in (
                "academy-session",
                "academy-graduation",
                "academy-remedial",
            ):
                continue
            text = f"{e.get('title', '')} {e.get('summary', '')}"
            sid = f"d{e.get('day', 0)}b{e.get('block', 0)}"
            records.append((text, sid))
    except Exception:
        pass
    return records


def drill_concept(concept: dict, session_n: int, closed_book: bool = False) -> dict:
    """One retrieval drill: can durable memory reconstruct this concept?

    Never re-reading. The drill poses a retrieval question and scores how
    well the best-matching memory passage covers the concept's content
    words. ``closed_book=True`` excludes the concept's own introductory
    records — the true retention test.
    """
    words = set(concept.get("content_words", []))
    if not words:
        return {
            "concept_id": concept["id"],
            "score": 0.0,
            "question": "",
            "recalled": "",
        }
    own_sid = f"d{concept['day']}b{concept['block']}"
    best_text, best_overlap = "", 0
    elaboration = 0
    for text, sid in _memory_records():
        if closed_book and sid == own_sid:
            continue
        tw = set(re.findall(r"[a-z]{3,}", text.lower()))
        overlap = len(words & tw)
        if overlap >= 2:
            elaboration += 1
        if overlap > best_overlap:
            best_overlap, best_text = overlap, text
    recall = best_overlap / len(words)
    elab = min(1.0, elaboration / 3)
    hit = 1.0 if best_text else 0.0
    score = round(0.5 * recall + 0.3 * elab + 0.2 * hit, 3)
    question = (
        f"Retrieve from memory: '{concept['name']}' — state its "
        f"operational core and the evidence or procedure behind it."
    )
    return {
        "concept_id": concept["id"],
        "score": score,
        "question": question,
        "recalled": best_text[:300],
        "closed_book": closed_book,
    }


def run_reviews(session_n: int, assessment: bool = False) -> dict:
    """Run this session's due review drills. Returns the review report."""
    limit = ASSESSMENT_REVIEWS if assessment else MAX_REVIEWS_PER_SESSION
    due = due_concepts(session_n, limit=limit)
    results = []
    forgotten: list[str] = []
    for c in due:
        idx = c.pop("_review_idx")
        # First scheduled review (offset +1) consolidates open-book;
        # later reviews are closed-book retention tests.
        closed_book = idx > 0
        drill = drill_concept(c, session_n, closed_book=closed_book)
        upd = record_review(c["id"], session_n, drill["score"])
        results.append(
            {
                "concept_id": c["id"],
                "name": c["name"],
                "track": c["track"],
                "score": drill["score"],
                "closed_book": closed_book,
                "forgotten": upd.get("forgotten", False),
            }
        )
        if upd.get("forgotten"):
            forgotten.append(c["id"])
    mean = round(sum(r["score"] for r in results) / len(results), 3) if results else 1.0
    return {
        "reviewed": len(results),
        "mean_score": mean,
        "forgotten": forgotten,
        "results": results,
        "assessment": assessment,
    }
