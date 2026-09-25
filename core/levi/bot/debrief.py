"""End-of-day debrief bot — the evening mirror of the check-in bot.

The check-in bot asks one question in the morning; the debrief asks one
at the close of the day. Same contract, opposite end of the day: the
question is deterministic by date (the same date always closes with the
same question), answers are an append-only journal at
``~/.levi/bot/debriefs.jsonl`` (owner-only), and a missed evening leaves
no record and breaks nothing.

:func:`pair_status` reports the day's bookends — check-in plus debrief —
as one honest state: a day is "closed" only when both ends are answered.

Laws
----
- append-only: answers are never overwritten; answering twice keeps
  both, newest wins in :func:`todays`
- deterministic rotation: day-of-year modulo the bank length — no state
  is stored to pick the question
- skippable: a missed day leaves no record; nothing downstream may
  treat a missing debrief as an error
- owner-only store: the journal file is chmod 600, written atomically
  (temp file + replace)
- deny-closed inputs: blank or over-long answers are refused with
  ``ValueError``; corrupt journal lines are skipped on read, never
  repaired or trusted
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

#: The evening question bank — LEVI-original, deliberately closing.
#: Rotation is day-of-year modulo the bank length, so the sequence is
#: stable and predictable without any stored state.
QUESTIONS: List[str] = [
    "What actually closed today — and what is still open?",
    "What carried over that should not have?",
    "What is the one thing tomorrow must not repeat?",
    "What did you finish that deserves to be named?",
    "What is unfinished, and what is its honest next step?",
    "Who did you fail to show up for today?",
    "What cost more than it should have — time, energy, or money?",
    "What is the sharpest loose end on your mind right now?",
    "What did the day teach you that the morning did not know?",
    "What are you still carrying into sleep that can wait?",
    "What deserves thanks before the day ends?",
    "Close the day in one sentence.",
]

_MAX_ANSWER_CHARS = 10_000


def _home() -> Path:
    return Path.home()


def _store_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "bot" / "debriefs.jsonl"


def _today_iso(day: Optional[_dt.date] = None) -> str:
    return (day or _dt.date.today()).isoformat()


def question_for(day: Optional[_dt.date] = None) -> str:
    """The debrief question for ``day`` (default today).

    Deterministic rotation: day-of-year modulo the bank length. The same
    date always closes with the same question; no state is stored.
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
    """Record tonight's debrief answer. Blank answers are refused.

    Journal semantics: every answer is appended; answering twice keeps
    both, newest wins in :func:`todays`.
    """
    text = str(text or "").strip()
    if not text:
        raise ValueError("debrief answer cannot be blank — nothing recorded.")
    if len(text) > _MAX_ANSWER_CHARS:
        raise ValueError(f"debrief answer is too long (max {_MAX_ANSWER_CHARS} chars).")
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
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".debriefs-")
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
    """Tonight's debrief state: question, whether answered, latest answer."""
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
    """Past debriefs, newest first. Corrupt lines are skipped."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, limit)
    records = _read_records(home)
    return list(reversed(records[-limit:]))


def format_debrief(state: Dict[str, Any]) -> str:
    """Render tonight's debrief state as plain text — the form a bot speaks."""
    lines = [f"Debrief — {state['date']}", "", f"Q: {state['question']}", ""]
    if state["answered"]:
        lines.append(f"A: {state['answer']}")
    else:
        lines.append("(no answer yet — say the word and it is recorded)")
    return "\n".join(lines) + "\n"


def pair_status(
    *,
    day: Optional[_dt.date] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """The day's bookends: check-in state plus debrief state, one dict.

    A day is "closed" only when both ends are answered. The check-in half
    is read, never written, here. Importing checkin lazily keeps this
    module importable on its own.
    """
    from levi.bot import checkin

    check = checkin.todays(day=day, home=home)
    debrief = todays(day=day, home=home)
    closed = bool(check["answered"] and debrief["answered"])
    return {
        "date": _today_iso(day),
        "checkin": check,
        "debrief": debrief,
        "closed": closed,
    }


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "bot-debrief",
            provides=(
                "bot.debrief.question",
                "bot.debrief.answer",
                "bot.debrief.pair-status",
            ),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
