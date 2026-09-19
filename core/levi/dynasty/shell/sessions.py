# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Session registry — the skeleton of session survival.

A session is a dict ``{name, created_at, last_heartbeat, status}``.
``SessionManager`` keeps sessions in memory and, when given a
``state_file``, persists them as JSON (atomic temp-file + rename).
Duplicate names raise :class:`SessionError`. Heartbeats mark a session
alive; killing marks it dead (the record is kept — a killed session is
history, not garbage).
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Union


class SessionError(ValueError):
    """A session operation was refused (duplicate, unknown, or invalid)."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SessionManager:
    """In-memory session registry with optional JSON persistence.

    Mutations are serialized per-process (thread lock) and across
    processes (exclusive flock on the state file), and every mutation
    re-reads the file first — concurrent instances sharing one home
    can no longer clobber each other's sessions last-writer-wins.
    (Purge: F-SW-3.)
    """

    def __init__(self, state_file: Optional[Union[str, Path]] = None) -> None:
        self._state_file = Path(state_file) if state_file is not None else None
        self._sessions: Dict[str, Dict[str, object]] = {}
        self._lock = threading.Lock()
        self._load()

    @contextlib.contextmanager
    def _exclusive(self) -> Iterator[None]:
        """Hold the process thread-lock and an exclusive flock while
        the caller re-reads, mutates, and saves.

        The lock lives on a SEPARATE lock file, never the data file:
        saves are atomic temp+rename, and renaming the data file would
        swap the locked inode out from under other holders. The lock
        file's identity never changes.
        """
        with self._lock:
            if self._state_file is None:
                yield
                return
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self._state_file.with_name(self._state_file.name + ".lock")
            with open(lock_path, "a+b") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _refresh(self) -> None:
        """Re-read the state file, replacing the in-memory view. Call
        inside :meth:`_exclusive` before mutating."""
        if self._state_file is None or not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # a corrupt state file never crashes the manager
        if isinstance(data, dict):
            self._sessions = {k: v for k, v in data.items() if isinstance(v, dict)}

    # -- persistence ------------------------------------------------
    def _load(self) -> None:
        if self._state_file is None or not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # a corrupt state file never crashes the manager
        if isinstance(data, dict):
            self._sessions = {k: v for k, v in data.items() if isinstance(v, dict)}

    def _save(self) -> None:
        if self._state_file is None:
            return
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._state_file.parent), prefix=".sessions-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._sessions, fh, sort_keys=True, indent=2)
                fh.write("\n")
            os.replace(tmp, self._state_file)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- API ----------------------------------------------------------
    def create(self, name: str, command: Optional[str] = None) -> Dict[str, object]:
        """Create a session. Raises :class:`SessionError` on duplicate names."""
        if not name or not name.strip():
            raise SessionError("session name must be non-empty")
        with self._exclusive():
            self._refresh()
            if name in self._sessions:
                raise SessionError(f"duplicate session: {name!r}")
            session = {
                "name": name,
                "created_at": _utc_now(),
                "last_heartbeat": _utc_now(),
                "status": "alive",
                "command": command or "",
            }
            self._sessions[name] = session
            self._save()
            return dict(session)

    def list_sessions(self) -> List[Dict[str, object]]:
        """Return copies of all session records."""
        return [dict(s) for s in self._sessions.values()]

    def get(self, name: str) -> Dict[str, object]:
        """Return a copy of the named session. Raises :class:`SessionError`
        when unknown."""
        try:
            return dict(self._sessions[name])
        except KeyError:
            raise SessionError(f"unknown session: {name!r}") from None

    def kill(self, name: str) -> Dict[str, object]:
        """Mark a session dead. The record is kept for history."""
        with self._exclusive():
            self._refresh()
            session = self._sessions.get(name)
            if session is None:
                raise SessionError(f"unknown session: {name!r}")
            session["status"] = "dead"
            session["last_heartbeat"] = _utc_now()
            self._save()
            return dict(session)

    def heartbeat(self, name: str) -> Dict[str, object]:
        """Mark a session alive and stamp its heartbeat."""
        with self._exclusive():
            self._refresh()
            session = self._sessions.get(name)
            if session is None:
                raise SessionError(f"unknown session: {name!r}")
            session["status"] = "alive"
            session["last_heartbeat"] = _utc_now()
            self._save()
            return dict(session)
