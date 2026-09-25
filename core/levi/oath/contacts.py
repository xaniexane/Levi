"""Contact address book for LEVI Oath.

Stored as JSON at ``<oath home>/contacts.json``::

    {
      "contacts": {
        "alice": {
          "name": "alice",
          "email": "alice@example.com",
          "fingerprints": ["AB12..."],
          "trust_floor": "TRUSTED",
          "tier_ceiling": "write",
          "grants": {"disk-usage": ["r"], "backup-now": ["w"]},
          "max_missions_per_hour": 10
        }
      }
    }

Semantics:

* ``fingerprints`` — pinned OpenPGP fingerprints.  A message is ``TRUSTED``
  only when its signature verifies *and* the signing key is pinned here.
* ``trust_floor`` — minimum trust level the contact's mail must reach
  before a mission is created.  The global hard requirement is
  ``VERIFIED``; a contact may raise their own floor to ``TRUSTED``.
  The floor can never be lowered below ``VERIFIED``.
* ``tier_ceiling`` — highest command risk tier the contact may run
  (``read`` < ``write`` < ``execute`` < ``dangerous``).
* ``grants`` — per-command letters: ``r`` read-only commands, ``w``
  state-changing commands, ``x`` pipeline-execution commands.  Deny-closed:
  anything not explicitly granted is denied.  ``dangerous`` tier commands
  additionally need the explicit letter ``d`` on that command.
* ``max_missions_per_hour`` — rate limit enforced at mission intake.

The agent itself holds zero authority here: contacts and grants are
owner-managed data, edited by the owner through the CLI, never by mail.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from levi.oath import CONTACTS_FILE
from levi.oath.keys import normalise_fingerprint
from levi.oath.trust import TRUSTED, VERIFIED

__all__ = [
    "TIERS",
    "GRANT_LETTERS",
    "Contact",
    "ContactBook",
    "load_book",
]

#: Risk tiers, lowest to highest.
TIERS = ("read", "write", "execute", "dangerous")

#: Grant letters.  ``d`` is the explicit dangerous-tier grant (never inherited).
GRANT_LETTERS = ("r", "w", "x", "d")

#: The letter each tier requires on a grant.
TIER_LETTER = {"read": "r", "write": "w", "execute": "x", "dangerous": "d"}

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")


@dataclass
class Contact:
    """One trusted correspondent."""

    name: str
    email: str = ""
    fingerprints: list[str] = field(default_factory=list)
    trust_floor: str = VERIFIED
    tier_ceiling: str = "write"
    grants: dict[str, list[str]] = field(default_factory=dict)
    max_missions_per_hour: int = 10

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise ValueError(f"invalid contact name: {self.name!r}")
        if self.trust_floor not in (VERIFIED, TRUSTED):
            raise ValueError(
                f"trust_floor must be VERIFIED or TRUSTED (hard floor is VERIFIED), "
                f"got {self.trust_floor!r}"
            )
        if self.tier_ceiling not in TIERS:
            raise ValueError(f"unknown tier ceiling: {self.tier_ceiling!r}")
        if (
            not isinstance(self.max_missions_per_hour, int)
            or self.max_missions_per_hour < 0
        ):
            raise ValueError("max_missions_per_hour must be a non-negative int")
        self.fingerprints = [normalise_fingerprint(f) for f in self.fingerprints]
        clean: dict[str, list[str]] = {}
        for cmd, letters in self.grants.items():
            bad = set(letters) - set(GRANT_LETTERS)
            if bad:
                raise ValueError(f"invalid grant letters {sorted(bad)} for {cmd!r}")
            clean[cmd] = sorted(set(letters))
        self.grants = clean

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contact":
        return cls(
            name=data["name"],
            email=data.get("email", ""),
            fingerprints=list(data.get("fingerprints", [])),
            trust_floor=data.get("trust_floor", VERIFIED),
            tier_ceiling=data.get("tier_ceiling", "write"),
            grants={k: list(v) for k, v in data.get("grants", {}).items()},
            max_missions_per_hour=int(data.get("max_missions_per_hour", 10)),
        )


class ContactBook:
    """Owner-managed address book persisted as JSON."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or CONTACTS_FILE()
        self.contacts: dict[str, Contact] = {}
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for name, raw in (data.get("contacts") or {}).items():
            try:
                self.contacts[name] = Contact.from_dict({"name": name, **raw})
            except (ValueError, KeyError, TypeError):
                continue  # skip corrupt entries rather than failing the book

    def save(self) -> None:
        """Write the book atomically with owner-only permissions."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"contacts": {n: c.to_dict() for n, c in self.contacts.items()}},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    # -- lookup ---------------------------------------------------------
    def get(self, name: str) -> Optional[Contact]:
        return self.contacts.get(name)

    def find_by_email(self, email_addr: str) -> Optional[Contact]:
        want = (email_addr or "").strip().lower()
        for contact in self.contacts.values():
            if contact.email.strip().lower() == want and want:
                return contact
        return None

    def find_by_fingerprint(self, fingerprint: str) -> Optional[Contact]:
        try:
            want = normalise_fingerprint(fingerprint)
        except ValueError:
            return None
        for contact in self.contacts.values():
            if want in contact.fingerprints:
                return contact
        return None

    # -- mutation (owner only; never callable from a mission) ------------
    def add(self, contact: Contact) -> None:
        if contact.name in self.contacts:
            raise KeyError(f"contact {contact.name!r} already exists")
        self.contacts[contact.name] = contact
        self.save()

    def remove(self, name: str) -> None:
        if name not in self.contacts:
            raise KeyError(f"no such contact: {name!r}")
        del self.contacts[name]
        self.save()

    def update(self, contact: Contact) -> None:
        if contact.name not in self.contacts:
            raise KeyError(f"no such contact: {contact.name!r}")
        self.contacts[contact.name] = contact
        self.save()

    def grant(self, name: str, command: str, letters: str) -> Contact:
        """Set the grant letters for ``command`` on ``name`` (replaces)."""
        contact = self.get(name)
        if contact is None:
            raise KeyError(f"no such contact: {name!r}")
        bad = set(letters) - set(GRANT_LETTERS)
        if bad:
            raise ValueError(f"invalid grant letters: {sorted(bad)}")
        contact.grants[command] = sorted(set(letters))
        self.save()
        return contact

    def pin(self, name: str, fingerprint: str) -> Contact:
        """Pin a fingerprint to a contact."""
        contact = self.get(name)
        if contact is None:
            raise KeyError(f"no such contact: {name!r}")
        fpr = normalise_fingerprint(fingerprint)
        if fpr not in contact.fingerprints:
            contact.fingerprints.append(fpr)
            self.save()
        return contact


def load_book(path: Optional[Path] = None) -> ContactBook:
    """Load the contact book (empty when the file does not exist yet)."""
    return ContactBook(path)
