"""Numeric identity: you own a number, and the network knows it by that.

Studied from: dead-networks-20260916/report.md [ICQ]

The studied shape: a persistent, ISP-independent numeric identity
(a UIN) riding on top of dial-up. Presence, offline message spooling,
multi-party chat, and file transfers all key off the number you own —
not the connection you're on.

LEVI-native re-expression: a tiny in-memory directory where numbers
are claimed once and never reused, presence is a per-number state
machine, messages to absent numbers wait in an honest spool, chat
rooms are just sets of numbers talking, and file transfers are
number-addressed records with size/checkpoint metadata. All local,
all in-memory; nothing here touches a network.

Honest limits: presence is cooperative (no heartbeat protocol —
numbers say what they say); the spool is bounded and in-memory;
file transfers model only the *transfer record* (who sent what to
whom, how much, resume offsets), not actual byte movement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/numeric-identity"


_PRESENCE_STATES = ("offline", "online", "away", "busy", "invisible")

#: Upper bound on undelivered messages per UIN; old ones spill first.
SPOOL_CAP = 100


class DirectoryError(Exception):
    """Raised for bad registrations, unknown numbers, or directory misuse."""


@dataclass
class Identity:
    """One claimed numeric identity."""

    uin: int
    handle: str
    presence: str = "offline"
    contacts: List[int] = field(default_factory=list)
    motto: str = ""

    def set_presence(self, state: str) -> None:
        if state not in _PRESENCE_STATES:
            raise DirectoryError(f"unknown presence state: {state!r}")
        self.presence = state

    def is_reachable(self) -> bool:
        return self.presence in ("online", "busy")


@dataclass
class SpooledMessage:
    """A message waiting for an absent number."""

    sender_uin: int
    recipient_uin: int
    body: str
    seq: int


@dataclass
class TransferRecord:
    """A file transfer tied to two numbers."""

    transfer_id: str
    sender_uin: int
    recipient_uin: int
    filename: str
    size_bytes: int
    bytes_done: int = 0
    note: str = ""

    @property
    def complete(self) -> bool:
        return self.bytes_done >= self.size_bytes

    def progress(self, n: int) -> None:
        if n < 0:
            raise DirectoryError("cannot transfer negative bytes")
        self.bytes_done = min(self.size_bytes, self.bytes_done + n)


class NumericIdentityDirectory:
    """The whole scheme: directory, spool, rooms, and transfers."""

    def __init__(self) -> None:
        self._ids: Dict[int, Identity] = {}
        self._spool: Dict[int, List[SpooledMessage]] = {}
        self._rooms: Dict[str, set] = {}
        self._transfers: Dict[str, TransferRecord] = {}
        self._next_uin = 100_000
        self._msg_seq = 0

    # -- registration -----------------------------------------------------
    def claim(self, handle: str, motto: str = "") -> Identity:
        """Hand out the next free number; numbers are never reused."""
        if not handle.strip():
            raise DirectoryError("handle may not be blank")
        uin = self._next_uin
        self._next_uin += 1
        ident = Identity(uin=uin, handle=handle.strip(), motto=motto)
        self._ids[uin] = ident
        self._spool[uin] = []
        return ident

    def lookup(self, uin: int) -> Identity:
        try:
            return self._ids[uin]
        except KeyError:
            raise DirectoryError(f"no such UIN: {uin}") from None

    def find(self, handle: str) -> Optional[Identity]:
        for ident in self._ids.values():
            if ident.handle.lower() == handle.lower():
                return ident
        return None

    # -- presence & contacts ----------------------------------------------
    def add_contact(self, owner_uin: int, contact_uin: int) -> None:
        owner = self.lookup(owner_uin)
        self.lookup(contact_uin)
        if contact_uin == owner_uin:
            raise DirectoryError("cannot add yourself as a contact")
        if contact_uin not in owner.contacts:
            owner.contacts.append(contact_uin)

    def presence_of(self, uin: int) -> str:
        return self.lookup(uin).presence

    # -- messaging ---------------------------------------------------------
    def send(
        self, sender_uin: int, recipient_uin: int, body: str
    ) -> Optional[SpooledMessage]:
        """Deliver instantly if the number is reachable; otherwise spool.

        Returns the spool record when the message had to wait, else None.
        """
        sender, recipient = self.lookup(sender_uin), self.lookup(recipient_uin)
        if not body.strip():
            raise DirectoryError("message body may not be blank")
        self._msg_seq += 1
        if recipient.is_reachable():
            return None
        record = SpooledMessage(
            sender_uin=sender.uin,
            recipient_uin=recipient.uin,
            body=body,
            seq=self._msg_seq,
        )
        box = self._spool[recipient_uin]
        box.append(record)
        del box[: max(0, len(box) - SPOOL_CAP)]  # oldest spill first
        return record

    def drain_spool(self, uin: int) -> List[SpooledMessage]:
        """Hand over everything waiting, oldest first; empties the spool."""
        self.lookup(uin)
        waiting = sorted(self._spool[uin], key=lambda m: m.seq)
        self._spool[uin] = []
        return waiting

    def spooled_count(self, uin: int) -> int:
        self.lookup(uin)
        return len(self._spool[uin])

    # -- multi-chat ----------------------------------------------------------
    def open_room(self, name: str, member_uins: List[int]) -> None:
        if not name.strip():
            raise DirectoryError("room name may not be blank")
        for u in member_uins:
            self.lookup(u)
        self._rooms[name] = set(member_uins)

    def room_members(self, name: str) -> List[int]:
        try:
            return sorted(self._rooms[name])
        except KeyError:
            raise DirectoryError(f"no such room: {name!r}") from None

    def room_say(self, room: str, sender_uin: int, body: str) -> List[int]:
        """Fan a message out to reachable members; return unreachable ones."""
        self.lookup(sender_uin)
        members = self.room_members(room)
        if sender_uin not in members:
            raise DirectoryError("sender is not in this room")
        unreachable = [u for u in members if not self.lookup(u).is_reachable()]
        for u in unreachable:
            self.send(sender_uin, u, f"[{room}] {body}")
        return unreachable

    # -- file transfers -------------------------------------------------------
    def send_file(
        self,
        sender_uin: int,
        recipient_uin: int,
        filename: str,
        size_bytes: int,
        note: str = "",
    ) -> TransferRecord:
        sender, recipient = self.lookup(sender_uin), self.lookup(recipient_uin)
        if size_bytes <= 0:
            raise DirectoryError("file size must be positive")
        tid = f"t{len(self._transfers) + 1:04d}"
        rec = TransferRecord(
            transfer_id=tid,
            sender_uin=sender.uin,
            recipient_uin=recipient.uin,
            filename=filename,
            size_bytes=size_bytes,
            note=note,
        )
        self._transfers[tid] = rec
        return rec

    def transfer(self, transfer_id: str) -> TransferRecord:
        try:
            return self._transfers[transfer_id]
        except KeyError:
            raise DirectoryError(f"no such transfer: {transfer_id!r}") from None
