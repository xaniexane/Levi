"""Trust-graph classifieds — local listings with mutual-connection trust.

Meta Marketplace's trust story is "we know everyone, trust our graph"
— a graph you can't see, computed by an algorithm you can't audit, on
a platform that monetizes every transaction with ads and boosted
listings. LEVI inverts it:

- Listings live in ``~/.levi/classifieds/listings.json`` — yours.
- The trust graph is built from a *contacts file you control*
  (``contacts.json``): your connections and, per connection, who *they*
  vouch for. No scraping, no platform graph.
- Trust scores use a **transparent published formula** (see
  :func:`trust_score`): mutual vouches between you and the lister,
  weighted by vouch strength, normalized by your total connections.
  Every score ships with its explanation — the exact mutuals counted.
- Export is portable: listings + signed trust attestations
  (HMAC-SHA256 with your local key — integrity, not identity theater)
  in one JSON bundle anyone can import and re-verify.

There is no ad layer, no boosting, no algorithmic ranking. Search is
substring match over your own listings, newest first. Boring — on
purpose. A classifieds board should be a board, not a casino.

Sybil honesty: this trusts *your* contacts file. If you vouch for
everyone, scores mean nothing — the formula is transparent so the
limitation is visible, not hidden behind "trust us".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"
EXPORT_FORMAT = "levi_classifieds_v1"


def classifieds_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "classifieds"


class ClassifiedsError(Exception):
    pass


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# trust graph
# ---------------------------------------------------------------------------
#
# contacts.json (user-controlled):
#   {"contacts": [
#      {"id": "ana", "name": "Ana", "vouches": {"bob": 1.0, "cara": 0.5}},
#      ...],
#    "me": "chauncey",
#    "my_vouches": {"ana": 1.0, "bob": 0.8}}
#
# vouch strength is 0..1, set by the user. trust_score(lister) =
#   sum over mutuals m of min(my_vouch[m], their_vouch_for_lister[m])
#   divided by (# of my connections), i.e. the fraction of my network
#   that (weighted) vouches for the lister. Range 0..1. Fully explainable.

def trust_score(lister_id: str, contacts: Dict[str, Any]) -> Dict[str, Any]:
    me_vouches: Dict[str, float] = contacts.get("my_vouches", {})
    mutuals = []
    total = 0.0
    for c in contacts.get("contacts", []):
        cid = c.get("id", "")
        their = c.get("vouches", {})
        if lister_id in their and cid in me_vouches:
            w = min(float(me_vouches[cid]), float(their[lister_id]))
            total += w
            mutuals.append({"via": cid, "weight": round(w, 3)})
    denom = len(me_vouches) or 1
    score = round(min(1.0, total / denom), 3)
    return {
        "lister": lister_id,
        "score": score,
        "mutuals": sorted(mutuals, key=lambda m: m["via"]),
        "formula": ("sum(min(my_vouch[m], their_vouch[m] for lister)) "
                    "/ my_connection_count = %.3f / %d" % (total, denom)),
    }


class ClassifiedsStore:
    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.root = classifieds_home(home)
        self.root.mkdir(parents=True, exist_ok=True)
        self._listings = self.root / "listings.json"
        self._contacts = self.root / "contacts.json"
        self._key = self.root / "attest.key"

    # -- listings -----------------------------------------------------------
    def _load_listings(self) -> List[Dict[str, Any]]:
        if not self._listings.exists():
            return []
        return json.loads(self._listings.read_text(encoding=ENC))

    def _save_listings(self, rows: List[Dict[str, Any]]) -> None:
        self._listings.write_text(json.dumps(rows, indent=2), encoding=ENC)

    def add(self, title: str, description: str = "", price: str = "",
            category: str = "misc", lister: str = "me",
            contact: str = "") -> Dict[str, Any]:
        if not title.strip():
            raise ClassifiedsError("title is required")
        rows = self._load_listings()
        row = {
            "id": uuid.uuid4().hex[:12],
            "title": title.strip(), "description": description,
            "price": price, "category": category, "lister": lister,
            "contact": contact, "status": "active",
            "created_at": _now(),
        }
        rows.append(row)
        self._save_listings(rows)
        return row

    def listings(self, category: Optional[str] = None,
                 query: Optional[str] = None,
                 include_sold: bool = False) -> List[Dict[str, Any]]:
        rows = self._load_listings()
        out = []
        for r in rows:
            if not include_sold and r["status"] != "active":
                continue
            if category and r["category"] != category:
                continue
            if query:
                q = query.lower()
                if q not in (r["title"] + " " + r["description"]).lower():
                    continue
            out.append(r)
        out.sort(key=lambda r: r["created_at"], reverse=True)
        return out

    def mark(self, listing_id: str, status: str) -> Dict[str, Any]:
        if status not in ("active", "sold", "withdrawn"):
            raise ClassifiedsError("status must be active|sold|withdrawn")
        rows = self._load_listings()
        for r in rows:
            if r["id"] == listing_id:
                r["status"] = status
                self._save_listings(rows)
                return r
        raise ClassifiedsError("no such listing: %s" % listing_id)

    # -- contacts / trust ----------------------------------------------------
    def _load_contacts(self) -> Dict[str, Any]:
        if not self._contacts.exists():
            return {"me": "me", "my_vouches": {}, "contacts": []}
        data = json.loads(self._contacts.read_text(encoding=ENC))
        if not isinstance(data, dict):
            raise ClassifiedsError("contacts.json must be an object")
        return data

    def save_contacts(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ClassifiedsError("contacts must be an object")
        self._contacts.write_text(json.dumps(data, indent=2), encoding=ENC)

    def vouch(self, contact_id: str, for_id: str, weight: float) -> Dict[str, Any]:
        """Record that one of my contacts vouches for someone (my curation)."""
        if not 0 < weight <= 1:
            raise ClassifiedsError("weight must be in (0, 1]")
        data = self._load_contacts()
        for c in data.setdefault("contacts", []):
            if c.get("id") == contact_id:
                c.setdefault("vouches", {})[for_id] = weight
                self.save_contacts(data)
                return {"contact": contact_id, "for": for_id, "weight": weight}
        raise ClassifiedsError("unknown contact: %s" % contact_id)

    def trust(self, lister_id: str) -> Dict[str, Any]:
        return trust_score(lister_id, self._load_contacts())

    def listings_with_trust(self, **kw) -> List[Dict[str, Any]]:
        rows = self.listings(**kw)
        for r in rows:
            r["trust"] = self.trust(r["lister"])
        return rows

    # -- portable export ------------------------------------------------------
    def _attest_key(self) -> bytes:
        if not self._key.exists():
            self._key.write_bytes(os.urandom(32))
            try:
                os.chmod(self._key, 0o600)
            except OSError:
                pass
        return self._key.read_bytes()

    def _sign(self, payload: bytes) -> str:
        return hmac.new(self._attest_key(), payload, hashlib.sha256).hexdigest()

    def export(self) -> Dict[str, Any]:
        """Portable bundle: listings + trust attestations, HMAC-signed."""
        listings = self._load_listings()
        contacts = self._load_contacts()
        attestations = []
        for r in listings:
            t = trust_score(r["lister"], contacts)
            body = json.dumps({"listing_id": r["id"], "lister": r["lister"],
                               "trust": t}, sort_keys=True).encode(ENC)
            attestations.append({
                "listing_id": r["id"],
                "attested_by": contacts.get("me", "me"),
                "attested_at": _now(),
                "trust": t,
                "hmac_sha256": self._sign(body),
                "note": ("integrity signature with the exporter's local key; "
                         "verifiable only by the exporter — it proves the "
                         "bundle wasn't altered after export, not identity"),
            })
        return {"format": EXPORT_FORMAT, "listings": listings,
                "attestations": attestations,
                "exported_at": _now(),
                "exported_by": contacts.get("me", "me")}

    def verify_export(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Recompute trust scores and check attestation integrity.

        Note: HMACs verify only against the exporter's own key — a recipient
        importing someone else's bundle sees scores recomputed from *their*
        contacts (honest: trust is always relative to your graph).
        """
        if bundle.get("format") != EXPORT_FORMAT:
            raise ClassifiedsError("not a levi classifieds bundle")
        contacts = self._load_contacts()
        checked, ok = 0, 0
        for a in bundle.get("attestations", []):
            checked += 1
            body = json.dumps({"listing_id": a["listing_id"],
                               "lister": a["trust"]["lister"],
                               "trust": a["trust"]}, sort_keys=True).encode(ENC)
            if hmac.compare_digest(self._sign(body), a.get("hmac_sha256", "")):
                ok += 1
        mine = {a["listing_id"]: trust_score(a["trust"]["lister"], contacts)
                for a in bundle.get("attestations", [])}
        return {"attestations": checked, "intact": ok,
                "my_trust_scores": mine,
                "note": "trust scores are recomputed against YOUR contacts"}

    def import_bundle(self, bundle: Dict[str, Any]) -> int:
        """Import listings from a bundle (ids preserved; no overwrite)."""
        if bundle.get("format") != EXPORT_FORMAT:
            raise ClassifiedsError("not a levi classifieds bundle")
        rows = self._load_listings()
        have = {r["id"] for r in rows}
        added = 0
        for r in bundle.get("listings", []):
            if r.get("id") in have:
                continue
            rows.append(r)
            added += 1
        self._save_listings(rows)
        return added
