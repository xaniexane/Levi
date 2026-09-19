"""Genesis license: lifetime 1-copy terms as data + license mint.

The genesis package is a lifetime single-copy buy — one-time purchase,
yours forever. These are the terms, as data, plus the mint that stamps a
license record at assembly time.

The buyer field is minted BLANK (``"buyer": "UNASSIGNED"``) and filled in
by the sale step — no fake buyers, ever.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

FORM_NAME = "genesis.license"
TERMS_VERSION = "genesis-terms-1"

TERMS: Dict[str, Any] = {
    "version": TERMS_VERSION,
    "sale": "one-time purchase — lifetime, single copy",
    "copy": "1 copy: install on machines you own or control",
    "transfer": "transferable once — the whole pack, with this license file; notify the keeper",
    "updates": "this copy is yours forever; future packs are separate buys",
    "forbidden": [
        "resell or redistribute the pack or its variants",
        "strip or alter the license record",
        "represent the variants as the full LEVI organism",
    ],
    "refund": "as-is digital good; refunds per the keeper's stated policy at sale",
}


def mint_license(pack_id: str, pack_hash: str) -> Dict[str, Any]:
    """Mint a license record for an assembled pack. Buyer left blank."""
    license_id = hashlib.sha256(
        ("%s:%s:%s" % (pack_id, pack_hash, TERMS_VERSION)).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "form": FORM_NAME,
        "license_id": "gen-lic-%s" % license_id,
        "pack_id": pack_id,
        "pack_hash": pack_hash,
        "terms_version": TERMS_VERSION,
        "terms": dict(TERMS),
        "buyer": "UNASSIGNED",  # filled by the sale step, never faked here
        "minted_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_license(record: Dict[str, Any]) -> bool:
    """Check a license record carries the required shape and terms."""
    for key in ("license_id", "pack_id", "pack_hash", "terms_version", "terms"):
        if key not in record:
            return False
    terms = record.get("terms") or {}
    return (
        terms.get("version") == TERMS_VERSION
        and terms.get("sale", "").startswith("one-time purchase")
        and terms.get("copy", "").startswith("1 copy")
    )
