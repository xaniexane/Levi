"""Daily check-in bot — one question a day, answered in plain words.

The check-in bot picks a rotating reflective question (deterministic by
date — the same date always asks the same question), records the answer
to ``~/.levi/bot/checkins.jsonl`` (owner-only), and reports history.
Answers are a journal: every answer is appended, never overwritten;
``todays()`` reports the latest answer for the current date.

Skippable by design: a missed day leaves no record and breaks nothing.
Pure stdlib, local-first. ``home`` is injectable everywhere so tests
never touch the real ``~/.levi``.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

#: The question bank — LEVI-original, deliberately concrete. Rotation is
#: day-of-year modulo the bank length, so the sequence is stable and
#: predictable without any stored state.
QUESTIONS: List[str] = [
    "What is one thing that actually moved today?",
    "What are you avoiding, and what is it costing?",
    "What did you build today that did not exist yesterday?",
    "Who did you show up for today?",
    "What is the sharpest thing on your mind right now?",
    "What would you do today if you trusted yourself completely?",
    "What drained you today, and what fed you?",
    "What is one small thing you could finish before sleep?",
    "What surprised you today?",
    "What are you carrying that is not yours to carry?",
    "What does tomorrow need from you?",
    "What is true right now that you have been dancing around?",
]


def _home() -> Path:
    return Path.home()


def _store_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "bot" / "checkins.jsonl"


def _today_iso(day: Optional[_dt.date] = None) -> str:
    return (day or _dt.date.today()).isoformat()


def question_for(day: Optional[_dt.date] = None) -> str:
    """The check-in question for ``day`` (default today).

    Deterministic rotation: day-of-year modulo the bank length. The same
    date always asks the same question; no state is stored.
    """
    day = day or _dt.date.today()
    index = (day.timetuple().tm_yday - 1) % len(QUESTIONS)
    return QUESTIONS[index]


def _read_records(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _store_file(home)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict) and raw.get("date") and raw.get("answer"):
            records.append(raw)
    return records


def answer(
    text: str,
    *,
    day: Optional[_dt.date] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record today's answer. Blank answers are refused (ValueError).

    Journal semantics: every answer is appended; answering twice keeps
    both, newest wins in ``todays()``.
    """
    text = str(text or "").strip()
    if not text:
        raise ValueError("check-in answer cannot be blank — nothing recorded.")
    if len(text) > 10_000:
        raise ValueError("check-in answer is too long (max 10,000 chars).")
    date_iso = _today_iso(day)
    record = {
        "date": date_iso,
        "question": question_for(day),
        "answer": text,
        "recorded_at": _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    path = _store_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".checkins-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            if path.exists():
                fh.write(path.read_text(encoding="utf-8"))
            fh.write(line)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return record


def todays(
    *,
    day: Optional[_dt.date] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Today's check-in state: question, whether answered, latest answer."""
    date_iso = _today_iso(day)
    latest: Optional[Dict[str, Any]] = None
    for record in _read_records(home):
        if record.get("date") == date_iso:
            latest = record
    return {
        "date": date_iso,
        "question": question_for(day),
        "answered": latest is not None,
        "answer": latest.get("answer") if latest else None,
    }


def history(*, home: Optional[Path] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """Past check-ins, newest first. Corrupt lines are skipped."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, limit)
    records = _read_records(home)
    return list(reversed(records[-limit:]))


def format_checkin(state: Dict[str, Any]) -> str:
    """Render today's check-in state as plain text — the form a bot speaks."""
    lines = [f"Check-in — {state['date']}", "", f"Q: {state['question']}", ""]
    if state["answered"]:
        lines.append(f"A: {state['answer']}")
    else:
        lines.append("(no answer yet — say the word and it is recorded)")
    return "\n".join(lines) + "\n"
