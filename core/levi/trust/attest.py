"""The attestation ledger: badges earned by proof, never by payment.

X's paid blue check and Meta Verified taught the same lesson: once a badge
can be bought, it stops being proof and becomes rent. The ledger answers
with structure — an attestation is only valid when it binds three things:

- ``claim``  — who or what is being vouched for ("entity:local-shop-12")
- ``proof``  — the EVIDENCE, named and checkable ("community-vouch:3-of-5",
  "document:state-id-shown", "history:2-years-of-deliveries")
- ``issuer`` — who checked the evidence ("levi-local", "keeper", a named peer)

Proof kinds that are just payment — "payment:card-ending-4242",
"subscription:meta-verified" — are refused by ``issue()`` outright. A
receipt is not proof; it is a toll receipt, and the ledger says so.

Every attestation gets a hash-chained receipt: each receipt commits to the
previous receipt's hash. Carry the ledger anywhere; ``verify_chain()``
detects any tampering. Revocation is a ledger entry, never a quiet delete.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Proof kinds that are payment in costume. Matching is case-insensitive and
# substring-based: "subscription-meta-verified-monthly" is still payment.
PAYMENT_PROOF_MARKERS = (
    "payment",
    "subscription",
    "billing",
    "invoice",
    "receipt",
    "stripe",
    "paypal",
    "premium-purchase",
    "boost",
)


def _looks_like_payment(proof: str) -> bool:
    low = proof.lower()
    return any(marker in low for marker in PAYMENT_PROOF_MARKERS)


@dataclass(frozen=True)
class Attestation:
    """One earned badge. ``proof`` is the evidence, never a payment."""

    id: str
    claim: str
    proof: str
    issuer: str
    issued_at: float
    prev_hash: str  # hash of the previous receipt ("GENESIS" for the first)
    revoked_at: Optional[float] = None

    def receipt(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "claim": self.claim,
            "proof": self.proof,
            "issuer": self.issuer,
            "issued_at": self.issued_at,
            "prev_hash": self.prev_hash,
            "revoked_at": self.revoked_at,
        }


def _receipt_hash(receipt: Dict[str, object], prev_hash: str) -> str:
    """The chain link: content hash commits to content + previous link."""
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + "|" + canonical).encode("utf-8")).hexdigest()


class AttestationLedger:
    """A portable, tamper-evident book of earned badges.

    LAW 1: ``issue()`` refuses payment-as-proof. No exceptions, no flag to
    disable it — the refusal is the feature.
    """

    def __init__(self) -> None:
        self._badges: Dict[str, Attestation] = {}
        self._hashes: Dict[str, str] = {}  # badge id -> receipt hash
        self._order: List[str] = []  # issuance order (chain order)

    # -- issue -----------------------------------------------------------

    def issue(self, claim: str, proof: str, issuer: str) -> Attestation:
        """Earn a badge. Raises ValueError if proof is payment in costume."""
        if not claim.strip():
            raise ValueError("attestation needs a claim")
        if not proof.strip():
            raise ValueError("attestation needs named proof, not an empty string")
        if not issuer.strip():
            raise ValueError("attestation needs a named issuer")
        if _looks_like_payment(proof):
            raise ValueError(
                "refused: %r is payment, not proof. "
                "A toll receipt cannot vouch for identity." % proof
            )
        badge_id = "badge-%04d" % (len(self._order) + 1)
        prev_hash = self._hashes[self._order[-1]] if self._order else "GENESIS"
        badge = Attestation(
            id=badge_id,
            claim=claim.strip(),
            proof=proof.strip(),
            issuer=issuer.strip(),
            issued_at=time.time(),
            prev_hash=prev_hash,
        )
        self._badges[badge_id] = badge
        self._hashes[badge_id] = _receipt_hash(badge.receipt(), prev_hash)
        self._order.append(badge_id)
        return badge

    # -- revoke ----------------------------------------------------------

    def revoke(self, badge_id: str, reason: str = "") -> Attestation:
        """Revoke publicly: the badge stays in the ledger, marked revoked."""
        badge = self._badges.get(badge_id)
        if badge is None:
            raise KeyError("no such badge: %r" % badge_id)
        if badge.revoked_at is not None:
            return badge
        revoked = Attestation(
            id=badge.id,
            claim=badge.claim,
            proof=badge.proof,
            issuer=badge.issuer,
            issued_at=badge.issued_at,
            prev_hash=badge.prev_hash,
            revoked_at=time.time(),
        )
        self._badges[badge_id] = revoked
        self._hashes[badge_id] = _receipt_hash(revoked.receipt(), badge.prev_hash)
        return revoked

    # -- verify ----------------------------------------------------------

    def verify(self, badge_id: str) -> Tuple[bool, str]:
        """LAW 2/4: valid only if present, unrevoked, chain-intact."""
        badge = self._badges.get(badge_id)
        if badge is None:
            return False, "unknown badge"
        if badge.revoked_at is not None:
            return False, "revoked"
        ok, detail = self.verify_chain()
        if not ok:
            return False, "chain broken: " + detail
        return True, "earned badge: %s proved by %s (issuer %s)" % (
            badge.claim,
            badge.proof,
            badge.issuer,
        )

    def verify_chain(self) -> Tuple[bool, str]:
        """LAW 3: every stored receipt must still match its chain link."""
        expected_prev = "GENESIS"
        for badge_id in self._order:
            badge = self._badges[badge_id]
            if badge.prev_hash != expected_prev:
                return False, "prev_hash mismatch at %s" % badge_id
            if self._hashes.get(badge_id) != _receipt_hash(
                badge.receipt(), badge.prev_hash
            ):
                return False, "receipt tampered at %s" % badge_id
            expected_prev = self._hashes[badge_id]
        return True, "chain intact: %d receipts" % len(self._order)

    # -- audit -----------------------------------------------------------

    def audit(self) -> Dict[str, object]:
        """Hunt for badges that smell like bought trust. Honest ledgers
        report zero; the audit exists so a future import can be checked."""
        suspicious = [
            badge_id
            for badge_id, badge in self._badges.items()
            if _looks_like_payment(badge.proof)
        ]
        chain_ok, chain_detail = self.verify_chain()
        return {
            "badges": len(self._badges),
            "revoked": sum(
                1 for b in self._badges.values() if b.revoked_at is not None
            ),
            "payment_as_proof": suspicious,
            "chain_ok": chain_ok,
            "chain_detail": chain_detail,
            "verdict": "honest"
            if (not suspicious and chain_ok)
            else "compromised",
        }

    # -- portable export -------------------------------------------------

    def export_bundle(self) -> Dict[str, object]:
        """The badge you can prove anywhere: receipts + chain, as JSON."""
        return {
            "format": "levi-attestation-bundle/1",
            "receipts": [self._badges[i].receipt() for i in self._order],
            "hashes": [self._hashes[i] for i in self._order],
        }

    @classmethod
    def import_bundle(cls, bundle: Dict[str, object]) -> "AttestationLedger":
        """Rebuild a ledger from an exported bundle; the chain is rechecked."""
        if bundle.get("format") != "levi-attestation-bundle/1":
            raise ValueError("not an attestation bundle")
        ledger = cls()
        receipts = bundle.get("receipts", [])
        hashes = bundle.get("hashes", [])
        if len(receipts) != len(hashes):
            raise ValueError("bundle receipts/hashes length mismatch")
        for receipt, stored_hash in zip(receipts, hashes):
            badge = Attestation(
                id=str(receipt["id"]),
                claim=str(receipt["claim"]),
                proof=str(receipt["proof"]),
                issuer=str(receipt["issuer"]),
                issued_at=float(receipt["issued_at"]),
                prev_hash=str(receipt["prev_hash"]),
                revoked_at=(
                    float(receipt["revoked_at"])
                    if receipt.get("revoked_at") is not None
                    else None
                ),
            )
            ledger._badges[badge.id] = badge
            ledger._hashes[badge.id] = str(stored_hash)
            ledger._order.append(badge.id)
        ok, detail = ledger.verify_chain()
        if not ok:
            raise ValueError("imported bundle failed chain check: " + detail)
        return ledger

    # -- listing ----------------------------------------------------------

    def list_claims(self) -> List[Attestation]:
        return [self._badges[i] for i in self._order]
