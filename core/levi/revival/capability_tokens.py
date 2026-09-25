"""LEVI's capability-token system: membership proven by token, skill proven by work.

Studied from: lost-crafts-20260916 / report.md [Batch 1]
(The Mason's Word and Masons' Marks)

The studied mechanism separated two things that people constantly blur:

* the Word — a token proving *membership* in the guild (an anti-scab
  token: you cannot hire the gang without producing it). It says who may
  sit at the bench. It says nothing about how well you hew.
* the marks — each mason's mark struck into finished stone, and the
  on-the-spot hewing itself. That is *competence*, demonstrated, not
  declared. A mark is a provenance claim about work, not a person.

This module rebuilds that split as LEVI's own mechanism. A capability
token is a membership/role attestation: unforgeable (HMAC, stdlib),
expirable, revocable, and — crucially — it authorizes nothing by itself.
Competence is recorded separately as work-marks: signed annotations on
finished artifacts that anyone can audit later. Tokens say "I belong";
marks say "I did this, and here is the work to judge."

What this is NOT: an access-control system. Tokens here never open a
door; a separate authority (which LEVI keeps elsewhere) decides what a
membership entitles you to. Conflating the two is exactly the failure
mode this module refuses.

Anti-forgery note: this uses HMAC-SHA256 with a locally generated
secret. Verification is meaningful only against the issuing
Workmaster's own secret — same as the old guilds, where the Word only
carried weight inside the lodge that taught it.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/capability_tokens"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Base error for capability-token failures."""


class UnknownMemberError(TokenError):
    """Raised when a name is not on the Workmaster's roll."""


class ExpiredTokenError(TokenError):
    """Raised when a presented token is past its expiry."""


class RevokedTokenError(TokenError):
    """Raised when a presented token was revoked."""


class ForgedTokenError(TokenError):
    """Raised when a presented token fails HMAC verification."""


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityToken:
    """A membership token: the Word.

    Carries the member's name, the guild (scope) it belongs to, a serial,
    and an expiry. The seal is an HMAC over the rest, computed with the
    issuing Workmaster's secret. It is a *claim of belonging* — nothing
    more, nothing less.
    """

    member: str
    guild: str
    serial: int
    issued_at: int
    expires_at: int
    seal: str

    def payload(self) -> str:
        return "|".join(
            str(p)
            for p in (
                self.member,
                self.guild,
                self.serial,
                self.issued_at,
                self.expires_at,
            )
        )


@dataclass
class WorkMark:
    """A mason's mark: a competence annotation struck into finished work.

    Links an artifact to the worker, with a self-assessed grade and the
    inspector's verdict left blank until audit. The mark travels with the
    artifact, not the person — it is how the work gets judged later,
    independently of whoever struck it.
    """

    artifact: str
    worker: str
    grade: str  # worker's own claim: "rough", "true", "master"
    struck_at: int
    inspector_verdict: Optional[str] = None  # "upheld" | "downgraded" | "rejected"

    def audit(self, verdict: str) -> None:
        if verdict not in ("upheld", "downgraded", "rejected"):
            raise TokenError(f"unknown verdict: {verdict!r}")
        self.inspector_verdict = verdict


# ---------------------------------------------------------------------------
# Workmaster — issues words, keeps the roll, audits marks
# ---------------------------------------------------------------------------


class Workmaster:
    """The lodge that issues Words and keeps the roll of marks.

    One Workmaster = one guild scope. The secret never leaves the
    instance; tokens can only be verified against the master that
    sealed them — the Word carries weight only in its own lodge.
    """

    def __init__(self, guild: str, word_validity_days: float = 365.0) -> None:
        self.guild = guild
        self.word_validity_secs = word_validity_days * 86400.0
        self._secret = secrets.token_bytes(32)
        self._roll: Dict[str, List[CapabilityToken]] = {}  # member -> tokens
        self._revoked: set[int] = set()
        self._serial = 0
        self._marks: Dict[str, List[WorkMark]] = {}  # artifact -> marks

    # -- the Word --------------------------------------------------------

    def enroll(self, member: str, now: Optional[int] = None) -> CapabilityToken:
        """Enroll a member and issue their Word."""
        now = int(time.time()) if now is None else now
        self._serial += 1
        token = CapabilityToken(
            member=member,
            guild=self.guild,
            serial=self._serial,
            issued_at=now,
            expires_at=int(now + self.word_validity_secs),
            seal="",
        )
        seal = hmac.new(
            self._secret, token.payload().encode(), hashlib.sha256
        ).hexdigest()
        token = CapabilityToken(
            member=token.member,
            guild=token.guild,
            serial=token.serial,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
            seal=seal,
        )
        self._roll.setdefault(member, []).append(token)
        return token

    def verify_word(self, token: CapabilityToken, now: Optional[int] = None) -> str:
        """Verify a presented Word. Returns the member's name on success.

        Raises ExpiredTokenError / RevokedTokenError / ForgedTokenError.
        A verified Word proves membership ONLY — never competence.
        """
        now = int(time.time()) if now is None else now
        if token.guild != self.guild:
            raise ForgedTokenError("token is for another guild's lodge")
        if token.serial in self._revoked:
            raise RevokedTokenError(f"token #{token.serial} revoked")
        expected = hmac.new(
            self._secret, token.payload().encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, token.seal):
            raise ForgedTokenError("seal does not match this lodge's secret")
        if now > token.expires_at:
            raise ExpiredTokenError(f"token #{token.serial} expired")
        return token.member

    def revoke(self, member: str) -> int:
        """Revoke every live Word of a member. Returns tokens revoked."""
        revoked = 0
        for token in self._roll.get(member, []):
            if token.serial not in self._revoked:
                self._revoked.add(token.serial)
                revoked += 1
        if member not in self._roll:
            raise UnknownMemberError(member)
        return revoked

    # -- the marks -------------------------------------------------------

    def strike_mark(
        self, artifact: str, worker: str, grade: str, now: Optional[int] = None
    ) -> WorkMark:
        """Strike a work-mark into an artifact's record.

        A mark records competence-as-claimed; it becomes competence-as-known
        only when an inspector calls :meth:`WorkMark.audit`.
        """
        if grade not in ("rough", "true", "master"):
            raise TokenError(f"unknown grade: {grade!r}")
        mark = WorkMark(
            artifact=artifact,
            worker=worker,
            grade=grade,
            struck_at=int(time.time()) if now is None else now,
        )
        self._marks.setdefault(artifact, []).append(mark)
        return mark

    def marks_on(self, artifact: str) -> List[WorkMark]:
        return list(self._marks.get(artifact, []))

    def roll(self) -> List[str]:
        """Names on the roll — membership, never a ranking."""
        return sorted(self._roll)

    def competence_report(self, worker: str) -> Tuple[int, int, int]:
        """(upheld, downgraded, rejected) mark counts for a worker.

        Workers with no audited marks report (0, 0, 0): the absence of a
        record is not a record of absence. The Word gets you the bench;
        this report is the only thing that speaks of your hands.
        """
        up = down = rej = 0
        for marks in self._marks.values():
            for mark in marks:
                if mark.worker != worker or mark.inspector_verdict is None:
                    continue
                if mark.inspector_verdict == "upheld":
                    up += 1
                elif mark.inspector_verdict == "downgraded":
                    down += 1
                else:
                    rej += 1
        return (up, down, rej)
