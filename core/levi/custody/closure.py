"""Tamper-evident closures: wax seals and letterlocking, revived.

History: for four centuries, European confidential correspondence was folded
paper sealed with wax, impressed with a personal signet -- anyone could see at
a glance whether the letter had been opened. Letterlocking (250,000 letters
studied by the MIT/KCL "Unlocking History" group) went further: the letter was
its own envelope, folded with spiral locks and slit-and-tuck mechanisms. The
security property is tamper-EVIDENCE without trust in the carrier, never
tamper-proofing: a broken seal proves compromise. An intact seal proves only
that THIS is exactly what left the sender's hands. (arch-method-wax-seal-letterlocking)

Clean-room recreation: a closure binds a SHA-256 digest of the payload bytes
to a signet id and a salt. Verification needs only the payload and the
closure -- no server, no PKI.

Honesty: verdicts are INTACT / TAMPERED / UNSIGNED. INTACT never claims
identity beyond the bound signet; a signet means something only if the
verifier already knows it, exactly like a wax impression.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

CLOSURE_FORMAT = "levi-closure/1"

INTACT = "INTACT"
TAMPERED = "TAMPERED"
UNSIGNED = "UNSIGNED"


class ClosureError(ValueError):
    """Malformed closure input."""


@dataclass(frozen=True)
class Closure:
    payload_digest: str
    signet: str
    sealed_at: str
    salt: str
    format: str = CLOSURE_FORMAT

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Closure":
        if data.get("format") != CLOSURE_FORMAT:
            raise ClosureError("not a levi-closure: %r" % (data.get("format"),))
        return cls(
            payload_digest=str(data["payload_digest"]),
            signet=str(data["signet"]),
            sealed_at=str(data["sealed_at"]),
            salt=str(data["salt"]),
        )


def seal_payload(
    payload: bytes,
    signet: str,
    *,
    salt: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Closure:
    """Seal a payload: the wax dollop. Returns the closure (travels with payload)."""
    if not payload:
        raise ClosureError("payload is required")
    if not signet or not signet.strip():
        raise ClosureError("signet is required")
    return Closure(
        payload_digest=hashlib.sha256(payload).hexdigest(),
        signet=signet.strip(),
        sealed_at=(now or datetime.now(timezone.utc)).isoformat(),
        salt=salt or secrets.token_hex(8),
    )


def inspect_closure(closure: Optional[Closure], payload: bytes) -> Dict[str, Any]:
    """Inspect: is the wax intact? Returns a verdict dict.

    - INTACT: payload bytes digest exactly the sealed digest -- this is
      precisely what left the signet's hands.
    - TAMPERED: the digest differs -- the artifact was opened or altered.
    - UNSIGNED: no closure present -- treat as read-aloud, trust nothing.
    """
    if closure is None:
        return {
            "verdict": UNSIGNED,
            "note": "No closure present. The artifact traveled open; treat it as hearsay.",
        }
    digest = hashlib.sha256(payload).hexdigest()
    if digest == closure.payload_digest:
        return {
            "verdict": INTACT,
            "signet": closure.signet,
            "sealed_at": closure.sealed_at,
            "note": (
                "The closure is intact: this is exactly what left the signet's "
                "hands. Intact proves unaltered-in-transit -- nothing about "
                "authorship beyond the bound signet."
            ),
        }
    return {
        "verdict": TAMPERED,
        "signet": closure.signet,
        "note": "The closure is broken: the payload was opened or altered in transit.",
    }


def closure_to_json(closure: Closure) -> str:
    return json.dumps(closure.to_dict(), ensure_ascii=False)


def closure_from_json(text: str) -> Closure:
    return Closure.from_dict(json.loads(text))
