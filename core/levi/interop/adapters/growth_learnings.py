"""Adapter: growth journal ← bot pending-learnings queue.

The bot writes candidate learnings to ``~/.levi/bot/pending_learnings.jsonl``
(one JSON object per line). This adapter consumes that queue into the growth
journal via the journal's public ``append_entry`` API.

Contract::

    consume_pending_learnings(queue_path, journal) ->
        {"accepted": int, "rejected": int, "backup": str | None,
         "journaled_ids": [...], "rejections": [...]}

- ``journal`` is the :mod:`levi.growth.journal` module or any duck-typed
  object exposing ``append_entry(dict) -> dict``.
- Validation is deny-closed per line: a candidate must be a dict with a
  non-empty ``text`` (or ``learning``) field. Malformed JSON lines and
  invalid candidates are counted as rejected and listed in
  ``"rejections"`` — never journaled.
- **Idempotent**: the queue file is renamed to
  ``<queue>.consumed-<UTC-timestamp>`` *before* journaling begins, so a
  consumed line can never be reprocessed, even if the process dies mid-run
  (a crash may leave a partially-consumed queue, which the next run still
  consumes exactly once — the backup always holds the full original).

The journal only ever receives growth-kind entries; this adapter does not
touch memory, tools, policy, or identity.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _validate_candidate(raw: Any, lineno: int) -> Dict[str, Any]:
    """Return a normalized learning dict, or raise ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("line %d: not a JSON object" % lineno)
    text = raw.get("text", raw.get("learning", ""))
    if not isinstance(text, str) or not text.strip():
        raise ValueError("line %d: missing non-empty 'text'/'learning'" % lineno)
    entry = {
        "kind": "learning",  # journal kind; the bot's candidate kind is kept below
        "text": text.strip(),
        "source": str(raw.get("source", "bot-pending-queue") or "bot-pending-queue"),
        "provisional": True,
    }
    candidate_kind = raw.get("kind")
    if isinstance(candidate_kind, str) and candidate_kind.strip():
        entry["candidate_kind"] = candidate_kind.strip()
    for key in ("confidence", "status", "ts", "tags", "context"):
        if key in raw:
            entry[key] = raw[key]
    return entry


def consume_pending_learnings(queue_path, journal) -> Dict[str, Any]:
    """Consume the pending-learnings queue into the growth journal.

    ``queue_path`` may be a str or :class:`pathlib.Path`. ``journal`` must
    expose ``append_entry``. Returns the consumption summary (see module
    docstring). Never raises on a missing queue — that is a normal idle
    state, reported honestly.
    """
    summary: Dict[str, Any] = {
        "accepted": 0,
        "rejected": 0,
        "backup": None,
        "journaled_ids": [],
        "rejections": [],
    }
    append = getattr(journal, "append_entry", None)
    if not callable(append):
        raise ValueError(
            "consume_pending_learnings: journal must expose append_entry()"
        )
    path = Path(queue_path)
    if not path.exists():
        summary["rejections"] = []
        return summary  # idle: nothing pending, nothing journaled

    # Move first: idempotency. From here on, no second run can see these lines.
    backup = path.with_name("%s.consumed-%s" % (path.name, _utc_stamp()))
    shutil.move(str(path), str(backup))
    summary["backup"] = str(backup)

    lines = backup.read_text(encoding="utf-8").splitlines()
    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError as exc:
            summary["rejected"] += 1
            summary["rejections"].append("line %d: invalid JSON (%s)" % (lineno, exc))
            continue
        try:
            entry = _validate_candidate(raw, lineno)
        except ValueError as exc:
            summary["rejected"] += 1
            summary["rejections"].append(str(exc))
            continue
        recorded = append(entry) or {}
        summary["accepted"] += 1
        jid = recorded.get("id") if isinstance(recorded, dict) else None
        summary["journaled_ids"].append(jid)
    return summary


def default_queue_path() -> Path:
    """``~/.levi/bot/pending_learnings.jsonl`` (override with
    ``LEVI_BOT_DIR``)."""
    base = os.environ.get("LEVI_BOT_DIR")
    root = Path(base).expanduser() if base else Path.home() / ".levi" / "bot"
    return root / "pending_learnings.jsonl"
