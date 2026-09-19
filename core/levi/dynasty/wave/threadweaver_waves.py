# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Threadweaver waves — listening sessions, wave scheduler, thread digests.

Three capabilities on the Thread+Waves beat:

* **Shared listening sessions** — a named session is a shared queue of
  media refs. Participants join/leave; ``enqueue`` adds a media ref;
  ``advance`` moves the front of the queue to ``now_playing``. An
  empty advance returns ``None``, not an error. Unknown sessions raise
  :class:`SessionError`.
* **Wave scheduler** — waves are payloads scheduled to fire at an ISO
  timestamp. :meth:`WaveScheduler.due_waves` lists what's due,
  :meth:`WaveScheduler.fire` delivers the payload exactly once (a
  second fire raises :class:`WaveError`), :meth:`WaveScheduler.cancel`
  retires a wave before it fires.
* **Thread digest** — :func:`digest` is a pure function (no I/O) that
  summarizes a list of thread steps: count, participants, first/last
  timestamps, media refs.

Persistence is file-backed JSON under
``<home>/dynasty/threadweaver/`` (``LEVI_HOME`` or ``~/.levi``),
written atomically (tmp + rename) and guarded by a per-instance lock.
No network. No playback engine — refs are indexed, not played.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import scrub_text


class SessionError(Exception):
    """A listening-session operation was refused."""


class WaveError(Exception):
    """A wave-scheduler operation was refused."""


