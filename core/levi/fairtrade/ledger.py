"""The honest-trade ledger.

The inversion of the sly trade: every LEVI generosity is declared up
front, with its true cost written down where the user can read it.

Declarations append to ``~/.levi/fairtrade/ledger.jsonl`` — one JSON
object per line, owner-only permissions (dir 0o700, file 0o600).
The ledger is append-only: a bad declaration is corrected by a new one,
never rewritten.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def default_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".levi" / "fairtrade"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def declare_trade(
    name: str,
    gives: List[str],
    asks: List[str],
    note: str = "",
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write one honest-trade declaration to the ledger.

    ``asks`` may be an empty list — but only if the trade genuinely asks
    nothing (e.g. a pure archive entry). For anything with a hidden cost,
    honesty demands listing it here, not burying it.
    """
    name = str(name).strip()
    if not name:
        raise ValueError("declaration needs a name")
    gives = [str(g).strip() for g in gives if str(g).strip()]
    if not gives:
        raise ValueError("declaration must say what it gives")

    record = {
        "declared_at": _utcnow(),
        "name": name,
        "gives": gives,
        "asks": [str(a).strip() for a in asks if str(a).strip()],
        "note": str(note).strip(),
    }
    d = default_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    path = d / "ledger.jsonl"
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".tmp-")
    try:
        existing = []
        if path.exists():
            existing = path.read_text(encoding="utf-8").splitlines()
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for line in existing:
                if line.strip():
                    fh.write(line + "\n")
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return record


def read_ledger(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = default_dir(home) / "ledger.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
