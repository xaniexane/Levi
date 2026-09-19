"""Append-only dream journal (JSONL, owner-only).

Dreams are records, never actions. The journal is the dream book LEVI and
the legion learn from — outcomes simulated, lessons compressed.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def default_journal_path() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "dream" / "journal.jsonl"


def enforce_owner_only(path: Path) -> None:
    """Lock a file (0600) and its parent dir (0700) to the owner.

    Best-effort on non-POSIX platforms; raises PermissionError on POSIX
    when the result cannot be verified.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        pass
    if os.name == "posix" and not owner_only_ok(path):
        raise PermissionError("could not enforce owner-only perms on %s" % path)


def owner_only_ok(path: Path) -> bool:
    """Check that ``path`` (and its parent dir) are not group/other readable.

    A missing file fails open (nothing to leak); an existing file must be
    0600 (no group/other bits) and its parent dir must be 0700 or tighter.
    """
    if os.name != "posix":
        return True
    try:
        mode = os.stat(path).st_mode & 0o777
        if mode & 0o077:
            return False
        dmode = os.stat(path.parent).st_mode & 0o777
        return dmode & 0o077 == 0
    except OSError:
        return False


class DreamJournal:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_journal_path()

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = dict(record)
        entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # owner-only permissions, verified in code (POSIX)
        enforce_owner_only(self.path)
        return entry

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for _ in self.path.open(encoding="utf-8"))
