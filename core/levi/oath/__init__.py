"""LEVI Oath — the trust-bound mission plane ("sudo for agents").

A clean-room, LEVI-native recreation of the Beadle *trust model* (see
``docs/OATH.md`` for the inspiration reference): signed instructions arrive
over email, every instruction is classified into a four-level trust ladder,
and nothing executes unless the sender is a known contact whose signature
verifies and whose explicit grants cover the requested command.  The agent
itself holds zero authority — every signing ceremony is sudo for agents.

Layout
------
``trust``      four-level message trust classification via ``gpg --verify``
``keys``       GPG wrapper (isolated GNUPGHOME, import, pinning, batch keygen)
``contacts``   address book with pinned fingerprints, trust floors, rwx grants
``commands``   signed command definitions; the loader refuses unsigned ones
``policy``     enforcement order: trust gate -> permission -> risk ceiling
``pipeline``   Unix-pipe-style mission chaining (signed cmds + AI stages)
``audit``      tamper-evident append-only audit trail with signed checkpoints
``inbox``      Maildir + IMAP intake (stdlib only), trust classification
``daemon``     working unattended daemon: poll, run missions, reply by SMTP

Home directory: ``$LEVI_OATH_HOME`` or ``~/.levi/oath``.
GPG home:      ``$LEVI_OATH_GNUPGHOME`` or ``<oath home>/gnupg``.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "oath_home",
    "gnupg_home",
    "CONTACTS_FILE",
    "COMMANDS_DIR",
    "AUDIT_FILE",
    "CHECKPOINTS_DIR",
    "USAGE_FILE",
    "OWNER_FILE",
    "MAIL_FILE",
    "MAILDIR",
]

_OATH_HOME_ENV = "LEVI_OATH_HOME"
_GNUPGHOME_ENV = "LEVI_OATH_GNUPGHOME"


def oath_home() -> Path:
    """Return the LEVI Oath home directory (``$LEVI_OATH_HOME`` or
    ``~/.levi/oath``).  Never modified by this function — callers that
    need it on disk must create it themselves (see ``init_home`` in
    :mod:`levi.oath.__main__`)."""
    raw = os.environ.get(_OATH_HOME_ENV)
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".levi" / "oath"


def gnupg_home() -> Path:
    """Return the isolated GPG home for Oath (``$LEVI_OATH_GNUPGHOME`` or
    ``<oath home>/gnupg``)."""
    raw = os.environ.get(_GNUPGHOME_ENV)
    if raw:
        return Path(raw).expanduser()
    return oath_home() / "gnupg"


def _p(name: str) -> Path:
    return oath_home() / name


# Standard on-disk locations.  Computed lazily everywhere these are used
# so tests can point $LEVI_OATH_HOME at a tmp dir; keep this module free of
# import-time filesystem side effects.
def CONTACTS_FILE() -> Path:  # noqa: N802
    return _p("contacts.json")


def COMMANDS_DIR() -> Path:  # noqa: N802
    return _p("commands")


def AUDIT_FILE() -> Path:  # noqa: N802
    return _p("audit.jsonl")


def CHECKPOINTS_DIR() -> Path:  # noqa: N802
    return _p("checkpoints")


def USAGE_FILE() -> Path:  # noqa: N802
    return _p("usage.json")


def OWNER_FILE() -> Path:  # noqa: N802
    return _p("owner.json")


def MAIL_FILE() -> Path:  # noqa: N802
    return _p("mail.json")


def MAILDIR() -> Path:  # noqa: N802
    return _p("maildir")
