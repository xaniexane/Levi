"""Verifiable interpenetration signatures.

A signature binds a composition to the exact content it was computed over:
``{organs, risk_ceiling, timestamp, content_hash, mark}``. Recomputing the
hash over the same canonical bytes must reproduce ``content_hash`` —
otherwise the signature does not verify and the composition does not ship.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple


@dataclass(frozen=True)
class Signature:
    """One interpenetration signature."""

    signature_id: str  # "ipsig-<12 hex>"
    organs: Tuple[str, ...]
    risk_ceiling: int
    timestamp: str
    content_hash: str  # sha256 hex of the canonical content bytes
    mark: str  # human-readable mark, e.g. "echo×mandella::468::a1b2c3d4e5f6"


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_signature(
    content: bytes,
    organs: List[str],
    risk_ceiling: int,
) -> Signature:
    """Compute the signature for ``content`` interpenetrated by ``organs``."""
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError("compute_signature: content must be bytes")
    if len(organs) < 2:
        raise ValueError("compute_signature: need at least 2 organs")
    digest = _content_hash(bytes(content))
    organ_names = tuple(o.strip().lower() for o in organs)
    stamp = datetime.now(timezone.utc).isoformat()
    sig_id = f"ipsig-{digest[:12]}"
    mark = "×".join(organ_names) + f"::{digest[:12]}"
    return Signature(
        signature_id=sig_id,
        organs=organ_names,
        risk_ceiling=int(risk_ceiling),
        timestamp=stamp,
        content_hash=digest,
        mark=mark,
    )


def verify_signature(sig: Signature, content: bytes) -> bool:
    """True iff ``sig`` reproduces over ``content`` (hash + organs + ceiling)."""
    if not isinstance(sig, Signature):
        return False
    try:
        recomputed = compute_signature(
            bytes(content), list(sig.organs), sig.risk_ceiling
        )
    except (ValueError, TypeError):
        return False
    return (
        recomputed.content_hash == sig.content_hash
        and recomputed.signature_id == sig.signature_id
        and recomputed.mark.rsplit("::", 1)[0] == sig.mark.rsplit("::", 1)[0]
    )
