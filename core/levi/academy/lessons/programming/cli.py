"""CLI dispatch for the programming course: ``levi academy programming ...``.

Usage:
  programming                  syllabus (same as: programming syllabus)
  programming syllabus         list the 14 lessons in order
  programming lesson <n|id>    teach one lesson
  programming next [--after N] teach the next lesson (default: after none = 1)
  programming search <words>   find lessons about the words
"""

from __future__ import annotations

from . import format_lesson, get_lesson, load_lessons, next_lesson, search, syllabus


def _print_syllabus() -> int:
    lessons = load_lessons()
    print("Programming course — 14 lessons:")
    for n, lid, title in syllabus():
        sub = lessons[n - 1]["subtitle"]
        print(f"  {n:2d}. {title} [{lid}] — {sub}")
    print("\nusage: levi academy programming lesson <n|id>")
    return 0


def main(argv=None) -> int:
    words = list(argv or [])
    if not words or words[0] == "syllabus":
        return _print_syllabus()
    if words[0] == "lesson":
        if len(words) < 2:
            print("usage: levi academy programming lesson <n|id>")
            return 2
        try:
            lesson = get_lesson(words[1])
        except KeyError as exc:
            print(exc)
            return 2
        print(format_lesson(lesson), end="")
        return 0
    if words[0] == "next":
        after = None
        rest = words[1:]
        if rest[:1] == ["--after"] and len(rest) >= 2:
            after = rest[1]
        elif rest:
            print("usage: levi academy programming next [--after N]")
            return 2
        try:
            lesson = next_lesson(after)
        except KeyError as exc:
            print(exc)
            return 2
        if lesson is None:
            print("Capstone complete — that's all 14 lessons. Keep shipping.")
            return 0
        print(format_lesson(lesson), end="")
        return 0
    if words[0] == "search":
        if len(words) < 2:
            print("usage: levi academy programming search <words>")
            return 2
        hits = search(" ".join(words[1:]))
        if not hits:
            print("No programming lessons match.")
            return 1
        for l in hits:
            print(f"  {l['n']:2d}. {l['title']} [{l['id']}]")
        return 0
    print(__doc__.strip())
    return 2
