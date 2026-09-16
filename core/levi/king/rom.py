"""King's own Wyrd-ROM — rupture-lock for multi-engine sessions.

THE DIVISION (do not collapse these two):

* ``lwp.model_engine.LWPModelEngine.wyrd_rupture()`` locks *prose canon
  inside one continuous manuscript*: a ROM lens, a rate-limited budget
  (~1 per 20k words), an immutable scene sealed into that manuscript's
  bible. Its scope is one engine, one manuscript.

* ``king.rom.SessionRom.rupture_session()`` locks *continuity state of a
  King-orchestrated multi-engine session*: a sha256 fingerprint of the
  continuity ledger (entities + causal edges + harvests + totals across
  BOTH engines) at a moment in time, with a human-readable reason. Its
  scope is the session, not any single manuscript.

A rupture inside a King session is a different kind of commitment than
a rupture inside one manuscript — the first says "this is what the
whole control plane believed at time T," the second says "this prose is
canon for this manuscript." They answer different questions, they are
consumed by different review paths, and merging them would trade real
usage friction for tidiness (blueprint §4). ``levi king rupture``
passes through to the manuscript engine (blueprint §4 CLI list);
``levi king d5`` exercises *this* ROM by sealing the promoted session
baseline.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ledger import _default_data_dir, _write_json_600


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRom:
    """Append-only rupture locks for King multi-engine sessions."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else _default_data_dir()
        self.path = self.data_dir / "rom.json"
        self.locks: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return
        if isinstance(raw, dict):
            locks = raw.get("locks", []) or []
            self.locks = [l for l in locks if isinstance(l, dict)]

    def _persist(self) -> None:
        _write_json_600(self.path, {"locks": self.locks})

    def rupture_session(self, reason: str, fingerprint: str) -> Dict[str, Any]:
        """Seal one multi-engine session state. Append-only; never edits."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                f"rupture reason must be a non-empty string, got {reason!r}"
            )
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise ValueError(
                f"rupture fingerprint must be a non-empty string, got {fingerprint!r}"
            )
        lock = {
            "id": "rom." + uuid.uuid4().hex[:10],
            "ts": _utcnow(),
            "reason": reason,
            "ledger_fingerprint": fingerprint,
            "scope": "king-session",
            "engine_scope": "multi-engine",
        }
        self.locks.append(lock)
        self._persist()
        return lock

    def latest(self) -> Optional[Dict[str, Any]]:
        return self.locks[-1] if self.locks else None

    def count(self) -> int:
        return len(self.locks)

    def verify(self, lock_id: str, fingerprint: str) -> bool:
        """Check that a lock still matches a ledger fingerprint."""
        for lock in self.locks:
            if lock.get("id") == lock_id:
                return lock.get("ledger_fingerprint") == fingerprint
        return False
