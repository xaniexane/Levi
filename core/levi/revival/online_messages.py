"""System-wide instant messaging with presence (OLMs).

Studied from: dead-networks-20260916 / report.md [Quantum Link / Q-Link]
(system-wide instant messaging with presence on Q-Link).

This is an original, from-scratch implementation for LEVI. ``PresenceBus``
is the whole mechanism: users sign on and off, mark themselves away with an
optional note, and send instant messages to anyone on the system. Delivery
follows the historical rules:

- recipient online: the message is delivered immediately and logged;
- recipient away: delivered immediately, plus the sender sees the away note
  (the original "they're not at the keyboard" courtesy);
- recipient offline: the message waits in their inbox and is handed over on
  the next sign-on — nothing is lost just because someone was away.

Public surface:
- ``PresenceBus``: ``sign_on(user)``, ``sign_off(user)``,
  ``set_away(user, note=None)``, ``presence_of(user)``,
  ``send(sender, recipient, text)``, ``inbox(user)``, ``online_users()``,
  ``delivery_log()``.
- ``OlmMessage``: frozen record — sender, recipient, text, seq, delivered
  vs. queued.
- ``OlmError`` for violations (unknown user, empty message, self-send).

Honest limits: delivery is an in-process record — there are no sockets, no
real-time push, and no encryption. Inboxes are unbounded in memory; a
production system would cap and expire them.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/online_messages"


class OlmError(ValueError):
    """Raised when messaging rules are violated."""


@dataclass(frozen=True)
class OlmMessage:
    """One instant message, as sent."""

    seq: int
    sender: str
    recipient: str
    text: str
    delivered_now: bool


class PresenceBus:
    """Presence roster + instant message routing for one system."""

    def __init__(self) -> None:
        self._presence: Dict[str, str] = {}  # user -> "online" | "away" | "offline"
        self._away_notes: Dict[str, str] = {}
        self._inboxes: Dict[str, List[OlmMessage]] = {}
        self._log: List[OlmMessage] = []
        self._seq = 0

    # -- presence ----------------------------------------------------------
    def sign_on(self, user: str) -> List[OlmMessage]:
        """Sign a user on. Returns (and clears) any queued inbox messages."""
        self._guard_name(user)
        self._presence[user] = "online"
        self._away_notes.pop(user, None)
        return self.inbox(user)

    def sign_off(self, user: str) -> None:
        """Sign a user off; undelivered messages stay queued in the inbox."""
        self._require(user)
        self._presence[user] = "offline"
        self._away_notes.pop(user, None)

    def set_away(self, user: str, note: Optional[str] = None) -> None:
        """Mark a signed-on user away, with an optional note for senders."""
        self._require(user)
        if self._presence[user] == "offline":
            raise OlmError(f"{user!r} is offline; sign on first")
        self._presence[user] = "away"
        if note is not None:
            self._away_notes[user] = note

    def back(self, user: str) -> None:
        """Clear the away flag without signing off."""
        self._require(user)
        if self._presence[user] == "away":
            self._presence[user] = "online"
            self._away_notes.pop(user, None)

    def presence_of(self, user: str) -> str:
        """``online`` | ``away`` | ``offline``. Unknown users read as offline."""
        return self._presence.get(user, "offline")

    def away_note(self, user: str) -> Optional[str]:
        return self._away_notes.get(user)

    def online_users(self) -> List[str]:
        """Users currently online or away, sorted."""
        return sorted(u for u, p in self._presence.items() if p != "offline")

    # -- messaging ----------------------------------------------------------
    def send(self, sender: str, recipient: str, text: str) -> OlmMessage:
        """Send an instant message.

        Returns the message record. Raises if the sender is unknown/offline
        or the text is empty; delivery itself never raises — an offline
        recipient simply queues the message.
        """
        self._guard_name(sender)
        self._guard_name(recipient)
        if sender == recipient:
            raise OlmError("cannot send an OLM to yourself")
        if self._presence.get(sender, "offline") == "offline":
            raise OlmError(f"sender {sender!r} is not signed on")
        if not text.strip():
            raise OlmError("message text must be non-empty")
        self._seq += 1
        delivered = self._presence.get(recipient, "offline") != "offline"
        message = OlmMessage(
            seq=self._seq,
            sender=sender,
            recipient=recipient,
            text=text,
            delivered_now=delivered,
        )
        self._log.append(message)
        if not delivered:
            self._inboxes.setdefault(recipient, []).append(message)
        return message

    def inbox(self, user: str) -> List[OlmMessage]:
        """Drain and return queued messages for ``user`` (oldest first)."""
        self._guard_name(user)
        queued = self._inboxes.pop(user, [])
        return list(queued)

    def pending_count(self, user: str) -> int:
        return len(self._inboxes.get(user, []))

    def delivery_log(self) -> List[OlmMessage]:
        """Every message ever sent, in order. Returns a copy."""
        return list(self._log)

    # -- internals ----------------------------------------------------------
    def _guard_name(self, user: str) -> None:
        if not user or not user.strip():
            raise OlmError("user name must be non-empty")

    def _require(self, user: str) -> None:
        self._guard_name(user)
        if user not in self._presence:
            raise OlmError(f"unknown user: {user!r}")
