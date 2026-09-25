"""Trust attested by people at reputational cost, not metrics.

Studied from: fallen-platforms-evening-20260916/report.md [3. Friendster]

The studied shape: friends write short, *named* public testimonials
on your profile. The trust signal isn't a follower count or an
engagement metric — it's a specific person putting their name on a
specific claim about you, which costs them reputation if it's false.
One testimonial per friend per profile: saying it twice adds nothing.

LEVI-native re-expression: profiles collect testimonials, each bound
to a named author; an author may attest to a profile only once
(subsequent attempts are rejected, not stacked); profile owners
approve or decline incoming testimonials before they show; and a
ledger records every attestation so the cost is visible — who vouched
for whom, and when.

Honest limits: reputation cost is *modeled* as a scarce ledger entry
(one per author-profile pair), not enforced on real people; there is
no identity verification, no fraud detection, and no weighting
beyond "named and approved". The mechanism is attestation bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/testimonials"


class TestimonialError(Exception):
    """Raised for duplicate attestations, unknown profiles, or bad text."""


@dataclass
class Testimonial:
    """One named public attestation."""

    author: str
    profile: str
    text: str
    approved: bool = False
    seq: int = 0


@dataclass
class LedgerEntry:
    """The visible cost record: who vouched for whom, when (sequence)."""

    seq: int
    author: str
    profile: str
    action: str  # "wrote" | "approved" | "declined" | "retracted"


class TestimonialBoard:
    """Profiles and the named words their friends stake on them."""

    def __init__(self) -> None:
        self._profiles: Dict[str, List[Testimonial]] = {}
        self._pending: Dict[str, List[Testimonial]] = {}
        self._ledger: List[LedgerEntry] = []
        self._seq = 0

    def _log(self, author: str, profile: str, action: str) -> None:
        self._seq += 1
        self._ledger.append(
            LedgerEntry(seq=self._seq, author=author, profile=profile, action=action)
        )

    # -- profiles ------------------------------------------------------------
    def register(self, profile: str) -> None:
        profile = profile.strip()
        if not profile:
            raise TestimonialError("profile name may not be blank")
        if profile.lower() in (p.lower() for p in self._profiles):
            raise TestimonialError(f"profile already registered: {profile!r}")
        self._profiles[profile] = []
        self._pending[profile] = []

    def _key(self, profile: str) -> str:
        for name in self._profiles:
            if name.lower() == profile.lower():
                return name
        raise TestimonialError(f"unknown profile: {profile!r}")

    # -- writing ---------------------------------------------------------------
    def write(self, author: str, profile: str, text: str) -> Testimonial:
        """Stake your name on someone. One attestation per author per profile."""
        author, text = author.strip(), text.strip()
        if not author:
            raise TestimonialError("author may not be blank")
        if not text:
            raise TestimonialError("testimonial text may not be blank")
        if len(text) > 500:
            raise TestimonialError("testimonials are short: 500 chars max")
        key = self._key(profile)
        existing = [
            t
            for t in self._profiles[key] + self._pending[key]
            if t.author.lower() == author.lower()
        ]
        if existing:
            raise TestimonialError(f"{author} already attested to {key}")
        t = Testimonial(author=author, profile=key, text=text, seq=self._seq + 1)
        self._pending[key].append(t)
        self._log(author, key, "wrote")
        return t

    # -- moderation --------------------------------------------------------------
    def approve(self, profile: str, author: str) -> Testimonial:
        key = self._key(profile)
        for t in self._pending[key]:
            if t.author.lower() == author.lower():
                self._pending[key].remove(t)
                t.approved = True
                self._profiles[key].append(t)
                self._log(author, key, "approved")
                return t
        raise TestimonialError(f"no pending testimonial from {author} on {key}")

    def decline(self, profile: str, author: str) -> None:
        key = self._key(profile)
        for t in self._pending[key]:
            if t.author.lower() == author.lower():
                self._pending[key].remove(t)
                self._log(author, key, "declined")
                return
        raise TestimonialError(f"no pending testimonial from {author} on {key}")

    def retract(self, author: str, profile: str) -> None:
        """An author may pull their own attestation back."""
        key = self._key(profile)
        for t in self._profiles[key]:
            if t.author.lower() == author.lower():
                self._profiles[key].remove(t)
                self._log(author, key, "retracted")
                return
        raise TestimonialError(f"{author} has no live testimonial on {key}")

    # -- reads ---------------------------------------------------------------------
    def shown(self, profile: str) -> List[Testimonial]:
        """Publicly visible, approved testimonials in approval order."""
        return list(self._profiles[self._key(profile)])

    def pending(self, profile: str) -> List[Testimonial]:
        return list(self._pending[self._key(profile)])

    def ledger(self, profile: Optional[str] = None) -> List[LedgerEntry]:
        """The full cost record, optionally filtered to one profile."""
        if profile is None:
            return list(self._ledger)
        key = self._key(profile)
        return [e for e in self._ledger if e.profile == key]

    def vouched_for(self, author: str) -> List[str]:
        """Every profile one author has live attestations on."""
        return [
            p
            for p, ts in self._profiles.items()
            if any(t.author.lower() == author.lower() for t in ts)
        ]
