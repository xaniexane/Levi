"""Void Box platform — classifieds: listings with validation and expiry.

FORMED: the listing data model + validation (title, description, price,
category, coarse location shape, duration), expiry (expired listings
flip to ``"expired"`` and drop out of active queries), and the RED-1
handoff dict on every listing.

NOT_WIRED (scaffolded, raises NotWiredError): payment — ``purchase()``
fails closed and names the missing enforcement wiring. Money moves
through Cybrus only; the platform holds NO money logic.

Location shape is coarse locality ONLY (city/region, <= 80 chars) —
never a street address; that is a product rule, stated here.

SI side: every public entry point calls ``require_adult()`` FIRST —
adult-only, default OFF.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — Adult gate: every public entry point calls require_adult()
  first — default OFF, minors hard-locked out; every refusal names its
  remedy. (WIRED)
- L2 — Validated listings: titles 1-80 chars; descriptions <= 2000;
  prices are integer cents >= 0 or absent; categories drawn from a
  fixed enum; location is coarse-only (<= 80 chars); duration 1-90
  days. Bad input fails closed. (WIRED)
- L3 — Expiry is real: expired listings flip to "expired" and leave
  active queries; expiry is checked on read. (WIRED)
- L4 — Payment is NOT_WIRED: purchase() raises NotWiredError naming
  the missing RED-1 enforcement wiring; nothing is charged, moved, or
  changed. (NOT_WIRED)
- L5 — Nothing thrown away: expired and withdrawn listings are marked,
  never deleted. (WIRED)

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from levi.voidbox.platform import (
    JsonStore,
    NotWiredError,
    PlatformError,
    ProfileNotFoundError,
    build_red1_details,
    expiry_after,
    is_expired,
    utcnow,
    valid_id,
    valid_price_cents,
    valid_text,
)

#: The declared laws, machine-readable.
LAWS = (
    ("L1", "Adult gate: every public entry point calls require_adult() first — default OFF, minors hard-locked out; every refusal names its remedy. (WIRED)"),
    ("L2", "Validated listings: titles 1-80; descriptions <= 2000; prices integer cents >= 0 or absent; categories from a fixed enum; coarse-only location <= 80; duration 1-90 days; bad input fails closed. (WIRED)"),
    ("L3", "Expiry is real: expired listings flip to expired and leave active queries; expiry checked on read. (WIRED)"),
    ("L4", "Payment is NOT_WIRED: purchase() raises NotWiredError naming the missing RED-1 enforcement wiring; nothing charged, moved, or changed. (NOT_WIRED)"),
    ("L5", "Nothing thrown away: expired and withdrawn listings are marked, never deleted. (WIRED)"),
)

CATEGORIES = ("services", "goods", "housing", "jobs", "community", "other")


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("listing_model", True, "post/get with validation."),
        ("expiry", True, "expired listings flip status and leave active queries."),
        ("withdraw", True, "seller-initiated early expiry marks state."),
        ("red1_details", True, "the exact RED-1 handoff dict per listing."),
        (
            "purchase",
            False,
            "payment: needs the enforcement worker's RED-1 ceremony "
            "wiring; money moves through Cybrus only.",
        ),
    ]


class ClassifiedsStore(JsonStore):
    """Classified listings. Owner-only JSON store."""

    _FILENAME = "classifieds.json"

    def __init__(self, home: Optional[Path] = None):
        super().__init__(home)

    # -- listings ------------------------------------------------------

    def post_listing(
        self,
        seller_id: str,
        title: str,
        description: str,
        price_cents: Optional[int] = None,
        category: str = "other",
        location_shape: str = "",
        duration_days: int = 30,
    ) -> dict:
        """Post a listing. ``price_cents`` may be None (no set price);
        ``location_shape`` is coarse locality only, never an address."""
        self._require_adult()
        seller_id = valid_id(seller_id, "seller_id")
        title = valid_text(title, "title", max_len=80)
        description = valid_text(
            description, "description", max_len=2000, allow_empty=True
        )
        if price_cents is not None:
            price_cents = valid_price_cents(price_cents, "price")
        if category not in CATEGORIES:
            raise PlatformError(
                "category must be one of %s, got %r." % (CATEGORIES, category)
            )
        location_shape = valid_text(
            location_shape, "location_shape", max_len=80, allow_empty=True
        )
        listing_id = "cls_" + secrets.token_hex(8)
        data = self._load()
        listings = data.setdefault("listings", {})
        listings[listing_id] = {
            "listing_id": listing_id,
            "seller_id": seller_id,
            "title": title,
            "description": description,
            "price_cents": price_cents,
            "category": category,
            "location_shape": location_shape,
            "status": "active",
            "posted_at": utcnow(),
            "expires_at": expiry_after(duration_days),
        }
        self._save(data)
        return dict(listings[listing_id])

    def get_listing(self, listing_id: str) -> dict:
        """Fetch a listing; expiry is applied on read (L3)."""
        self._require_adult()
        listing_id = valid_id(listing_id, "listing_id")
        data = self._load()
        listing = self._get(data, listing_id)
        if self._apply_expiry(data, listing):
            self._save(data)
        return dict(listing)

    def active_listings(self, category: Optional[str] = None) -> list[dict]:
        """Active (non-expired, non-withdrawn) listings, optionally by
        category. Expiry is applied on read (L3)."""
        self._require_adult()
        if category is not None and category not in CATEGORIES:
            raise PlatformError(
                "category must be one of %s, got %r." % (CATEGORIES, category)
            )
        data = self._load()
        dirty = False
        out = []
        for listing in data.get("listings", {}).values():
            dirty |= self._apply_expiry(data, listing)
            if listing["status"] != "active":
                continue
            if category is not None and listing["category"] != category:
                continue
            out.append(dict(listing))
        if dirty:
            self._save(data)
        return out

    def expire_listing(self, seller_id: str, listing_id: str) -> dict:
        """Withdraw a listing early (seller only). Marked "expired",
        never deleted (L5)."""
        self._require_adult()
        seller_id = valid_id(seller_id, "seller_id")
        listing_id = valid_id(listing_id, "listing_id")
        data = self._load()
        listing = self._get(data, listing_id)
        if listing["seller_id"] != seller_id:
            raise PlatformError(
                "only the seller (%r) may expire listing %r."
                % (listing["seller_id"], listing_id)
            )
        listing["status"] = "expired"
        listing["expired_at"] = utcnow()
        listing["withdrawn_early"] = True
        self._save(data)
        return dict(listing)

    @staticmethod
    def _get(data: dict, listing_id: str) -> dict:
        listing = data.get("listings", {}).get(listing_id)
        if listing is None:
            raise ProfileNotFoundError("no listing %r." % listing_id)
        return listing

    @staticmethod
    def _apply_expiry(data: dict, listing: dict) -> bool:
        """Flip an active listing to expired when past its expiry.
        Returns True when the store needs saving."""
        if listing["status"] == "active" and is_expired(listing):
            listing["status"] = "expired"
            listing["expired_at"] = utcnow()
            return True
        return False

    # -- payment: NOT_WIRED ----------------------------------------------

    def red1_details_for(self, buyer_id: str, listing_id: str) -> dict:
        """The exact ``details`` dict the RED-1 ceremony will consume for
        a listing purchase — the handoff contract with the sibling
        enforcement worker. The platform never acts on it."""
        self._require_adult()
        buyer_id = valid_id(buyer_id, "buyer_id")
        listing_id = valid_id(listing_id, "listing_id")
        listing = self._get(self._load(), listing_id)
        return build_red1_details(
            "listing_purchase",
            seller_id=listing["seller_id"],
            buyer_id=buyer_id,
            listing_id=listing_id,
            listing_title=listing["title"],
            amount_cents=listing["price_cents"],
        )

    def purchase(self, buyer_id: str, listing_id: str) -> dict:
        """Buy a listing — NOT_WIRED.

        Raises NotWiredError fail-closed: nothing is charged, moved, or
        changed. The pending RED-1 details dict rides on the error for
        the enforcement worker.
        """
        self._require_adult()
        details = self.red1_details_for(buyer_id, listing_id)
        raise NotWiredError(
            capability="classifieds.purchase",
            missing="the enforcement worker's RED-1 payment ceremony — "
            "money moves through Cybrus only, and the ceremony is not "
            "wired yet.",
            details=details,
        )

    def prepare_purchase_request(
        self,
        buyer_id: str,
        listing_id: str,
        platform_destination,
        seller_pay_tier: str = "free",
        seller_destination=None,
    ) -> dict:
        """Prepare the payment request for buying a listing. INERT.

        Builds the PaymentRequest (split, deep link, QR text, RED-1
        details) WITHOUT charging anything. purchase() stays NOT_WIRED.
        The seller's pay tier defaults to the provisional "free" tier;
        pass the seller's real tier/destination when known (e.g. from
        their creator profile).
        """
        self._require_adult()
        buyer_id = valid_id(buyer_id, "buyer_id")
        listing_id = valid_id(listing_id, "listing_id")
        data = self._load()
        listing = data.get("listings", {}).get(listing_id)
        if listing is None:
            raise ProfileNotFoundError("no listing %r." % listing_id)
        if listing.get("price_cents") is None:
            raise PlatformError("listing %r has no set price." % listing_id)

        from levi.voidbox.payments.requests import prepare_request

        req = prepare_request(
            kind="classified",
            total_cents=listing["price_cents"],
            tier=seller_pay_tier,
            platform_destination=platform_destination,
            creator_destination=seller_destination,
            memo="classified purchase %s listing %s" % (buyer_id, listing_id),
        )
        return {
            "request_id": req.request_id,
            "deep_link": req.deep_link,
            "qr_text": req.qr_text,
            "split": req.split.as_dict(),
            "tier_table_provisional": req.red1_details["tier_provisional"],
            "red1_details": req.red1_details,
            "status": "prepared_not_charged",
        }
