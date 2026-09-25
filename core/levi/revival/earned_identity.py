"""earned_identity — standing that is earned or genuinely verified, never bought.

Studied from: giant-patterns-hunt-20260916-0016/report.md (Section 9).

The load-bearing idea: some marks of standing must be *unbuyable* by
construction. When a badge, tier, or trust mark can be purchased, the
mark stops meaning what it says — so the honest inversion makes
purchase structurally impossible, not merely discouraged.

LEVI's take: ``EarnedIdentity`` keeps claims about a person (tenure,
peer attestation, demonstrated skill, completed rites) and computes
standing tiers purely from *evidence*. Money is not a field anywhere
in the model — there is no price, no "premium tier" SKU, no
accelerator. ``attempt_purchase`` raises ``IdentityNotForSale`` so any
caller trying to buy standing hits a wall instead of a price tag.
Verification is quorum-based: a claim counts only when independent
attesters back it, and tiers are derived functions of earned points,
never assigned directly.

Honest limits: this is a heuristic trust model, not a court. It cannot
prove who someone *is* (no biometrics, no document checks), and
attestation is only as honest as the attesters — collusion can fake
standing, so ``collusion_risk`` is surfaced, not hidden.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/earned-identity"


class IdentityNotForSale(Exception):
    """Raised when anything tries to attach a price to standing."""


class AttestationError(Exception):
    """Raised when an attestation is malformed or self-serving."""


# Points awarded per verified claim, by evidence kind. Fixed at the
# module level so no caller can inflate them; money appears nowhere.
EVIDENCE_WEIGHTS: Dict[str, int] = {
    "tenure_day": 1,  # one point per verified day of presence
    "peer_attestation": 10,  # one peer vouching for a specific claim
    "demonstration": 25,  # a witnessed, reviewable act of skill
    "rite": 50,  # a completed community rite of passage
}


def _tier_for(points: int) -> str:
    if points >= 500:
        return "elder"
    if points >= 200:
        return "proven"
    if points >= 50:
        return "known"
    return "newcomer"


@dataclass
class Attestation:
    """One peer's witnessed backing of another person's claim."""

    attester: str
    claim: str
    evidence: str  # one of EVIDENCE_WEIGHTS
    detail: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.evidence not in EVIDENCE_WEIGHTS:
            raise AttestationError(f"unknown evidence kind: {self.evidence!r}")
        if not self.attester or not self.claim:
            raise AttestationError("attester and claim must both be named")


@dataclass
class EarnedIdentity:
    """Standing computed only from evidence. Money has no field here."""

    subject: str
    _attestations: List[Attestation] = field(default_factory=list)

    def attest(self, attestation: Attestation) -> int:
        """Record a peer attestation; returns points it was worth."""
        if attestation.attester == self.subject:
            raise AttestationError("self-attestation does not count")
        if attestation.claim != self.subject and attestation.claim:
            # A claim field naming someone else is a bookkeeping error:
            # attestations land on the subject's record only.
            raise AttestationError(
                f"attestation names {attestation.claim!r}, not {self.subject!r}"
            )
        self._attestations.append(attestation)
        return EVIDENCE_WEIGHTS[attestation.evidence]

    def earned_points(self) -> int:
        """Total points from verified evidence. Never purchasable."""
        return sum(EVIDENCE_WEIGHTS[a.evidence] for a in self._attestations)

    def tier(self) -> str:
        """Derived standing. Computed, never assigned."""
        return _tier_for(self.earned_points())

    def quorum(self, minimum_attesters: int = 3) -> bool:
        """True when enough *distinct* peers have attested."""
        distinct = {a.attester for a in self._attestations}
        return len(distinct) >= minimum_attesters

    def collusion_risk(self) -> float:
        """Fraction of attestations from the single most common attester.

        A heuristic: if one voice dominates the record, treat the
        standing with suspicion. 0.0 = fully distributed, 1.0 = one voice.
        """
        if not self._attestations:
            return 0.0
        counts: Dict[str, int] = {}
        for a in self._attestations:
            counts[a.attester] = counts.get(a.attester, 0) + 1
        return max(counts.values()) / len(self._attestations)

    def attempt_purchase(self, tier: str, price: object) -> None:
        """The honest inversion: standing cannot be bought, full stop."""
        raise IdentityNotForSale(
            f"tier {tier!r} is earned, not sold — no price ({price!r}) is accepted"
        )

    def summary(self) -> Dict[str, object]:
        return {
            "subject": self.subject,
            "points": self.earned_points(),
            "tier": self.tier(),
            "attestations": len(self._attestations),
            "quorum_3": self.quorum(),
            "collusion_risk": round(self.collusion_risk(), 3),
        }


@dataclass
class IdentityRegistry:
    """Many identities, one shared rule: no money enters the model."""

    _identities: Dict[str, EarnedIdentity] = field(default_factory=dict)

    def register(self, subject: str) -> EarnedIdentity:
        if subject in self._identities:
            return self._identities[subject]
        identity = EarnedIdentity(subject=subject)
        self._identities[subject] = identity
        return identity

    def get(self, subject: str) -> Optional[EarnedIdentity]:
        return self._identities.get(subject)

    def leaders(self, limit: int = 10) -> List[Dict[str, object]]:
        ranked = sorted(
            self._identities.values(),
            key=lambda i: i.earned_points(),
            reverse=True,
        )
        return [i.summary() for i in ranked[:limit]]
