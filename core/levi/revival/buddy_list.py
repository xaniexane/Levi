"""Buddy list: the first consumer social graph with live presence.

Studied from: dead-networks-20260916 / report.md [AIM] (first consumer social
graph with live presence; the Away Message as the direct ancestor of the
tweet/status update).

This is an original, from-scratch implementation for LEVI. ``BuddyList``
belongs to one owner and holds their social graph: buddies organized into
named groups, each with a live presence state, an away message with a
timestamped history (the proto-status-update), and a block list. Presence
changes are fanned out as ``PresenceEvent`` records so a UI layer could
render the classic "buddy signed on" moment.

Public surface:
- ``BuddyList``: ``add_buddy(name, group="Buddies")``, ``move_buddy``,
  ``remove_buddy``, ``block(name)``, ``unblock(name)``,
  ``set_presence(name, state)``, ``set_away_message(name, text)``,
  ``roster()`` (grouped, honoring blocks), ``status_history(name)``,
  ``events()`` (presence event feed), ``blocked()``.
- ``PresenceEvent``: frozen ``(seq, buddy, old, new)`` record.
- ``StatusUpdate``: frozen ``(seq, buddy, text)`` — one away message.
- ``BuddyError`` for violations (bad state, unknown buddy, ...).

Presence states: ``online``, ``idle``, ``away``, ``offline``.

Honest limits: presence is set explicitly by callers — there is no idle
detection, no network subscription, and no federation. Away messages are
plain text capped at 280 characters; history is in-memory only.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/buddy_list"


class BuddyError(ValueError):
    """Raised when buddy-list rules are violated."""


PRESENCE_STATES = ("online", "idle", "away", "offline")

AWAY_MESSAGE_LIMIT = 280


@dataclass(frozen=True)
class PresenceEvent:
    """One presence transition on the owner's list."""

    seq: int
    buddy: str
    old: Optional[str]
    new: str


@dataclass(frozen=True)
class StatusUpdate:
    """One away message posted by a buddy — the proto-status-update."""

    seq: int
    buddy: str
    text: str


class BuddyList:
    """One owner's social graph: grouped buddies, live presence, blocks."""

    def __init__(self, owner: str) -> None:
        if not owner or not owner.strip():
            raise BuddyError("owner name must be non-empty")
        self.owner = owner
        self._groups: Dict[str, List[str]] = {}
        self._presence: Dict[str, str] = {}
        self._away: Dict[str, str] = {}
        self._history: Dict[str, List[StatusUpdate]] = {}
        self._blocked: List[str] = []
        self._events: List[PresenceEvent] = []
        self._seq = 0

    # -- graph -------------------------------------------------------------
    def add_buddy(self, name: str, group: str = "Buddies") -> None:
        """Add a buddy to a group. Buddies start offline."""
        self._guard(name)
        if not group.strip():
            raise BuddyError("group name must be non-empty")
        if name in self._blocked:
            raise BuddyError(f"{name!r} is blocked; unblock first")
        if self._find_group(name) is not None:
            raise BuddyError(f"{name!r} is already on the list")
        self._groups.setdefault(group, []).append(name)
        self._presence[name] = "offline"

    def move_buddy(self, name: str, group: str) -> None:
        """Move a buddy to another group (created if needed)."""
        old = self._find_group(name)
        if old is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        if not group.strip():
            raise BuddyError("group name must be non-empty")
        if old != group:
            self._groups[old].remove(name)
            self._groups.setdefault(group, []).append(name)

    def remove_buddy(self, name: str) -> None:
        """Remove a buddy entirely, including presence and history."""
        group = self._find_group(name)
        if group is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        self._groups[group].remove(name)
        self._presence.pop(name, None)
        self._away.pop(name, None)
        self._history.pop(name, None)

    def groups(self) -> List[str]:
        return sorted(self._groups)

    # -- blocking ----------------------------------------------------------
    def block(self, name: str) -> None:
        """Block a name: removed from the roster and invisible everywhere."""
        self._guard(name)
        group = self._find_group(name)
        if group is not None:
            self._groups[group].remove(name)
        self._presence.pop(name, None)
        self._away.pop(name, None)
        if name not in self._blocked:
            self._blocked.append(name)

    def unblock(self, name: str) -> None:
        if name not in self._blocked:
            raise BuddyError(f"{name!r} is not blocked")
        self._blocked.remove(name)

    def blocked(self) -> List[str]:
        return list(self._blocked)

    def is_blocked(self, name: str) -> bool:
        return name in self._blocked

    # -- presence ----------------------------------------------------------
    def set_presence(self, name: str, state: str) -> PresenceEvent:
        """Set a buddy's presence; records and returns the transition event."""
        if state not in PRESENCE_STATES:
            raise BuddyError(f"bad presence state: {state!r}")
        if self._find_group(name) is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        old = self._presence.get(name)
        self._presence[name] = state
        if state != "away":
            self._away.pop(name, None)
        self._seq += 1
        event = PresenceEvent(seq=self._seq, buddy=name, old=old, new=state)
        self._events.append(event)
        return event

    def presence_of(self, name: str) -> str:
        if self._find_group(name) is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        return self._presence.get(name, "offline")

    def events(self) -> List[PresenceEvent]:
        """The presence event feed, oldest first. Returns a copy."""
        return list(self._events)

    # -- away messages (proto-status-updates) ------------------------------
    def set_away_message(self, name: str, text: str) -> StatusUpdate:
        """Post an away message for a buddy; kept in their history."""
        if self._find_group(name) is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        if len(text) > AWAY_MESSAGE_LIMIT:
            raise BuddyError(f"away message over {AWAY_MESSAGE_LIMIT} characters")
        self._away[name] = text
        if self._presence.get(name) != "away":
            self.set_presence(name, "away")
        self._seq += 1
        update = StatusUpdate(seq=self._seq, buddy=name, text=text)
        self._history.setdefault(name, []).append(update)
        return update

    def away_message(self, name: str) -> Optional[str]:
        if self._find_group(name) is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        return self._away.get(name)

    def status_history(self, name: str) -> List[StatusUpdate]:
        """Every away message a buddy ever posted, oldest first."""
        if self._find_group(name) is None:
            raise BuddyError(f"unknown buddy: {name!r}")
        return list(self._history.get(name, []))

    # -- roster ------------------------------------------------------------
    def roster(self) -> Dict[str, List[Dict[str, Optional[str]]]]:
        """Grouped roster: group -> [{name, presence, away}]. Blocked names
        never appear. Empty groups are omitted."""
        out: Dict[str, List[Dict[str, Optional[str]]]] = {}
        for group in sorted(self._groups):
            members = []
            for name in sorted(self._groups[group]):
                if name in self._blocked:
                    continue
                members.append(
                    {
                        "name": name,
                        "presence": self._presence.get(name, "offline"),
                        "away": self._away.get(name),
                    }
                )
            if members:
                out[group] = members
        return out

    # -- internals ----------------------------------------------------------
    def _find_group(self, name: str) -> Optional[str]:
        for group, members in self._groups.items():
            if name in members:
                return group
        return None

    def _guard(self, name: str) -> None:
        if not name or not name.strip():
            raise BuddyError("buddy name must be non-empty")
