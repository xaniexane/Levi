"""Split-custody agreements: the Exchequer tally stick, revived.

History: from ~1100 to 1826 the English Exchequer cut hazelwood tally sticks --
notches recorded the amount, then the stick was split lengthwise through the
notches. The Exchequer kept the stock; the payer kept the foil. The halves fit
only each other, so altering either half was detectable on reunion. The obsolete
stock was burned in 1834 and the fire destroyed most of the Palace of
Westminster. (arch-method-tally-stick-exchequer)

Clean-room recreation: an agreement is two halves bound to one statement
digest. Each half carries only the digest -- a stranger holding one half
cannot read the agreement. Reunion is comparison, not testimony.

Honesty: a tally proves that two parties agreed on ONE statement at ONE time.
It proves nothing about truth, legality, or authorization. Never claim more.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

TALLY_FORMAT = "levi-tally/1"

STOCK = "stock"  # the half kept by the issuer (Exchequer's half)
FOIL = "foil"  # the half given to the counterparty (the payer's half)


class TallyError(ValueError):
    """Malformed tally input."""


def _digest(statement: str) -> str:
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


@dataclass(frozen=True)
class TallyHalf:
    """One half of a cut tally. Contains only digests -- never the statement."""

    tally_id: str
    role: str  # stock | foil
    party: str
    counterparty: str
    statement_digest: str
    cut_at: str
    nonce: str
    format: str = TALLY_FORMAT

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TallyHalf":
        if data.get("format") != TALLY_FORMAT:
            raise TallyError("not a levi-tally half: %r" % (data.get("format"),))
        return cls(
            tally_id=str(data["tally_id"]),
            role=str(data["role"]),
            party=str(data["party"]),
            counterparty=str(data["counterparty"]),
            statement_digest=str(data["statement_digest"]),
            cut_at=str(data["cut_at"]),
            nonce=str(data["nonce"]),
        )


def cut_tally(
    statement: str,
    issuer: str,
    counterparty: str,
    *,
    tally_id: Optional[str] = None,
    nonce: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[TallyHalf, TallyHalf]:
    """Cut a tally: return (stock_half, foil_half).

    The issuer keeps the stock; the counterparty holds the foil. Both halves
    bind the statement digest; neither half contains the statement itself.
    """
    if not statement or not statement.strip():
        raise TallyError("statement is required")
    if not issuer or not issuer.strip():
        raise TallyError("issuer is required")
    if not counterparty or not counterparty.strip():
        raise TallyError("counterparty is required")
    tid = tally_id or secrets.token_hex(8)
    digest = _digest(statement)
    cut_at = _now_iso(now)
    salt = nonce or secrets.token_hex(8)
    stock = TallyHalf(tid, STOCK, issuer, counterparty, digest, cut_at, salt + ":stock")
    foil = TallyHalf(tid, FOIL, counterparty, issuer, digest, cut_at, salt + ":foil")
    return stock, foil


CLOSE_MATCH = "MATCH"
CLOSE_MISMATCH = "MISMATCH"
CLOSE_WRONG_PAIR = "WRONG_PAIR"


def close_tally(half_a: TallyHalf, half_b: TallyHalf) -> Dict[str, Any]:
    """Reunite two halves. The halves FIT or they do not -- that is the whole law.

    Returns a verdict dict with ``verdict`` in {MATCH, MISMATCH, WRONG_PAIR}:
      - MATCH: same tally_id and same statement_digest -- agreement confirmed.
      - MISMATCH: same tally_id, different digests -- one half was altered.
      - WRONG_PAIR: different tally_ids -- these halves were never one stick.
    """
    if half_a.tally_id != half_b.tally_id:
        return {"verdict": CLOSE_WRONG_PAIR, "tally_id": half_a.tally_id}
    if half_a.statement_digest == half_b.statement_digest:
        return {
            "verdict": CLOSE_MATCH,
            "tally_id": half_a.tally_id,
            "statement_digest": half_a.statement_digest,
            "parties": sorted(
                {half_a.party, half_a.counterparty, half_b.party, half_b.counterparty}
            ),
            "cut_at": half_a.cut_at,
            "note": (
                "The halves agree on one statement at one time. "
                "This proves agreement, not truth."
            ),
        }
    return {
        "verdict": CLOSE_MISMATCH,
        "tally_id": half_a.tally_id,
        "note": "The halves do not fit: one of them was altered after cutting.",
    }


def halves_to_json(stock: TallyHalf, foil: TallyHalf) -> str:
    """Portable handoff format: both halves, one line each."""
    return json.dumps(stock.to_dict()) + "\n" + json.dumps(foil.to_dict())


def halves_from_json(text: str) -> Tuple[TallyHalf, TallyHalf]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) != 2:
        raise TallyError("expected exactly two tally halves, got %d" % len(lines))
    return TallyHalf.from_dict(json.loads(lines[0])), TallyHalf.from_dict(
        json.loads(lines[1])
    )
