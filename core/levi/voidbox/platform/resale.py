"""Void Box platform — resale: product listings with price/location.

FORMED: the resale listing data model + validation (product, price,
quantity, unit, coarse location shape, duration), expiry, and the
RED-1 handoff dict on every listing.

NOT_WIRED (scaffolded, raises NotWiredError): checkout — ``checkout()``
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
- L2 — Validated listings: products 1-80 chars; prices are positive
  integer cents; quantities are positive integers; units drawn from a
  fixed enum; location is coarse-only (<= 80 chars); duration 1-90
  days. Bad input fails closed. (WIRED)
- L3 — Expiry is real: expired listings flip to "expired" and leave
  active queries; expiry is checked on read. (WIRED)
- L4 — Checkout is NOT_WIRED: checkout() raises NotWiredError naming
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
    ("L2", "Validated listings: products 1-80; prices positive integer cents; quantities positive integers; units from a fixed enum; coarse-only location <= 80; duration 1-90 days; bad input fails closed. (WIRED)"),
    ("L3", "Expiry is real: expired listings flip to expired and leave active queries; expiry checked on read. (WIRED)"),
    ("L4", "Checkout is NOT_WIRED: checkout() raises NotWiredError naming the missing RED-1 enforcement wiring; nothing charged, moved, or changed. (NOT_WIRED)"),
    ("L5", "Nothing thrown away: expired and withdrawn listings are marked, never deleted. (WIRED)"),
)

UNITS = ("each", "gram", "ounce", "pack", "bottle", "unit", "other")


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("listing_model", True, "post/get with product/price/location validation."),
        ("expiry", True, "expired listings flip status and leave active queries."),
        ("withdraw", True, "vendor-initiated early expiry marks state."),
        ("red1_details", True, "the exact RED-1 handoff dict per listing."),
        (
            "checkout",
            False,
            "payment: needs the enforcement worker's RED-1 ceremony "
            "wiring; money moves through Cybrus only.",
        ),
    ]


class ResaleStore(JsonStore):
    """Resale listings. Owner-only JSON store."""

    _FILENAME = "resale.json"

    def __init__(self, home: Optional[Path] = None):
        super().__init__(home)

    # -- listings ------------------------------------------------------

    def post_listing(
        self,
        vendor_id: str,
        product: str,
        description: str,
        price_cents: int,
        quantity: int,
        unit: str = "each",
        location_shape: str = "",
        duration_days: int = 30,
    ) -> dict:
        """Post a resale listing. ``location_shape`` is coarse locality
        only, never an address."""
        self._require_adult()
        vendor_id = valid_id(vendor_id, "vendor_id")
        product = valid_text(product, "product", max_len=80)
        description = valid_text(
            description, "description", max_len=2000, allow_empty=True
        )
        price_cents = valid_price_cents(price_cents, "price")
        if price_cents <= 0:
            raise PlatformError(
                "resale price must be positive, got %d cents." % price_cents
            )
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise PlatformError(
                "quantity must be a positive integer, got %r." % (quantity,)
            )
        if unit not in UNITS:
            raise PlatformError(
                "unit must be one of %s, got %r." % (UNITS, unit)
            )
        location_shape = valid_text(
            location_shape, "location_shape", max_len=80, allow_empty=True
        )
        listing_id = "rsl_" + secrets.token_hex(8)
        data = self._load()
        listings = data.setdefault("listings", {})
        listings[listing_id] = {
            "listing_id": listing_id,
            "vendor_id": vendor_id,
            "product": product,
            "description": description,
            "price_cents": price_cents,
            "quantity": quantity,
            "unit": unit,
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

    def active_listings(self, vendor_id: Optional[str] = None) -> list[dict]:
        """Active listings, optionally filtered by vendor. Expiry is
        applied on read (L3)."""
        self._require_adult()
        if vendor_id is not None:
            vendor_id = valid_id(vendor_id, "vendor_id")
        data = self._load()
        dirty = False
        out = []
        for listing in data.get("listings", {}).values():
            dirty |= self._apply_expiry(data, listing)
            if listing["status"] != "active":
                continue
            if vendor_id is not None and listing["vendor_id"] != vendor_id:
                continue
            out.append(dict(listing))
        if dirty:
            self._save(data)
        return out

    def expire_listing(self, vendor_id: str, listing_id: str) -> dict:
        """Withdraw a listing early (vendor only). Marked "expired",
        never deleted (L5)."""
        self._require_adult()
        vendor_id = valid_id(vendor_id, "vendor_id")
        listing_id = valid_id(listing_id, "listing_id")
        data = self._load()
        listing = self._get(data, listing_id)
        if listing["vendor_id"] != vendor_id:
            raise PlatformError(
                "only the vendor (%r) may expire listing %r."
                % (listing["vendor_id"], listing_id)
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

    # -- checkout: NOT_WIRED ---------------------------------------------

    def red1_details_for(self, buyer_id: str, listing_id: str) -> dict:
        """The exact ``details`` dict the RED-1 ceremony will consume for
        a resale checkout — the handoff contract with the sibling
        enforcement worker. The platform never acts on it."""
        self._require_adult()
        buyer_id = valid_id(buyer_id, "buyer_id")
        listing_id = valid_id(listing_id, "listing_id")
        listing = self._get(self._load(), listing_id)
        return build_red1_details(
            "resale_checkout",
            vendor_id=listing["vendor_id"],
            buyer_id=buyer_id,
            listing_id=listing_id,
            product=listing["product"],
            amount_cents=listing["price_cents"],
            quantity=listing["quantity"],
            unit=listing["unit"],
        )

    def checkout(self, buyer_id: str, listing_id: str) -> dict:
        """Check out a resale listing — NOT_WIRED.

        Raises NotWiredError fail-closed: nothing is charged, moved, or
        changed. The pending RED-1 details dict rides on the error for
        the enforcement worker.
        """
        self._require_adult()
        details = self.red1_details_for(buyer_id, listing_id)
        raise NotWiredError(
            capability="resale.checkout",
            missing="the enforcement worker's RED-1 payment ceremony — "
            "money moves through Cybrus only, and the ceremony is not "
            "wired yet.",
            details=details,
        )

    def prepare_checkout_request(
        self,
        buyer_id: str,
        listing_id: str,
        platform_destination,
        seller_pay_tier: str = "free",
        seller_destination=None,
    ) -> dict:
        """Prepare the payment request for a resale checkout. INERT.

        Builds the PaymentRequest (split, deep link, QR text, RED-1
        details) WITHOUT charging anything. checkout() stays NOT_WIRED.
        The seller's pay tier defaults to the provisional "free" tier;
        pass the seller's real tier/destination when known.
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
            kind="resale",
            total_cents=listing["price_cents"],
            tier=seller_pay_tier,
            platform_destination=platform_destination,
            creator_destination=seller_destination,
            memo="resale checkout %s listing %s" % (buyer_id, listing_id),
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
