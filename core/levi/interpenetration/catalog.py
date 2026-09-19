"""The Echo × Mandella interpenetration signature over the automation engine.

Echo expands the minion space — every minion the catalog holds is a branch Echo
could have grown. Mandella stakes each one under fog before it ships
(see :mod:`levi.interpenetration.fog`). Their interpenetration is stamped
onto every minion record as ``signature_id``; :func:`verify_signatures`
recomputes the signature over the live catalog and checks every stamp.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .composition import interpenetrate
from .signature import Signature, verify_signature

ECHO_MANDELLA_ORGANS = ("echo", "mandella")

#: Canonical row keys. ``signature_id`` is deliberately excluded: the
#: signature is computed over content, and the stamp is the signature's
#: id — including it would make verification circular.
_CANON_KEYS = [
    "id",
    "category",
    "subcategory",
    "trigger",
    "condition",
    "android_tool",
    "windows_tool",
    "mac_tool",
    "chrome_extension",
    "bridge",
    "usb_auto_launch",
    "hitl_type",
    "example_rite",
    "notes",
    "origin",
    "incomplete",
]

_RAIL_MARK = "plan>preview>permission>execute>verify>receipt"


def canonical_catalog_bytes(rows: List[Dict[str, Any]]) -> bytes:
    """Deterministic bytes for a list of minion row dicts."""
    canon = [{k: row.get(k) for k in _CANON_KEYS} for row in rows]
    payload = {"rail": _RAIL_MARK, "minions": canon}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def signature_for_rows(rows: List[Dict[str, Any]]) -> Signature:
    """The Echo × Mandella signature over raw catalog rows."""
    content = canonical_catalog_bytes(rows)
    composite = interpenetrate(
        *ECHO_MANDELLA_ORGANS,
        name="echo × mandella :: automation",
        content=content,
    )
    return composite.signature


def sign_automation_catalog() -> Signature:
    """The Echo × Mandella signature over the live catalog."""
    from levi.automation.minions import MINIONS

    return signature_for_rows([b.to_dict() for b in MINIONS])


def verify_signatures() -> Dict[str, Any]:
    """Recompute the signature and check every minion's stamp.

    Returns an honest dict: ``ok`` is True only when the recomputed
    signature matches AND every minion carries its id.
    """
    from levi.automation.minions import MINIONS

    rows = [b.to_dict() for b in MINIONS]
    sig = signature_for_rows(rows)
    mismatched = [b.id for b in MINIONS if b.signature_id != sig.signature_id]
    hash_ok = verify_signature(sig, canonical_catalog_bytes(rows))
    ok = hash_ok and not mismatched
    detail = (
        f"{len(MINIONS)} minions stamped {sig.signature_id}; "
        f"hash {'reproduces' if hash_ok else 'MISMATCH'}; "
        f"{len(mismatched)} unstamped"
    )
    return {
        "ok": ok,
        "signature_id": sig.signature_id,
        "mark": sig.mark,
        "risk_ceiling": sig.risk_ceiling,
        "organs": list(sig.organs),
        "minions_checked": len(MINIONS),
        "mismatched": mismatched,
        "hash_ok": hash_ok,
        "detail": detail,
    }
