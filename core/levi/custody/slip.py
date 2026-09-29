"""Traveling routing slips: the work item carries its own chain.

History: offices circulated documents on paper routing slips -- the US federal
Optional Form 41, "Routing and Transmittal Slip": numbered recipients with
Initials/Date blocks and action codes (Action, Approval, Circulate, Comment,
For Clearance, For Your Information, Prepare Reply, See Me, Signature...).
The slip traveled WITH the document; every handler initialed it. OF-41 prints
its own boundary: "DO NOT use as a RECORD of approvals, concurrences,
disposals, clearances, and similar actions." (arch-method-routing-slip-of41)

Clean-room recreation: a portable, hash-chained card attached to any decision
or work item. Each block is signed (initials, date, action); blocks are
append-only; the card declares what it is NOT.

Honesty: a slip is circulation infrastructure -- who saw it, when, what they
did with it. It is never the decision record itself.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SLIP_FORMAT = "levi-slip/1"

# Action codes carried over from US Optional Form 41 (the OF-41 lineage).
ACTIONS = {
    "ACTION": "Take action",
    "APPROVAL": "Approve",
    "AS_REQUESTED": "As requested",
    "CIRCULATE": "Circulate",
    "COMMENT": "Comment",
    "COORDINATION": "Coordinate",
    "FILE": "File",
    "FOR_CLEARANCE": "Clear",
    "FOR_CORRECTION": "Correct",
    "FOR_YOUR_INFORMATION": "Inform",
    "INVESTIGATE": "Investigate",
    "JUSTIFY": "Justify",
    "NOTE_AND_RETURN": "Note and return",
    "PER_CONVERSATION": "Per conversation",
    "PREPARE_REPLY": "Prepare reply",
    "SEE_ME": "See me",
    "SIGNATURE": "Sign",
}

HONESTY_FOOTER = (
    "This slip is a circulation memo -- a traveling record of who handled the "
    "item, when, and what action they took. It is NOT a record of approvals, "
    "concurrences, disposals, or clearances. (After OF-41.)"
)


class SlipError(ValueError):
    """Malformed slip input."""


def _block_hash(prev_hash: str, block: Dict[str, Any]) -> str:
    payload = prev_hash + json.dumps(block, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Slip:
    slip_id: str
    item_ref: str
    issued_by: str
    issued_at: str
    recipients: List[str]
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    closed: bool = False
    format: str = SLIP_FORMAT

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Slip":
        if data.get("format") != SLIP_FORMAT:
            raise SlipError("not a levi-slip: %r" % (data.get("format"),))
        return cls(
            slip_id=str(data["slip_id"]),
            item_ref=str(data["item_ref"]),
            issued_by=str(data["issued_by"]),
            issued_at=str(data["issued_at"]),
            recipients=list(data["recipients"]),
            blocks=list(data.get("blocks", [])),
            closed=bool(data.get("closed", False)),
        )


def issue_slip(
    item_ref: str,
    recipients: List[str],
    issued_by: str = "keeper",
    *,
    slip_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Slip:
    """Issue a traveling slip for a work item. Recipients in expected order."""
    if not item_ref or not item_ref.strip():
        raise SlipError("item_ref is required")
    if not recipients:
        raise SlipError("at least one recipient is required")
    return Slip(
        slip_id=slip_id or secrets.token_hex(8),
        item_ref=item_ref.strip(),
        issued_by=issued_by,
        issued_at=(now or datetime.now(timezone.utc)).isoformat(),
        recipients=list(recipients),
    )


def sign_slip(
    slip: Slip,
    recipient: str,
    initials: str,
    action: str,
    *,
    remark: str = "",
    now: Optional[datetime] = None,
) -> Slip:
    """Append a signed block: recipient initials + date + action code.

    Blocks are append-only; signing does not reorder or rewrite history.
    Unknown action codes are refused -- use the OF-41 lineage codes in ACTIONS.
    """
    if slip.closed:
        raise SlipError("slip %s is closed" % slip.slip_id)
    if not initials or not initials.strip():
        raise SlipError("initials are required")
    action = action.strip().upper()
    if action not in ACTIONS:
        raise SlipError(
            "unknown action %r; use one of: %s" % (action, ", ".join(sorted(ACTIONS)))
        )
    prev = slip.blocks[-1]["block_hash"] if slip.blocks else "GENESIS"
    block = {
        "seq": len(slip.blocks) + 1,
        "recipient": recipient,
        "initials": initials.strip(),
        "action": action,
        "action_text": ACTIONS[action],
        "remark": remark,
        "signed_at": (now or datetime.now(timezone.utc)).isoformat(),
        "prev_hash": prev,
    }
    block["block_hash"] = _block_hash(prev, block)
    slip.blocks.append(block)
    return slip


def close_slip(slip: Slip) -> Slip:
    """Close the slip; the item returns to the issuer with its chain intact."""
    slip.closed = True
    return slip


def verify_slip(slip: Slip) -> Dict[str, Any]:
    """Verify the hash chain and ordering. Returns a verdict dict."""
    prev = "GENESIS"
    for block in slip.blocks:
        expected = _block_hash(
            prev, {k: v for k, v in block.items() if k != "block_hash"}
        )
        if block.get("block_hash") != expected:
            return {
                "verdict": "TAMPERED",
                "at_seq": block.get("seq"),
                "note": "Block %s was altered after signing." % block.get("seq"),
            }
        prev = block["block_hash"]
    return {
        "verdict": "INTACT",
        "blocks": len(slip.blocks),
        "closed": slip.closed,
        "note": HONESTY_FOOTER,
    }


def slip_to_json(slip: Slip) -> str:
    return json.dumps(slip.to_dict(), ensure_ascii=False)


def slip_from_json(text: str) -> Slip:
    return Slip.from_dict(json.loads(text))
