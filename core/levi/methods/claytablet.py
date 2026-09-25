"""Mesopotamian clay-tablet accounting: the sealed record.

Origin: late 4th millennium BCE, Uruk — temple administrators ran the
world's first large-scale bureaucracy (grain, livestock, labor rations) on
a four-stage pipeline with built-in integrity: (1) tokens — 3D clay
counters for sheep, jars, labor-days; (2) bullae — tokens sealed inside a
hollow clay ball with the same marks impressed on the outside, so breaking
the seal meant the inside tokens had to match the outside marks (a
tamper-evident checksum, verified by destruction); (3) impressed tablets —
token-shapes pressed into flat tablets, moving from 3D to 2D, the
abstraction that invented numerals and then writing; (4) sealed legal
tablets whose text could be checked at a glance.

What it is in LEVI: a sealed record with a destructively verified
checksum. Seal a token set and the outside marks are struck from a hash of
the contents; ``break_seal()`` re-hashes and compares — any tamper fails
verification with a ValueError, never a silent acceptance. Only AFTER the
seal verifies can the record be impressed: abstracted from 3D tokens into
an immutable flat 2D ledger entry. Verification is the gate between the
physical record and its abstraction.

Honesty label: LOAD-BEARING — seal-then-verify-by-hash with
abstraction-only-after-verification is a concrete integrity primitive.

Deny-closed inputs: empty record ids, empty commodity names,
non-positive-integer counts, adding tokens after sealing, sealing an empty
token set, sealing twice, tampering outside the sealed-but-unverified
window, breaking an unsealed record, breaking twice, and impressing before
verification are all rejected with ValueError.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = ["SealedRecord", "LedgerEntry"]

STATE_OPEN = "open"
STATE_SEALED = "sealed"
STATE_VERIFIED = "verified"
STATE_IMPRESSED = "impressed"


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class LedgerEntry:
    """The impressed tablet: 2D abstraction of a verified token set."""

    record_id: str
    lines: tuple  # ((commodity, count), ...) sorted
    total: int


class SealedRecord:
    """Tokens -> sealed bulla -> break-and-verify -> impressed ledger."""

    def __init__(self, record_id: str) -> None:
        self._id = _clean(record_id, "record id")
        self._tokens: dict[str, int] = {}
        self._state = STATE_OPEN
        self._mark = ""

    # -- tokens ------------------------------------------------------------------
    def add_token(self, commodity: str, count: int) -> None:
        """Press a 3D clay counter into the record's token set."""
        commodity = _clean(commodity, "commodity")
        if self._state != STATE_OPEN:
            raise ValueError(
                f"cannot add tokens to {self._id!r}: record is {self._state}, not open"
            )
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f"count must be a positive integer, got {count!r}")
        self._tokens[commodity] = self._tokens.get(commodity, 0) + count

    # -- the bulla -----------------------------------------------------------------
    def seal(self) -> str:
        """Seal the tokens in the bulla; strike the checksum on the outside.

        Returns the outside mark (the hash of the contents)."""
        if self._state != STATE_OPEN:
            raise ValueError(
                f"cannot seal {self._id!r}: record is {self._state}, not open"
            )
        if not self._tokens:
            raise ValueError(f"cannot seal {self._id!r}: no tokens to seal")
        self._mark = self._checksum(self._tokens)
        self._state = STATE_SEALED
        return self._mark

    def tamper(self, commodity: str, delta: int) -> None:
        """Adversary hook for testing: alter the inside tokens without
        re-striking the outside marks. ``break_seal`` must catch this."""
        commodity = _clean(commodity, "commodity")
        if self._state != STATE_SEALED:
            raise ValueError(
                f"cannot tamper {self._id!r}: record is {self._state} — "
                "tampering is only meaningful between sealing and breaking"
            )
        if not isinstance(delta, int) or isinstance(delta, bool) or delta == 0:
            raise ValueError(f"delta must be a non-zero integer, got {delta!r}")
        self._tokens[commodity] = self._tokens.get(commodity, 0) + delta

    # -- break the seal: verified by destruction -------------------------------------
    def break_seal(self) -> dict:
        """Break the bulla. The inside tokens must match the outside marks —
        any mismatch raises, never silently passes."""
        if self._state != STATE_SEALED:
            raise ValueError(
                f"cannot break the seal on {self._id!r}: record is "
                f"{self._state}, not sealed"
            )
        if self._checksum(self._tokens) != self._mark:
            raise ValueError(
                f"seal verification FAILED for {self._id!r}: inside tokens "
                "do not match the outside marks — tampering detected"
            )
        self._state = STATE_VERIFIED
        return dict(self._tokens)

    # -- impress: 3D -> 2D ------------------------------------------------------------
    def impress(self) -> LedgerEntry:
        """Press the verified tokens into a flat 2D ledger entry. Only
        reachable after the seal has verified."""
        if self._state != STATE_VERIFIED:
            raise ValueError(
                f"cannot impress {self._id!r}: record is {self._state} — "
                "break and verify the seal first"
            )
        lines = tuple(sorted(self._tokens.items()))
        entry = LedgerEntry(
            record_id=self._id,
            lines=lines,
            total=sum(self._tokens.values()),
        )
        self._state = STATE_IMPRESSED
        return entry

    # -- internals ----------------------------------------------------------------------
    @staticmethod
    def _checksum(tokens: dict[str, int]) -> str:
        canonical = "|".join(f"{k}={v}" for k, v in sorted(tokens.items()))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
