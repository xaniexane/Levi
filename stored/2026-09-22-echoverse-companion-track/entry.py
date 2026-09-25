"""Echoverse SFW entry points — the surface the separation audit proves clean.

Phase 0 seed. These entry points are deliberately small: a zone status
probe and a local SFW session (open / log / close) backed by 0600 files
under ``~/.levi/echoverse/``. Later milestones grow companion depth,
the branching simulator, and wellness rituals on top of this surface.

Hard rules for this module (and everything the audit covers):
  - NEVER import anything from ``levi.plaiground`` — the adult package
    is not a dependency, not a fallback, not a lazy import.
  - NEVER touch PINs, gates, or adult entries. There is nothing to
    PIN-gate on the SFW track, so adult gating is N/A here.
  - stdlib only, no network, no analytics, no accounts. Opt-in: every
    function takes ``home`` explicitly; nothing writes the real
    ``~/.levi`` unless the caller points it there.

Paired-mind shape: a session is a pair — the *ledger* (what happened,
owner-readable) and the *witness* (an append-only hash chain over the
ledger so a later phase can prove nothing was rewritten). Two sides,
one session; each exists only against the other.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.echoverse import themes

ZONE = "echoverse"
_ZONE_DIRNAME = "echoverse"
_RECORD_MODE = 0o600

__all__ = [
    "ZONE",
    "Session",
    "close_session",
    "log_line",
    "open_session",
    "read_ledger",
    "zone_dir",
    "zone_status",
]


# ---------------------------------------------------------------------------
# Paths — caller-supplied home only.
# ---------------------------------------------------------------------------


def zone_dir(home: Optional[Path] = None) -> Path:
    """``~/.levi/echoverse`` under the caller-supplied home (never assumed)."""
    base = Path(home) if home is not None else Path.home()
    return base / ".levi" / _ZONE_DIRNAME


def _write_private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, _RECORD_MODE)
    return path


# ---------------------------------------------------------------------------
# Zone status — the honest probe.
# ---------------------------------------------------------------------------


def zone_status(home: Optional[Path] = None) -> Dict[str, Any]:
    """Describe the Echoverse zone without touching any adult surface.

    Read-only except for nothing: it creates no records and flips no
    switches. The returned ``sfw_only`` flag is a declaration the
    separation audit verifies in code.
    """
    return {
        "zone": ZONE,
        "track": "sfw",
        "sfw_only": True,
        "adult_gating": "n/a — no adult surface in this package",
        "local_first": True,
        "network": "none",
        "theme": themes.active_theme(home),
        "dir": str(zone_dir(home)),
    }


# ---------------------------------------------------------------------------
# Sessions — the paired ledger + witness.
# ---------------------------------------------------------------------------


class Session:
    """An open SFW session: ledger (what happened) + witness (hash chain).

    The witness chains ``sha256(prev_hash + line)`` per logged line, so
    any rewrite of the ledger breaks the chain. The session itself is
    local and private — readable by the owner, by nobody else.
    """

    def __init__(self, home: Path, session_id: str) -> None:
        self.home = Path(home)
        self.session_id = session_id
        self._dir = zone_dir(self.home) / "sessions" / session_id
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self._dir / "ledger.jsonl"
        self._witness_path = self._dir / "witness.txt"
        if not self._witness_path.exists():
            self._write_witness("genesis")
        self._open = True

    # -- witness ------------------------------------------------------
    def _last_hash(self) -> str:
        try:
            return (
                self._witness_path.read_text(encoding="utf-8").strip().splitlines()[-1]
            )
        except (OSError, IndexError):
            return "genesis"

    def _write_witness(self, digest: str) -> None:
        with open(self._witness_path, "a", encoding="utf-8") as fh:
            fh.write(digest + "\n")
        os.chmod(self._witness_path, _RECORD_MODE)

    # -- ledger -------------------------------------------------------
    @staticmethod
    def _clean_line(line: str) -> str:
        if not isinstance(line, str) or not line.strip():
            raise ValueError("log_line needs a non-empty string.")
        cleaned = " ".join(line.split())
        if len(cleaned) > 2000:
            raise ValueError("log_line too long (max 2000 chars).")
        return cleaned

    def log(self, line: str) -> Dict[str, str]:
        """Append one owner-readable line; extend the witness chain."""
        if not self._open:
            raise ValueError("session is closed.")
        cleaned = self._clean_line(line)
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "line": cleaned,
        }
        with open(self._ledger_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        os.chmod(self._ledger_path, _RECORD_MODE)
        digest = hashlib.sha256(
            (self._last_hash() + cleaned).encode("utf-8")
        ).hexdigest()
        self._write_witness(digest)
        return {"line": cleaned, "witness": digest}

    def verify_chain(self) -> bool:
        """Recompute the witness chain from the ledger. True iff intact."""
        try:
            lines = self._witness_path.read_text(encoding="utf-8").strip().splitlines()
            ledger = self._ledger_path.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return False
        if not lines or lines[0] != "genesis":
            return False
        prev = "genesis"
        if len(lines) - 1 != len(ledger):
            return False
        for stored, raw in zip(lines[1:], ledger, strict=False):
            try:
                entry = json.loads(raw)
            except ValueError:
                return False
            expect = hashlib.sha256((prev + entry["line"]).encode("utf-8")).hexdigest()
            if stored != expect:
                return False
            prev = stored
        return True

    def close(self) -> Path:
        self._open = False
        return self._dir


def open_session(home: Path, session_id: Optional[str] = None) -> Session:
    """Open an SFW session under the caller's home. Opt-in, local, private."""
    sid = session_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    if any(c not in "0123456789T-_" and not c.isalnum() for c in sid):
        raise ValueError("session_id must be a simple token.")
    return Session(home, sid)


def log_line(session: Session, line: str) -> Dict[str, str]:
    """Append a line to an open session's ledger."""
    return session.log(line)


def close_session(session: Session) -> Path:
    """Close the session; returns its directory."""
    return session.close()


def read_ledger(home: Path, session_id: str) -> List[Dict[str, Any]]:
    """Owner-readable ledger — the "here is the record of how" seed."""
    path = zone_dir(home) / "sessions" / session_id / "ledger.jsonl"
    entries: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            entries.append(json.loads(raw))
    return entries
