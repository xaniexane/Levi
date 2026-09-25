"""Honest receipts for the dispatch ledger (KFX2 workstream DISPATCH).

Every mutation the dispatcher twin performs is recorded as a Receipt
carried by BOTH twins (dispatcher proposes, verifier countersigns).
Receipts form a SHA-256 hash chain: each receipt embeds the hash of the
previous one, so a tampered or reordered history is detectable locally —
the "honest receipt for every dispatch" doctrine, enforced by math
rather than by a vendor's promise.

Stdlib only. No network. The chain lives in the local SQLite ledger.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_payload(
    *,
    seq: int,
    ts: str,
    twin_a: str,
    twin_b: str,
    load_id: str,
    action: str,
    from_state: str,
    to_state: str,
    details: dict,
    prev_hash: str,
) -> str:
    """Canonical string a receipt hash is computed over.

    Field order and JSON key order are fixed so the same facts always
    produce the same hash.
    """
    return "|".join(
        [
            str(seq),
            ts,
            twin_a,
            twin_b,
            load_id,
            action,
            from_state,
            to_state,
            json.dumps(details, sort_keys=True, separators=(",", ":")),
            prev_hash,
        ]
    )


def receipt_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class Receipt:
    """One countersigned dispatch event."""

    seq: int
    ts: str
    twin_a: str  # the dispatcher twin (proposer)
    twin_b: str  # the verifier twin (countersigner)
    load_id: str
    action: str
    from_state: str
    to_state: str
    details: dict = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    @classmethod
    def create(
        cls,
        *,
        seq: int,
        load_id: str,
        action: str,
        from_state: str = "",
        to_state: str = "",
        details: dict | None = None,
        prev_hash: str = GENESIS_HASH,
        twin_a: str = "dispatcher",
        twin_b: str = "verifier",
        ts: str | None = None,
    ) -> "Receipt":
        ts = ts or utcnow_iso()
        details = details or {}
        payload = canonical_payload(
            seq=seq,
            ts=ts,
            twin_a=twin_a,
            twin_b=twin_b,
            load_id=load_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            details=details,
            prev_hash=prev_hash,
        )
        return cls(
            seq=seq,
            ts=ts,
            twin_a=twin_a,
            twin_b=twin_b,
            load_id=load_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            details=details,
            prev_hash=prev_hash,
            hash=receipt_hash(payload),
        )

    def recomputed_hash(self) -> str:
        return receipt_hash(
            canonical_payload(
                seq=self.seq,
                ts=self.ts,
                twin_a=self.twin_a,
                twin_b=self.twin_b,
                load_id=self.load_id,
                action=self.action,
                from_state=self.from_state,
                to_state=self.to_state,
                details=self.details,
                prev_hash=self.prev_hash,
            )
        )

    def is_intact(self) -> bool:
        """True when the receipt's stored hash matches its content."""
        return self.hash == self.recomputed_hash()


def verify_chain(receipts: list[Receipt]) -> tuple[bool, str]:
    """Verify a receipt chain in order.

    Returns (True, "") when every receipt is intact, sequenced from 1,
    and each prev_hash links to the previous receipt's hash. Otherwise
    (False, reason) naming the first break — honest about what failed.
    """
    expected_prev = GENESIS_HASH
    for i, r in enumerate(receipts, start=1):
        if r.seq != i:
            return False, f"receipt {r.seq}: expected sequence {i}"
        if not r.is_intact():
            return False, f"receipt {r.seq}: hash mismatch (content altered)"
        if r.prev_hash != expected_prev:
            return False, f"receipt {r.seq}: chain link broken (prev_hash mismatch)"
        expected_prev = r.hash
    return True, ""
