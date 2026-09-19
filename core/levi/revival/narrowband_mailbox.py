"""Narrowband mailbox network: packet mail you collect from any terminal.

Studied from: dead-networks-20260916/report.md [Mobitex]

The studied shape: a packet-switched, data-only, narrowband wireless
network. Messages are stored in network mailboxes; a user logs in from
any terminal and collects what is waiting. Push email arrives as a
network primitive — the network tells you something is waiting — rather
than as an app polling for it.

LEVI-native re-expression: addresses own mailboxes; messages are
fragmented into fixed-size packets and reassembled on collection;
login drains a mailbox in priority-then-arrival order; terminals can
register for push so the network notifies them the moment mail lands
instead of them asking.

Honest limits: the radio layer is simulated (packets never actually
drop here — loss modeling is out of scope); "push" is an in-process
callback registry, not a paging signal; login is a name check, not
authentication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List


ORIGIN = "levi-revival/narrowband-mailbox"


@dataclass
class Packet:
    mailbox: str
    msg_id: str
    seq: int
    total: int
    payload: str
    priority: int = 0


@dataclass
class StoredMessage:
    msg_id: str
    sender: str
    mailbox: str
    packets: List[Packet] = field(default_factory=list)
    priority: int = 0
    read: bool = False

    def reassemble(self) -> str:
        ordered = sorted(self.packets, key=lambda p: p.seq)
        if not ordered:
            return ""
        if len(ordered) != ordered[0].total:
            raise ValueError(f"message {self.msg_id} is missing packets")
        return "".join(p.payload for p in ordered)


class MailboxNetwork:
    """The network: mailboxes, packet fragmentation, login, push."""

    def __init__(self, packet_size: int = 64) -> None:
        if packet_size <= 0:
            raise ValueError("packet_size must be positive")
        self.packet_size = packet_size
        self.mailboxes: Dict[str, List[StoredMessage]] = {}
        self._push_handlers: Dict[str, List[Callable[[StoredMessage], None]]] = {}
        self._seq = 0

    def create_mailbox(self, address: str) -> None:
        if address in self.mailboxes:
            raise ValueError(f"mailbox exists: {address!r}")
        self.mailboxes[address] = []
        self._push_handlers[address] = []

    def send(self, sender: str, recipient: str, text: str, priority: int = 0) -> str:
        if recipient not in self.mailboxes:
            raise KeyError(f"unknown mailbox: {recipient!r}")
        self._seq += 1
        msg_id = f"m{self._seq:06d}"
        chunks = [
            text[i : i + self.packet_size]
            for i in range(0, max(len(text), 1), self.packet_size)
        ]
        msg = StoredMessage(
            msg_id=msg_id, sender=sender, mailbox=recipient, priority=priority
        )
        for seq, chunk in enumerate(chunks):
            msg.packets.append(
                Packet(
                    mailbox=recipient,
                    msg_id=msg_id,
                    seq=seq,
                    total=len(chunks),
                    payload=chunk,
                    priority=priority,
                )
            )
        self.mailboxes[recipient].append(msg)
        # push primitive: the network speaks first
        for handler in self._push_handlers[recipient]:
            handler(msg)
        return msg_id

    def on_push(self, address: str, handler: Callable[[StoredMessage], None]) -> None:
        if address not in self.mailboxes:
            raise KeyError(f"unknown mailbox: {address!r}")
        self._push_handlers[address].append(handler)

    def pending(self, address: str) -> int:
        if address not in self.mailboxes:
            raise KeyError(f"unknown mailbox: {address!r}")
        return sum(1 for m in self.mailboxes[address] if not m.read)

    def login(self, address: str) -> List[StoredMessage]:
        """Log in from any terminal: collect everything waiting, newest priority first."""
        if address not in self.mailboxes:
            raise KeyError(f"unknown mailbox: {address!r}")
        waiting = [m for m in self.mailboxes[address] if not m.read]
        waiting.sort(key=lambda m: (-m.priority, m.msg_id))
        for m in waiting:
            m.read = True
        return waiting

    def purge_read(self, address: str) -> int:
        """Mailbox storage is scarce: drop messages already collected."""
        if address not in self.mailboxes:
            raise KeyError(f"unknown mailbox: {address!r}")
        before = len(self.mailboxes[address])
        self.mailboxes[address] = [m for m in self.mailboxes[address] if not m.read]
        return before - len(self.mailboxes[address])
