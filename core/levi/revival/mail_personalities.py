"""Multiple identities per account, no switching ceremony.

Studied from: desktop-casualties-20260916/report.md [3. Eudora]

The studied shape: one mail account can wear several *personalities*
— different display names, signatures, reply styles — and choosing
who you are this message is a lightweight inline decision, not a
ceremony of logging out and back in. The honesty is in the headers:
every message still records which personality sent it, so there's no
impersonation-by-accident.

LEVI-native re-expression: an account owns a list of personalities
(each with a display name, return name, signature block, and optional
stationery note); composing a message picks one inline with the
compose call; sent mail is recorded with the personality used so
receipts and threads stay attributable. Local only, no mail server.

Honest limits: this is composition-and-attribution bookkeeping, not
a mail transport — nothing leaves the machine, nothing is encrypted,
and spam rules still see one underlying account address.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/mail-personalities"


class PersonalityError(Exception):
    """Raised for bad personalities, unknown accounts, or compose misuse."""


@dataclass
class Personality:
    """One of the faces an account may wear."""

    name: str  # label shown in the picker, e.g. "Work"
    display_name: str  # what recipients see, e.g. "Dana (Acme Support)"
    return_name: str = ""  # Reply-To style override; "" = display_name
    signature: str = ""
    stationery: str = ""  # free-text tone/format note, e.g. "formal letterhead"

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.display_name = self.display_name.strip()
        if not self.name:
            raise PersonalityError("personality name may not be blank")
        if not self.display_name:
            raise PersonalityError("display name may not be blank")
        if not self.return_name.strip():
            self.return_name = self.display_name


@dataclass
class Message:
    """A composed message, permanently stamped with its personality."""

    msg_id: str
    from_personality: str
    display_from: str
    to: str
    subject: str
    body: str
    signature_used: str
    stationery: str


@dataclass
class MailAccount:
    """One underlying address wearing one or more personalities."""

    address: str
    personalities: List[Personality] = field(default_factory=list)
    default_personality: Optional[str] = None

    def add_personality(self, p: Personality) -> None:
        if any(
            existing.name.lower() == p.name.lower() for existing in self.personalities
        ):
            raise PersonalityError(f"duplicate personality: {p.name!r}")
        self.personalities.append(p)
        if self.default_personality is None:
            self.default_personality = p.name

    def get(self, name: str) -> Personality:
        for p in self.personalities:
            if p.name.lower() == name.lower():
                return p
        raise PersonalityError(f"no such personality: {name!r}")

    def remove_personality(self, name: str) -> None:
        if len(self.personalities) <= 1:
            raise PersonalityError("an account must keep at least one personality")
        target = self.get(name)
        self.personalities.remove(target)
        if (
            self.default_personality
            and self.default_personality.lower() == name.lower()
        ):
            self.default_personality = self.personalities[0].name


class PersonalityPost:
    """Compose and file messages under any of your personalities."""

    def __init__(self) -> None:
        self._accounts: Dict[str, MailAccount] = {}
        self._sent: List[Message] = []
        self._seq = 0

    def add_account(self, address: str) -> MailAccount:
        address = address.strip().lower()
        if "@" not in address:
            raise PersonalityError(f"not a mail address: {address!r}")
        if address in self._accounts:
            raise PersonalityError(f"account already registered: {address!r}")
        acct = MailAccount(address=address)
        self._accounts[address] = acct
        return acct

    def compose(
        self,
        account: str,
        personality: Optional[str],
        to: str,
        subject: str,
        body: str,
        sign: bool = True,
    ) -> Message:
        """Pick who you are *for this message* and send it.

        No logout, no account ceremony — just a personality name.
        """
        acct = self._accounts.get(account.strip().lower())
        if acct is None:
            raise PersonalityError(f"unknown account: {account!r}")
        pname = personality or acct.default_personality
        if pname is None:
            raise PersonalityError("no personalities defined and none given")
        p = acct.get(pname)
        if not to.strip():
            raise PersonalityError("recipient may not be blank")
        self._seq += 1
        msg = Message(
            msg_id=f"m{self._seq:05d}",
            from_personality=p.name,
            display_from=p.display_name,
            to=to.strip(),
            subject=subject,
            body=body,
            signature_used=p.signature if sign else "",
            stationery=p.stationery,
        )
        self._sent.append(msg)
        return msg

    def sent_by(self, personality: str) -> List[Message]:
        """All messages attributable to one personality, across accounts."""
        return [
            m for m in self._sent if m.from_personality.lower() == personality.lower()
        ]

    def thread_for(self, subject: str) -> List[Message]:
        """Messages sharing an exact subject line, in send order."""
        return [m for m in self._sent if m.subject == subject]