def _home(override: Optional[os.PathLike | str] = None) -> Path:
    if override is not None:
        return Path(override).expanduser()
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_iso(value: Any, what: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise WaveError(f"{what} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise WaveError(f"{what} is not a valid ISO-8601 timestamp: {value!r}") from exc
    return parsed


def _jsonable(payload: Any, what: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise WaveError(f"{what} payload must be a dict")
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise WaveError(f"{what} payload must be JSON-serializable: {exc}") from exc
    return payload


def _clean_name(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SessionError(f"{what} must be a non-empty string")
    return scrub_text(value.strip())


class ListeningSessions:
    """Shared listening sessions — one queue of media refs per session.

    Sessions persist to ``<home>/dynasty/threadweaver/sessions.json``.
    """

    _FILE = "sessions.json"

    def __init__(self, home: Optional[os.PathLike | str] = None) -> None:
        self._home = _home(home)
        self._lock = threading.Lock()
        self._path = self._home / "dynasty" / "threadweaver" / self._FILE

    # -- persistence --------------------------------------------------
    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise SessionError("session store is corrupt: top level is not an object")
        return data

    def _save(self, data: Dict[str, Dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    def _get(self, session: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        sid = _clean_name(session, "session id")
        data = self._load()
        record = data.get(sid)
        if record is None:
            raise SessionError(f"unknown session: {sid!r}")
        return data, record

    # -- API ----------------------------------------------------------
    def create_session(self, name: Any) -> str:
        """Create a session; returns the session id."""
        clean = _clean_name(name, "session name")
        sid = uuid.uuid4().hex
        with self._lock:
            data = self._load()
            data[sid] = {
                "name": clean,
                "participants": [],
                "queue": [],
                "now_playing": None,
                "created_at": _iso_now(),
            }
            self._save(data)
        return sid

    def join(self, session: str, participant: Any) -> List[str]:
        """Add a participant (idempotent); returns the roster."""
        who = _clean_name(participant, "participant")
        with self._lock:
            data, record = self._get(session)
            if who not in record["participants"]:
                record["participants"].append(who)
            self._save(data)
            return list(record["participants"])

    def leave(self, session: str, participant: Any) -> List[str]:
        """Remove a participant; leaving as a non-member is refused."""
        who = _clean_name(participant, "participant")
        with self._lock:
            data, record = self._get(session)
            if who not in record["participants"]:
                raise SessionError(f"{who!r} is not in session {record['name']!r}")
            record["participants"].remove(who)
            self._save(data)
            return list(record["participants"])

    def enqueue(self, session: str, media_ref: Any) -> int:
        """Append a media ref to the queue; returns queue depth."""
        ref = _clean_name(media_ref, "media ref")
        with self._lock:
            data, record = self._get(session)
            record["queue"].append(ref)
            self._save(data)
            return len(record["queue"])

    def advance(self, session: str) -> Optional[str]:
        """Play the next queued ref; empty queue returns ``None``."""
        with self._lock:
            data, record = self._get(session)
            if record["queue"]:
                record["now_playing"] = record["queue"].pop(0)
            else:
                record["now_playing"] = None
            self._save(data)
            return record["now_playing"]

    def position(self, session: str) -> Dict[str, Any]:
        """Snapshot: now_playing, queue_depth, participants."""
        with self._lock:
            _, record = self._get(session)
            return {
                "now_playing": record["now_playing"],
                "queue_depth": len(record["queue"]),
                "participants": list(record["participants"]),
            }


class WaveScheduler:
    """Scheduled waves — payloads that fire once at an ISO timestamp.

    Waves persist to ``<home>/dynasty/threadweaver/waves.json``.
    """

    _FILE = "waves.json"

    def __init__(self, home: Optional[os.PathLike | str] = None) -> None:
        self._home = _home(home)
        self._lock = threading.Lock()
        self._path = self._home / "dynasty" / "threadweaver" / self._FILE

    # -- persistence --------------------------------------------------
    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise WaveError("wave store is corrupt: top level is not an object")
        return data

    def _save(self, data: Dict[str, Dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    # -- API ----------------------------------------------------------
    def schedule_wave(self, thread_id: Any, fire_at_iso: Any, payload: Any) -> str:
        """Schedule a wave; returns the wave id."""
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise WaveError("thread_id must be a non-empty string")
        _parse_iso(fire_at_iso, "fire_at")
        _jsonable(payload, "wave")
        wid = uuid.uuid4().hex
        with self._lock:
            data = self._load()
            data[wid] = {
                "thread_id": thread_id.strip(),
                "fire_at": fire_at_iso.strip(),
                "payload": payload,
                "status": "scheduled",
                "scheduled_at": _iso_now(),
            }
            self._save(data)
        return wid

    def due_waves(self, now_iso: Any) -> List[Dict[str, Any]]:
        """Waves scheduled to fire at or before ``now_iso``, oldest first."""
        now = _parse_iso(now_iso, "now")
        with self._lock:
            data = self._load()
            due = [
                {"id": wid, **wave}
                for wid, wave in data.items()
                if wave.get("status") == "scheduled"
                and _parse_iso(wave.get("fire_at"), "fire_at") <= now
            ]
        due.sort(key=lambda w: (w["fire_at"], w["id"]))
        return due

    def fire(self, wave_id: str) -> Dict[str, Any]:
        """Fire a wave — returns its payload and marks it fired.

        Firing twice, or firing a cancelled or unknown wave, raises
        :class:`WaveError`.
        """
        if not isinstance(wave_id, str) or not wave_id.strip():
            raise WaveError("wave_id must be a non-empty string")
        with self._lock:
            data = self._load()
            wave = data.get(wave_id.strip())
            if wave is None:
                raise WaveError(f"unknown wave: {wave_id!r}")
            if wave.get("status") == "fired":
                raise WaveError(f"wave {wave_id!r} already fired")
            if wave.get("status") == "cancelled":
                raise WaveError(f"wave {wave_id!r} was cancelled")
            wave["status"] = "fired"
            wave["fired_at"] = _iso_now()
            self._save(data)
            return dict(wave["payload"])

    def cancel(self, wave_id: str) -> None:
        """Retire a scheduled wave before it fires."""
        if not isinstance(wave_id, str) or not wave_id.strip():
            raise WaveError("wave_id must be a non-empty string")
        with self._lock:
            data = self._load()
            wave = data.get(wave_id.strip())
            if wave is None:
                raise WaveError(f"unknown wave: {wave_id!r}")
            if wave.get("status") == "fired":
                raise WaveError(f"wave {wave_id!r} already fired; cannot cancel")
            if wave.get("status") == "cancelled":
                raise WaveError(f"wave {wave_id!r} already cancelled")
            wave["status"] = "cancelled"
            wave["cancelled_at"] = _iso_now()
            self._save(data)


def digest(thread_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize thread steps — pure function, no I/O.

    Reads ``author``/``participant`` for participants, ``ts``/
    ``timestamp`` for the time window, and ``media_ref``/``media_refs``
    for woven media. Malformed input raises :class:`TypeError`.
    """
    if not isinstance(thread_steps, list):
        raise TypeError("thread_steps must be a list of dicts")
    for step in thread_steps:
        if not isinstance(step, dict):
            raise TypeError("thread_steps must be a list of dicts")

    participants: List[str] = []
    timestamps: List[str] = []
    media: List[str] = []
    for step in thread_steps:
        who = step.get("author", step.get("participant"))
        if isinstance(who, str) and who.strip() and who.strip() not in participants:
            participants.append(who.strip())
        ts = step.get("ts", step.get("timestamp"))
        if isinstance(ts, str) and ts.strip():
            timestamps.append(ts.strip())
        ref = step.get("media_ref")
        if isinstance(ref, str) and ref.strip() and ref.strip() not in media:
            media.append(ref.strip())
        refs = step.get("media_refs")
        if isinstance(refs, list):
            for item in refs:
                if isinstance(item, str) and item.strip() and item.strip() not in media:
                    media.append(item.strip())

    return {
        "step_count": len(thread_steps),
        "participants": sorted(participants),
        "first_ts": min(timestamps) if timestamps else None,
        "last_ts": max(timestamps) if timestamps else None,
        "media_refs": media,
    }
