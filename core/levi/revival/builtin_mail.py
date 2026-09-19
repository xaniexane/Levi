"""LEVI's built-in mail client: a local mail desk, not a wire.

Studied from: desktop-casualties-20260916 / report.md [1. Opera]
(The built-in client, later ejected into a separate download.)

The studied shape kept mail *inside* the user's own software: accounts,
folders, drafts, an outbox — a desk where mail is worked, not a portal
into someone else's cloud. This module rebuilds that shape as LEVI's
own. A local client manages accounts and folders (inbox, drafts,
outbox, sent, trash), composes and queues messages, and records sends
as local ledger events.

What this is NOT: a network client. There is no IMAP, no SMTP, no
sending over a wire here. ``send_queued()`` moves a message from the
outbox to the sent ledger of the same local store and marks it
``delivered-locally`` — an honest simulation of the handoff point,
not a claim that bytes left the machine. The point is the desk, not
the wire.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/builtin-mail"


SYSTEM_FOLDERS = ("inbox", "drafts", "outbox", "sent", "trash")


@dataclass
class MailMessage:
    """One message on the desk: headers, body, and working state.

    ``flags`` is a set like {"seen", "flagged", "answered"} — the small
    honest vocabulary a local client needs.
    """

    uid: str
    account: str
    from_addr: str
    to_addrs: List[str]
    subject: str
    body: str
    date: int
    cc: List[str] = field(default_factory=list)
    flags: set = field(default_factory=set)

    def flag(self, name: str) -> None:
        self.flags.add(name)

    def unflag(self, name: str) -> None:
        self.flags.discard(name)


@dataclass
class Account:
    """A named identity the desk can act as: address plus display name."""

    name: str
    address: str


class BuiltinMail:
    """A built-in, local-first mail client.

    One client, several accounts, each account holding the same five
    system folders plus any user folders. Messages are worked locally:
    composed into drafts, queued into the outbox, and recorded as sent.
    """

    def __init__(self) -> None:
        self.accounts: Dict[str, Account] = {}
        # account name -> folder name -> list of messages
        self._folders: Dict[str, Dict[str, List[MailMessage]]] = {}

    # -- accounts --------------------------------------------------------

    def add_account(self, name: str, address: str) -> Account:
        """Register a local identity. Raises if the name is taken."""
        if name in self.accounts:
            raise ValueError(f"account already exists: {name!r}")
        account = Account(name=name, address=address)
        self.accounts[name] = account
        self._folders[name] = {f: [] for f in SYSTEM_FOLDERS}
        return account

    def remove_account(self, name: str) -> None:
        """Drop an account and all its local folders. Irreversible."""
        if name not in self.accounts:
            raise KeyError(f"no such account: {name!r}")
        del self.accounts[name]
        del self._folders[name]

    # -- folders ----------------------------------------------------------

    def folders(self, account: str) -> List[str]:
        """Folder names for an account, system folders first."""
        return list(self._folders[account])

    def add_folder(self, account: str, folder: str) -> None:
        """Add a user folder. System folder names are reserved."""
        if folder in self._folders[account]:
            raise ValueError(f"folder already exists: {folder!r}")
        self._folders[account][folder] = []

    def list(self, account: str, folder: str) -> List[MailMessage]:
        """Messages in a folder, oldest first."""
        return list(self._folders[account][folder])

    # -- working mail -----------------------------------------------------

    def compose(
        self,
        account: str,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        now: Optional[int] = None,
    ) -> MailMessage:
        """Draft a message. Lands in the drafts folder, unsent."""
        acct = self.accounts[account]  # KeyError if unknown — good
        msg = MailMessage(
            uid=uuid.uuid4().hex,
            account=account,
            from_addr=acct.address,
            to_addrs=list(to),
            subject=subject,
            body=body,
            date=int(time.time()) if now is None else now,
            cc=list(cc or []),
        )
        self._folders[account]["drafts"].append(msg)
        return msg

    def receive(self, account: str, msg: MailMessage) -> MailMessage:
        """File an incoming message into the inbox.

        Local intake only — a stand-in for whatever transport the user
        wires up elsewhere. Returns the filed message with ``seen``
        unset.
        """
        if account not in self.accounts:
            raise KeyError(f"no such account: {account!r}")
        self._folders[account]["inbox"].append(msg)
        return msg

    def queue_send(self, account: str, uid: str) -> MailMessage:
        """Move a draft (or anything) to the outbox for sending."""
        msg = self._take(account, uid)
        self._folders[account]["outbox"].append(msg)
        return msg

    def send_queued(self, account: str) -> List[MailMessage]:
        """Record the outbox as sent.

        Each message is flagged ``delivered-locally`` and moved to the
        sent folder. This is the handoff point: no network is involved,
        and the flag says so honestly.
        """
        outbox = self._folders[account]["outbox"]
        sent = self._folders[account]["sent"]
        moved = []
        for msg in outbox:
            msg.flag("delivered-locally")
            sent.append(msg)
            moved.append(msg)
        outbox.clear()
        return moved

    def move(self, account: str, uid: str, folder: str) -> MailMessage:
        """Move a message between folders of one account."""
        msg = self._take(account, uid)
        self._folders[account][folder].append(msg)
        return msg

    def delete(self, account: str, uid: str) -> MailMessage:
        """Send a message to the trash."""
        return self.move(account, uid, "trash")

    def expunge(self, account: str, folder: str) -> int:
        """Permanently drop every message in a folder. Returns the count."""
        msgs = self._folders[account][folder]
        count = len(msgs)
        msgs.clear()
        return count

    def find(self, account: str, uid: str) -> Optional[MailMessage]:
        """Locate a message by uid across all folders of an account."""
        for msgs in self._folders[account].values():
            for msg in msgs:
                if msg.uid == uid:
                    return msg
        return None

    # -- internals --------------------------------------------------------

    def _take(self, account: str, uid: str) -> MailMessage:
        for msgs in self._folders[account].values():
            for i, msg in enumerate(msgs):
                if msg.uid == uid:
                    return msgs.pop(i)
        raise KeyError(f"no message {uid!r} in account {account!r}")
