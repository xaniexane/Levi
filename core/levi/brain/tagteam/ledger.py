"""Round ledger: the append-only log of every tag-team round.

Each round appends exactly one entry — whatever happened, including
honest skips (no torch, dry-run, aborted on eval-prompt contamination).
The ledger is the memory of the loop: the next round reads the last
entry's eval scores for its gap report and its teacher history for
rotation.

Schema ``levi-tagteam-round/1``. Entries are JSON lines; the file is
never rewritten, only appended. Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "levi-tagteam-round/1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_entry(round_n: int, **fields: Any) -> dict[str, Any]:
    """Build a ledger entry. ``round`` and ``ts`` are always set."""
    entry: dict[str, Any] = {
        "schema": SCHEMA,
        "round": round_n,
        "ts": utc_now_iso(),
    }
    entry.update(fields)
    return entry


def append_entry(ledger_path: Path, entry: dict[str, Any]) -> None:
    """Append one entry. The ledger file is created on first use."""
    ledger_path = Path(ledger_path)
    if entry.get("schema") != SCHEMA:
        raise ValueError(f"ledger entry has wrong schema: {entry.get('schema')!r}")
    if "round" not in entry or "ts" not in entry:
        raise ValueError("ledger entry needs 'round' and 'ts'")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_entries(ledger_path: Path) -> list[dict[str, Any]]:
    """Read all entries in order. Missing file -> empty list (round 1)."""
    ledger_path = Path(ledger_path)
    if not ledger_path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    with open(ledger_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"ledger corrupt at line {lineno}: {exc}"
                    ) from exc
    return entries


def last_entry(ledger_path: Path) -> dict[str, Any] | None:
    entries = read_entries(ledger_path)
    return entries[-1] if entries else None


def prev_scores(ledger_path: Path) -> dict[str, float]:
    """Eval scores from the most recent round that recorded any."""
    for entry in reversed(read_entries(ledger_path)):
        scores = (entry.get("eval") or {}).get("scores")
        if scores:
            return dict(scores)
    return {}


def teacher_history(ledger_path: Path) -> dict[str, list[str]]:
    """Topic -> seats used in the most recent round (for rotation)."""
    for entry in reversed(read_entries(ledger_path)):
        hist = entry.get("teacher_history")
        if hist:
            return {t: list(s) for t, s in hist.items()}
    return {}


def round_conditions(ledger_path: Path) -> list[list[dict[str, Any]]]:
    """Persona-condition frames per round, oldest first.

    Every entry records its round's conditioning frames under
    ``"conditions"`` (all provisional until Chauncey names the final
    persona set). Rounds before conditioning existed report [].
    """
    return [list(entry.get("conditions") or []) for entry in read_entries(ledger_path)]
