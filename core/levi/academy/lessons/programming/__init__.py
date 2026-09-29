"""Chauncey's 14-lesson programming course — teachable academy layer.

Structured lesson records (order, core ideas, examples with captured
outputs, exercises with hints) built deterministically from the course
source by ``build_programming_lessons.py``. The PDF under
``~/workspace/your_files/programming-full-course/`` remains the readable
edition; this package is how LEVI teaches and queries the course through
its own commands (``levi academy programming ...``).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LESSONS_PATH = HERE / "lessons.json"
MANIFEST_PATH = HERE / "manifest.json"

_cache: list[dict] | None = None


def load_lessons() -> list[dict]:
    """All 14 lessons, in course order. Cached after first load."""
    global _cache
    if _cache is None:
        _cache = json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
    return _cache


def syllabus() -> list[tuple[int, str, str]]:
    """Ordered (n, id, title) triples."""
    return [(l["n"], l["id"], l["title"]) for l in load_lessons()]


def get_lesson(key: int | str) -> dict:
    """Fetch a lesson by number (1-14), id slug, or title.

    Raises KeyError with the valid ids when the key matches nothing.
    """
    lessons = load_lessons()
    if isinstance(key, int) or (isinstance(key, str) and key.strip().isdigit()):
        n = int(key)
        for l in lessons:
            if l["n"] == n:
                return l
    else:
        want = str(key).strip().lower()
        for l in lessons:
            if l["id"] == want or l["title"].lower() == want:
                return l
    valid = ", ".join(f"{l['n']}={l['id']}" for l in lessons)
    raise KeyError(f"unknown programming lesson {key!r} (valid: {valid})")


def next_lesson(after: int | str | None = None) -> dict | None:
    """The lesson after ``after`` (lesson 1 when ``after`` is None).

    Returns None past the capstone.
    """
    lessons = load_lessons()
    if after is None:
        return lessons[0]
    cur = get_lesson(after)
    idx = lessons.index(cur)
    return lessons[idx + 1] if idx + 1 < len(lessons) else None


def search(query: str) -> list[dict]:
    """Case-insensitive substring search over titles, ideas, prose,
    example titles, and exercise tasks. Returns lessons in order."""
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for l in load_lessons():
        hay = " ".join(
            [
                l["title"],
                l["subtitle"],
                l["idea"],
                *[p["text"] for p in l["prose"]],
                *[e["title"] for e in l["examples"]],
                *[e["task"] for e in l["exercises"]],
            ]
        ).lower()
        if q in hay:
            hits.append(l)
    return hits


def format_lesson(lesson: dict) -> str:
    """Plain-text teachable rendering of one lesson."""
    total = len(load_lessons())
    lines = [
        f"Lesson {lesson['n']}/{total} — {lesson['title']}",
        lesson["subtitle"],
        "",
        f"Core idea: {lesson['idea']}",
    ]
    for p in lesson["prose"]:
        text = p["text"]
        if p["kind"] == "h2":
            lines += ["", f"## {text}"]
        elif p["kind"] == "note":
            lines += ["", f"Note: {text}"]
        else:
            lines += ["", text]
    for e in lesson["examples"]:
        lines += ["", f"--- {e['title']} ---"]
        if e["kind"] == "shell":
            lines.append("(shell)")
        lines.append(e["code"])
        if e.get("stdin") is not None:
            lines.append(f"(typed at the prompt: {e['stdin'].strip()})")
        if e.get("output") is not None:
            lines += ["(output)", e["output"].rstrip("\n")]
    if lesson["exercises"]:
        lines += ["", "Your try:"]
        for i, ex in enumerate(lesson["exercises"], 1):
            lines.append(f"  {i}. {ex['task']}")
            if ex.get("detail"):
                lines.append(f"     {ex['detail']}")
            if ex.get("hint"):
                lines.append(f"     Hint: {ex['hint']}")
    return "\n".join(lines).rstrip("\n") + "\n"
