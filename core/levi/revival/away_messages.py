"""Away messages: ambient, voluntary presence without reply-obligation.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #3] (away messages: ambient, voluntary presence broadcasting mood
without reply-obligation).

This is an original, from-scratch implementation for LEVI. A ``Board`` holds
one current ``AwayMessage`` per person. Setting a message is voluntary and
ambient: it says "here is my weather" without asking anything of the reader.
The mechanism carries the no-reply-obligation as a *declared property* of
every message (``expects_reply=False`` by default, and readers see the
declaration), rather than a social norm the software nags about.

Messages can expire (``expires_at``); expired messages drop off the board
automatically on read, so stale presence never lingers. A bounded history
per person lets the board show "recent weather" without turning presence
into a timeline.

Honest limits:
- The no-reply-obligation is declared, not enforced — no software can stop
  another human from replying. What the module guarantees is that no reply
  is ever *requested or tracked*: there is no read-receipt, no "seen"
  indicator, no nudge timer.
- Expiry is evaluated lazily on read (no background process), so an expiry
  passes only when someone looks at the board.
- Moods are free text, not a fixed taxonomy — the module does not infer or
  classify feelings.

Public surface:
- ``AwayMessage``, ``Board``: ``set``, ``clear``, ``current``,
  ``visible_board``, ``history``, ``purge_expired``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

ORIGIN = "levi-revival/away-messages"

_HISTORY_LIMIT = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AwayMessage:
    """One person's ambient presence broadcast."""

    person: str
    mood: str
    detail: str = ""
    # The core of the mechanism: presence never asks for a reply.
    expects_reply: bool = False
    set_at: str = field(default_factory=lambda: _now().isoformat())
    expires_at: Optional[str] = None

    def expired(self, at: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        return (at or _now()) >= datetime.fromisoformat(self.expires_at)

    def time_left(self, at: Optional[datetime] = None) -> Optional[timedelta]:
        if not self.expires_at:
            return None
        return datetime.fromisoformat(self.expires_at) - (at or _now())


class BoardError(ValueError):
    """Raised when an away message cannot be recorded."""


class Board:
    """One current message per person; expired messages fall off on read."""

    def __init__(self) -> None:
        self._current: Dict[str, AwayMessage] = {}
        self._history: Dict[str, List[AwayMessage]] = {}

    # -- writing presence ---------------------------------------------------

    def set(
        self,
        person: str,
        mood: str,
        detail: str = "",
        ttl: Optional[timedelta] = None,
        expects_reply: bool = False,
    ) -> AwayMessage:
        person = person.strip()
        mood = mood.strip()
        if not person:
            raise BoardError("a message needs a person")
        if not mood:
            raise BoardError("a message needs a mood")
        if ttl is not None and ttl.total_seconds() <= 0:
            raise BoardError("ttl must be positive")
        message = AwayMessage(
            person=person,
            mood=mood,
            detail=detail.strip(),
            expects_reply=expects_reply,
            expires_at=((_now() + ttl).isoformat() if ttl is not None else None),
        )
        self._current[person] = message
        self._history.setdefault(person, []).append(message)
        self._history[person] = self._history[person][-_HISTORY_LIMIT:]
        return message

    def clear(self, person: str) -> bool:
        """Voluntarily withdraw presence. Returns True if one was live."""
        return self._current.pop(person.strip(), None) is not None

    # -- reading presence ----------------------------------------------------

    def purge_expired(self, at: Optional[datetime] = None) -> int:
        """Drop expired messages. Returns how many fell off."""
        moment = at or _now()
        expired = [p for p, m in self._current.items() if m.expired(moment)]
        for person in expired:
            del self._current[person]
        return len(expired)

    def current(
        self, person: str, at: Optional[datetime] = None
    ) -> Optional[AwayMessage]:
        message = self._current.get(person.strip())
        if message is not None and message.expired(at or _now()):
            del self._current[person.strip()]
            return None
        return message

    def visible_board(self, at: Optional[datetime] = None) -> List[AwayMessage]:
        """Everyone's current, unexpired presence. Oldest-set first."""
        self.purge_expired(at)
        return sorted(self._current.values(), key=lambda m: m.set_at)

    def history(self, person: str) -> List[AwayMessage]:
        """Recent weather for one person. Never a reply ledger."""
        return list(self._history.get(person.strip(), []))

    def people(self) -> List[str]:
        return sorted(self._current)

    def __len__(self) -> int:
        self.purge_expired()
        return len(self._current)
