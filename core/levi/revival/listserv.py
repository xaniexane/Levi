"""LISTSERV-style mailing-list manager: the list is driven by emailed commands.

Studied from: dead-networks-20260916/report.md (BITNET + LISTSERV + BITNET Relay)

The mechanism: an automated list manager that answers command messages
instead of a human operator. Commands: SUBSCRIBE / UNSUBSCRIBE (SIGNOFF),
REVIEW (member list), HELP, plus owner commands ADD / DELETE / SET
MODERATED. Distribution sends to every member; a moderated list holds
messages in a queue for owner approval instead. All traffic lands in an
archive keyed by sequence number.

Honest limits: there is no email transport — ``receive`` takes the
command body text directly and returns the reply text, modeling the
protocol faithfully without sending anything. Addresses are opaque
strings; no validation beyond non-empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/listserv"

HELP_TEXT = (
    "SUBSCRIBE <list> [name]  - join the list\n"
    "UNSUBSCRIBE <list>        - leave the list (SIGNOFF works too)\n"
    "REVIEW <list>              - list members\n"
    "HELP                       - this message\n"
    "Owner: ADD <list> <addr>, DELETE <list> <addr>, "
    "SET <list> MODERATED|OPEN"
)


@dataclass
class ArchivedMessage:
    seq: int
    sender: str
    subject: str
    body: str
    held: bool = False


class MailingList:
    """A single automated mailing list."""

    def __init__(self, name: str, owner: str) -> None:
        if not name or not name.strip():
            raise ValueError("list name must be non-empty")
        if not owner or not owner.strip():
            raise ValueError("owner must be non-empty")
        self.name = name.upper()
        self.owner = owner
        self.moderated = False
        self.members: List[str] = []
        self.archive: List[ArchivedMessage] = []
        self.pending: List[ArchivedMessage] = []
        self._seq = 0

    # ------------------------------------------------------------------
    # Membership (direct API)
    # ------------------------------------------------------------------
    def subscribe(self, address: str) -> bool:
        address = self._addr(address)
        if address in self.members:
            return False
        self.members.append(address)
        return True

    def unsubscribe(self, address: str) -> bool:
        address = self._addr(address)
        if address not in self.members:
            return False
        self.members.remove(address)
        return True

    # ------------------------------------------------------------------
    # Distribution
    # ------------------------------------------------------------------
    def distribute(self, sender: str, subject: str, body: str) -> ArchivedMessage:
        self._seq += 1
        msg = ArchivedMessage(
            seq=self._seq,
            sender=sender,
            subject=subject,
            body=body,
            held=self.moderated,
        )
        if self.moderated:
            self.pending.append(msg)
        else:
            self.archive.append(msg)
        return msg

    def approve(self, seq: int) -> ArchivedMessage:
        """Owner approves a held message; it joins the archive."""
        for i, msg in enumerate(self.pending):
            if msg.seq == seq:
                msg.held = False
                self.archive.append(msg)
                del self.pending[i]
                return msg
        raise KeyError(f"no pending message with seq {seq}")

    def reject(self, seq: int) -> None:
        for i, msg in enumerate(self.pending):
            if msg.seq == seq:
                del self.pending[i]
                return
        raise KeyError(f"no pending message with seq {seq}")

    # ------------------------------------------------------------------
    # The command interface: receive a command email, get a reply
    # ------------------------------------------------------------------
    def receive(self, sender: str, command_text: str) -> str:
        """Parse one emailed command and return the manager's reply."""
        parts = command_text.strip().split()
        if not parts:
            return "Empty command. Send HELP for the command list."
        cmd = parts[0].upper()
        args = parts[1:]

        if cmd == "HELP":
            return HELP_TEXT
        if cmd == "SUBSCRIBE" and args:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            joined = self.subscribe(sender)
            return (
                f"{sender} subscribed to {self.name}."
                if joined
                else f"{sender} is already on {self.name}."
            )
        if cmd in ("UNSUBSCRIBE", "SIGNOFF") and args:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            left = self.unsubscribe(sender)
            return (
                f"{sender} removed from {self.name}."
                if left
                else f"{sender} was not on {self.name}."
            )
        if cmd == "REVIEW" and args:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            lines = [f"Members of {self.name} ({len(self.members)}):"]
            lines.extend(f"  {m}" for m in self.members)
            return "\n".join(lines)
        if cmd == "ADD" and len(args) >= 2 and sender == self.owner:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            self.subscribe(args[1])
            return f"{args[1]} added to {self.name}."
        if cmd == "DELETE" and len(args) >= 2 and sender == self.owner:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            self.unsubscribe(args[1])
            return f"{args[1]} removed from {self.name}."
        if cmd == "SET" and len(args) >= 2 and sender == self.owner:
            if args[0].upper() != self.name:
                return f"Unknown list {args[0]!r}."
            mode = args[1].upper()
            if mode not in ("MODERATED", "OPEN"):
                return "Mode must be MODERATED or OPEN."
            self.moderated = mode == "MODERATED"
            return f"{self.name} is now {mode}."
        return f"Unknown command {cmd!r}. Send HELP for the command list."

    @staticmethod
    def _addr(address: str) -> str:
        if not address or not address.strip():
            raise ValueError("address must be non-empty")
        return address.strip()


@dataclass
class ListServer:
    """Hosts many automated lists under one manager."""

    lists: Dict[str, MailingList] = field(default_factory=dict)

    def create(self, name: str, owner: str) -> MailingList:
        key = name.upper()
        if key in self.lists:
            raise ValueError(f"list {key!r} already exists")
        ml = MailingList(name=key, owner=owner)
        self.lists[key] = ml
        return ml

    def get(self, name: str) -> Optional[MailingList]:
        return self.lists.get(name.upper())
