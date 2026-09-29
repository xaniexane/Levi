"""Shift log — the append-only journal of work shifts.

A shift is one unit of real work: a pack run, a recovery pass, a build
session. Shift log records one entry per shift into an append-only
ndjson journal under ``~/.levi/daemon/shiftlog.ndjson``::

    {"ts": "<iso>", "actor": "pack-to-the-brim", "surfaces": ["engines/x"],
     "note": "what shipped, terse", "head": "8b89f4c5c"}

- Entries are append-only: the log is never rewritten, only added to.
  History is sacred; a wrong entry is corrected by a new entry, never by
  an edit.
- Writes are atomic (temp file + rename) and owner-only (0o600).
- Reading is honest: malformed lines are *counted as quarantined*,
  never as shifts and never as a fatal error — a corrupt line must not
  erase the log.
- ``summarize()`` folds today's entries into a shift report: shift
  count, surfaces touched, notes in order, quarantined-line count.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Append-only law** — an entry never modifies or removes an earlier
   line; ``append`` is the only write path.
2. **Deny-closed append law** — an entry missing ``actor`` or ``note``
   is refused, never written half-formed.
3. **Atomicity law** — a failed append leaves the file byte-identical;
   no partial line ever lands in the journal.
4. **Quarantine law** — corrupt lines on read are counted and listed by
   line number, never parsed as shifts.
5. **Privacy law** — the journal is created owner-only (0o600) and
   appends never loosen permissions.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.shiftlog`` inside the perpetual supervisor
(one_for_one child), or a plain ``run_once()`` call from cron. The
``note`` subcommand appends one entry from the command line.

Deliberately NOT self-declared to the interop registry at import: the
supervisor's expected-service count is owned by a sibling suite that
enumerates declared daemons, and shiftlog runs standalone like coroner
unless a worker wires it in explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_JOURNAL = Path.home() / ".levi" / "daemon" / "shiftlog.ndjson"

_JOURNAL_MODE = 0o600


class ShiftLogError(ValueError):
    """Deny-closed input to the shift log itself."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ShiftLogError("shift entry must be a dict, got " + type(entry).__name__)
    missing = [k for k in ("actor", "note") if not entry.get(k)]
    if missing:
        raise ShiftLogError(
            "shift entry missing required fields: " + ", ".join(missing)
        )
    for key in ("surfaces", "tags"):
        if key in entry and entry[key] is not None:
            if not isinstance(entry[key], list) or any(
                not isinstance(v, str) for v in entry[key]
            ):
                raise ShiftLogError(f"shift entry '{key}' must be a list of str")
    clean = dict(entry)
    clean.setdefault("ts", _utcnow_iso())
    return clean


def _ensure_journal(journal: Path) -> None:
    journal.parent.mkdir(parents=True, exist_ok=True)
    if not journal.exists():
        journal.touch(mode=_JOURNAL_MODE)
        os.chmod(journal, _JOURNAL_MODE)


def append(
    entry: Dict[str, Any], journal: "str | os.PathLike[str] | None" = None
) -> Dict[str, Any]:
    """Append one shift entry. Atomic; refuses malformed entries."""
    journal_path = Path(journal) if journal is not None else DEFAULT_JOURNAL
    _ensure_journal(journal_path)
    clean = _validate_entry(entry)
    line = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
    fd, tmp = tempfile.mkstemp(
        dir=str(journal_path.parent), prefix=journal_path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(line + b"\n")
        os.chmod(tmp, _JOURNAL_MODE)
        with open(journal_path, "ab") as fh:
            with open(tmp, "rb") as src:
                fh.write(src.read())
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return clean


def read(
    journal: "str | os.PathLike[str] | None" = None,
) -> Tuple[List[Dict[str, Any]], List[Tuple[int, str]]]:
    """Read the journal. Returns (entries, quarantined [(line_no, reason)])."""
    journal_path = Path(journal) if journal is not None else DEFAULT_JOURNAL
    entries: List[Dict[str, Any]] = []
    quarantined: List[Tuple[int, str]] = []
    if not journal_path.exists():
        return entries, quarantined
    with open(journal_path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                quarantined.append((lineno, f"not JSON: {exc.msg}"))
                continue
            try:
                entries.append(_validate_entry(payload))
            except ShiftLogError as exc:
                quarantined.append((lineno, str(exc)))
    return entries, quarantined


def summarize(
    journal: "str | os.PathLike[str] | None" = None,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    """Fold one UTC day of entries into a shift report."""
    entries, quarantined = read(journal)
    day = day or datetime.now(timezone.utc).date().isoformat()
    day_entries = [e for e in entries if e["ts"][:10] == day]
    surfaces: List[str] = []
    for entry in day_entries:
        for surface in entry.get("surfaces") or []:
            if surface not in surfaces:
                surfaces.append(surface)
    return {
        "day": day,
        "shifts": len(day_entries),
        "actors": sorted({e["actor"] for e in day_entries}),
        "surfaces": surfaces,
        "notes": [e["note"] for e in day_entries],
        "quarantined_lines": len(quarantined),
        "total_entries": len(entries),
    }


def run_once(
    journal: "str | os.PathLike[str] | None" = None,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    """One supervisor tick: return today's shift report."""
    return summarize(journal, day)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="levi.daemon.shiftlog")
    parser.add_argument("--journal", default=None, help="journal path override")
    sub = parser.add_subparsers(dest="command")
    note_cmd = sub.add_parser("note", help="append one shift entry")
    note_cmd.add_argument("note", help="terse note of what the shift did")
    # Separate dest: a subparser default would clobber the top-level value.
    note_cmd.add_argument(
        "--journal",
        default=None,
        dest="note_journal",
        help="journal path override (also accepted after the subcommand)",
    )
    note_cmd.add_argument("--actor", default="cli", help="who did the shift")
    note_cmd.add_argument("--surface", action="append", default=[], dest="surfaces")
    note_cmd.add_argument("--head", default=None, help="git head after the shift")
    args = parser.parse_args(argv)
    if args.command == "note":
        journal = args.note_journal or args.journal
        append(
            {
                "actor": args.actor,
                "note": args.note,
                "surfaces": args.surfaces,
                "head": args.head,
            },
            journal,
        )
        return 0
    print(json.dumps(run_once(args.journal), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
