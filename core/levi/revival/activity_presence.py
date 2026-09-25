"""Activity-enriched presence: who is here, and what they are doing.

Studied from: dead-networks-20260916 / report.md [MSN Messenger] (presence
enriched with activity metadata — 'what I'm listening to'; custom emoticons,
nudges, winks).

This is an original, from-scratch implementation for LEVI. Three mechanisms,
each independent:

- ``RichPresence`` — a presence record is a state *plus* an activity tuple
  (kind, title, detail), e.g. ``("music", "Kind of Blue", "Miles Davis")``.
  The "what I'm listening to" shape, generalized to any activity.
- ``EmoticonPack`` — a user-defined shortcut table mapping text shortcuts
  like ``:)`` to glyphs. ``render`` substitutes shortcuts while honoring
  backslash escapes, so ``\\:)`` stays literal.
- ``Nudge`` via ``AttentionBus`` — a "get their attention" ping with a
  per-pair cooldown (default 30 seconds, injectable clock for tests) so
  nudges stay meaningful instead of becoming spam.

Public surface:
- ``RichPresence``: ``set_state(state)``, ``set_activity(kind, title,
  detail="")``, ``clear_activity()``, ``snapshot()``.
- ``EmoticonPack``: ``add(shortcut, glyph)``, ``remove(shortcut)``,
  ``render(text)``, ``shortcuts()``.
- ``AttentionBus``: ``nudge(sender, recipient)`` -> bool (False on
  cooldown), ``nudges_received(user)``, ``reset_cooldown(sender,
  recipient)``.
- ``PresenceError`` for violations.

Honest limits: activity metadata is caller-supplied text — there is no media
player integration and no verification that anyone is actually listening to
anything. Nudges are in-process records, not screen-shaking UI. Emoticon
glyphs are text, not images.

stdlib-only. No network.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


ORIGIN = "levi-revival/activity_presence"


class PresenceError(ValueError):
    """Raised when activity-presence rules are violated."""


PRESENCE_STATES = ("online", "busy", "away", "offline", "idle")

#: Seconds between nudges from the same sender to the same recipient.
NUDGE_COOLDOWN = 30.0


@dataclass(frozen=True)
class Activity:
    """One activity tuple: what kind, what title, optional detail."""

    kind: str
    title: str
    detail: str = ""


class RichPresence:
    """Presence as state + activity metadata, per user."""

    def __init__(self, user: str) -> None:
        if not user or not user.strip():
            raise PresenceError("user name must be non-empty")
        self.user = user
        self._state = "offline"
        self._activity: Optional[Activity] = None

    def set_state(self, state: str) -> None:
        if state not in PRESENCE_STATES:
            raise PresenceError(f"bad presence state: {state!r}")
        self._state = state

    def state(self) -> str:
        return self._state

    def set_activity(self, kind: str, title: str, detail: str = "") -> None:
        """Publish what the user is doing, e.g. kind="music"."""
        if not kind.strip() or not title.strip():
            raise PresenceError("activity kind and title must be non-empty")
        self._activity = Activity(kind=kind, title=title, detail=detail)

    def clear_activity(self) -> None:
        self._activity = None

    def activity(self) -> Optional[Activity]:
        return self._activity

    def snapshot(self) -> Dict[str, Optional[str]]:
        """Flat, UI-ready view of this user's presence."""
        snap: Dict[str, Optional[str]] = {"user": self.user, "state": self._state}
        if self._activity is not None:
            snap["activity_kind"] = self._activity.kind
            snap["activity_title"] = self._activity.title
            snap["activity_detail"] = self._activity.detail or None
        else:
            snap["activity_kind"] = None
            snap["activity_title"] = None
            snap["activity_detail"] = None
        return snap


class EmoticonPack:
    """User-defined text-shortcut -> glyph table with escape support."""

    def __init__(self) -> None:
        self._table: Dict[str, str] = {}

    def add(self, shortcut: str, glyph: str) -> None:
        """Map ``shortcut`` (e.g. ``":)"``) to ``glyph`` (e.g. ``"🙂"``)."""
        if not shortcut:
            raise PresenceError("shortcut must be non-empty")
        if not glyph:
            raise PresenceError("glyph must be non-empty")
        if "\\" in shortcut:
            raise PresenceError("shortcut may not contain a backslash")
        self._table[shortcut] = glyph

    def remove(self, shortcut: str) -> None:
        if shortcut not in self._table:
            raise PresenceError(f"unknown shortcut: {shortcut!r}")
        del self._table[shortcut]

    def shortcuts(self) -> List[str]:
        return sorted(self._table)

    def render(self, text: str) -> str:
        """Substitute shortcuts in ``text``.

        A backslash escapes the next character, so ``\\:)`` renders as the
        literal ``:)`` and ``\\\\`` renders as ``\\``. Longest shortcuts win
        at each position.
        """
        if not self._table:
            return text.replace("\\\\", "\\")
        ordered = sorted(self._table, key=len, reverse=True)
        out: List[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            for shortcut in ordered:
                if text.startswith(shortcut, i):
                    out.append(self._table[shortcut])
                    i += len(shortcut)
                    break
            else:
                out.append(ch)
                i += 1
        return "".join(out)


class AttentionBus:
    """Nudges: attention pings with a per-pair cooldown.

    ``clock`` is an injectable seconds-since-epoch callable (defaults to
    ``time.monotonic``) so cooldown behavior is testable without sleeping.
    """

    def __init__(self, clock: Optional[Callable[[], float]] = None) -> None:
        self._clock = clock or time.monotonic
        self._last: Dict[Tuple[str, str], float] = {}
        self._received: Dict[str, int] = {}

    def nudge(self, sender: str, recipient: str) -> bool:
        """Ping ``recipient`` for attention.

        Returns True and records the nudge, or False if the pair is still
        inside the cooldown window (the nudge is dropped, not queued).
        """
        if not sender.strip() or not recipient.strip():
            raise PresenceError("sender and recipient must be non-empty")
        if sender == recipient:
            raise PresenceError("cannot nudge yourself")
        now = self._clock()
        last = self._last.get((sender, recipient))
        if last is not None and now - last < NUDGE_COOLDOWN:
            return False
        self._last[(sender, recipient)] = now
        self._received[recipient] = self._received.get(recipient, 0) + 1
        return True

    def nudges_received(self, user: str) -> int:
        return self._received.get(user, 0)

    def reset_cooldown(self, sender: str, recipient: str) -> None:
        """Clear the cooldown for a pair (moderation/testing escape hatch)."""
        self._last.pop((sender, recipient), None)
