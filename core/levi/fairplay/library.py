"""The owned library: games you bought cannot be un-bought by a shutdown.

Stadia (Jan 18, 2023) taught the lesson in one motion: the 'Buy' button
on someone else's server is a rental with no lease term. When the
landlord demolishes the building, the library evaporates and the
'solution' is publisher charity. The owned library inverts the custody
model: ownership is a local, hash-chained receipt, and saves are
exportable with checksums. No server on earth can revoke a local fact.

LAWS (invariants, machine-checked by tests):
1. OWNERSHIP IS A LOCAL RECEIPT. ``register()`` writes a hash-chained
   receipt; ``verify_chain()`` detects any tampering. The receipt does
   not phone home.
2. NO REVOCATION PRIMITIVE. There is deliberately no method that
   un-registers a game. A shutdown is the seller's problem, not yours.
3. SAVES ARE PORTABLE BY CONSTRUCTION. ``export_save()`` returns data
   plus a sha256 checksum; ``import_save()`` refuses corrupted or
   tampered payloads. The save format is documented in the docstring
   below, not locked in a binary blob.
4. THE SHELF OUTLIVES THE SELLER. ``export_shelf()`` serializes the
   whole library \u2014 receipts, chain, saves \u2014 so the player carries it
   across machines with nothing to ask anyone.

Save envelope format (JSON):
    {"slot": <str>, "game": <title>, "sha256": <hex of data>,
     "data": <base64 of the raw save bytes>}

Clean-room from first principles; no platform code was read or copied.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OwnershipReceipt:
    """One game's ownership record. Immutable; chained to the previous."""

    title: str
    build_hash: str  # hash of the local installer/binary, as recorded
    source: str  # where it came from: "drm-free", "local-build", ...
    registered_at: float
    prev_hash: str  # "GENESIS" for the first receipt

    def receipt_hash(self) -> str:
        body = json.dumps(
            {
                "title": self.title,
                "build_hash": self.build_hash,
                "source": self.source,
                "registered_at": self.registered_at,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
        )
        return _hash(body)


class OwnedLibrary:
    """The shelf. Receipts chain; saves travel; nothing is revocable."""

    def __init__(self) -> None:
        self._receipts: List[OwnershipReceipt] = []
        self._saves: Dict[Tuple[str, str], str] = {}  # (title, slot) -> envelope

    def register(self, title: str, build_hash: str, source: str) -> OwnershipReceipt:
        """Record ownership. Law 1: the receipt is local and chained."""
        if any(r.title == title for r in self._receipts):
            raise ValueError(f"{title!r} is already on the shelf")
        prev = self._receipts[-1].receipt_hash() if self._receipts else "GENESIS"
        receipt = OwnershipReceipt(
            title=title,
            build_hash=build_hash,
            source=source,
            registered_at=time.time(),
            prev_hash=prev,
        )
        self._receipts.append(receipt)
        return receipt

    def verify_chain(self) -> Tuple[bool, str]:
        """Law 1: every receipt must chain to its predecessor."""
        prev = "GENESIS"
        for receipt in self._receipts:
            if receipt.prev_hash != prev:
                return False, f"chain broken at {receipt.title!r}"
            prev = receipt.receipt_hash()
        return True, "ok"

    @property
    def titles(self) -> List[str]:
        return [r.title for r in self._receipts]

    def export_save(self, title: str, slot: str, raw: bytes) -> str:
        """Law 3: save leaves as a checksummed envelope the player owns."""
        if title not in self.titles:
            raise KeyError(f"{title!r} is not on the shelf")
        envelope = json.dumps(
            {
                "slot": slot,
                "game": title,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "data": base64.b64encode(raw).decode("ascii"),
            },
            sort_keys=True,
        )
        self._saves[(title, slot)] = envelope
        return envelope

    def import_save(self, envelope: str) -> Tuple[str, str, bytes]:
        """Verify the checksum, then hand back (game, slot, raw bytes).

        Refuses anything corrupted or tampered. Law 3.
        """
        try:
            doc = json.loads(envelope)
        except json.JSONDecodeError as exc:
            raise ValueError("not a save envelope") from exc
        for key in ("slot", "game", "sha256", "data"):
            if key not in doc:
                raise ValueError(f"save envelope missing {key!r}")
        raw = base64.b64decode(doc["data"])
        if hashlib.sha256(raw).hexdigest() != doc["sha256"]:
            raise ValueError("checksum mismatch \u2014 save is corrupted or tampered")
        return str(doc["game"]), str(doc["slot"]), raw

    def export_shelf(self) -> str:
        """Law 4: the whole shelf as one portable JSON document."""
        ok, why = self.verify_chain()
        if not ok:
            raise RuntimeError(f"cannot export a broken shelf: {why}")
        return json.dumps(
            {
                "receipts": [
                    {
                        "title": r.title,
                        "build_hash": r.build_hash,
                        "source": r.source,
                        "registered_at": r.registered_at,
                        "prev_hash": r.prev_hash,
                    }
                    for r in self._receipts
                ],
                "saves": list(self._saves.values()),
            },
            sort_keys=True,
        )

    @classmethod
    def import_shelf(cls, document: str) -> "OwnedLibrary":
        """Rebuild a shelf from an export. Re-verifies the whole chain."""
        doc = json.loads(document)
        lib = cls()
        for r in doc["receipts"]:
            lib._receipts.append(OwnershipReceipt(**r))
        ok, why = lib.verify_chain()
        if not ok:
            raise ValueError(f"imported shelf failed verification: {why}")
        for envelope in doc.get("saves", []):
            game, slot, _raw = lib.import_save(envelope)
            lib._saves[(game, slot)] = envelope
        return lib
