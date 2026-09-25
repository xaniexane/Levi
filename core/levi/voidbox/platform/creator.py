"""Void Box platform — creator: profiles, subscription tiers, grants.

FORMED: creator profile data model + validation, subscription tier
model + validation, subscriber grant records (admin/comped grants),
revocation. Every grant carries the exact ``details`` dict the RED-1
ceremony will consume (``red1_details``), marked
``"status": "pending_enforcement"``.

NOT_WIRED (scaffolded, raises NotWiredError): charging — anything that
moves money. ``subscribe()`` (the buyer-facing purchase path) fails
closed and names the missing enforcement wiring. Money moves through
Cybrus only; the platform holds NO money logic.

SI side: every public entry point calls ``require_adult()`` FIRST —
adult-only, default OFF.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — Adult gate: every public entry point calls require_adult()
  first — default OFF, minors hard-locked out; every refusal names its
  remedy. (WIRED)
- L2 — Validated models: creator handles unique and shaped; tier
  prices are integer cents >= 0; perks capped; billing drawn from a
  fixed enum. Bad input fails closed. (WIRED)
- L3 — Grants are records, not charges: subscriber grants record who
  may access what at which tier; the money side stays a pending
  RED-1 details dict until the enforcement worker wires it. (WIRED)
- L4 — Charging is NOT_WIRED: subscribe() raises NotWiredError naming
  the missing payment enforcement; nothing is charged, moved, or
  changed. (NOT_WIRED)
- L5 — Nothing thrown away: revocations and tier retirements mark
  state; records persist. (WIRED)

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from levi.voidbox.platform import (
    JsonStore,
    NotWiredError,
    PlatformError,
    ProfileNotFoundError,
    build_red1_details,
    utcnow,
    valid_handle,
    valid_id,
    valid_price_cents,
    valid_text,
)
from levi.voidbox.rooms import NotAdminError

#: The declared laws, machine-readable.
LAWS = (
    ("L1", "Adult gate: every public entry point calls require_adult() first — default OFF, minors hard-locked out; every refusal names its remedy. (WIRED)"),
    ("L2", "Validated models: unique shaped creator handles; tier prices are integer cents >= 0; perks capped; billing from a fixed enum; bad input fails closed. (WIRED)"),
    ("L3", "Grants are records, not charges: subscriber grants record access; the money side stays a pending RED-1 details dict. (WIRED)"),
    ("L4", "Charging is NOT_WIRED: subscribe() raises NotWiredError naming the missing payment enforcement; nothing charged, moved, or changed. (NOT_WIRED)"),
    ("L5", "Nothing thrown away: revocations and tier retirements mark state; records persist. (WIRED)"),
)

_BILLING = ("monthly", "yearly", "one_time", "free")
_MAX_PERKS = 20
_MAX_PERK_LEN = 80


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("creator_profile", True, "create/get with validation."),
        ("subscription_tiers", True, "define/retire tiers with validation."),
        ("grant_subscription", True, "admin/comped grant records with RED-1 details."),
        ("revoke_subscription", True, "revocation marks state."),
        (
            "subscribe",
            False,
            "charging: the buyer-facing purchase path needs the "
            "enforcement worker's RED-1 ceremony wiring; money moves "
            "through Cybrus only.",
        ),
    ]


def _validate_tier_fields(
    name: str, price_cents: int, billing: str, perks: object
) -> dict:
    name = valid_text(name, "tier name", max_len=64)
    price_cents = valid_price_cents(price_cents, "tier price")
    if billing not in _BILLING:
        raise PlatformError(
            "billing must be one of %s, got %r." % (_BILLING, billing)
        )
    if not isinstance(perks, (list, tuple)):
        raise PlatformError("perks must be a list of text.")
    if len(perks) > _MAX_PERKS:
        raise PlatformError("at most %d perks per tier." % _MAX_PERKS)
    clean_perks = [valid_text(p, "perk", max_len=_MAX_PERK_LEN) for p in perks]
    return {
        "name": name,
        "price_cents": price_cents,
        "billing": billing,
        "perks": clean_perks,
    }


class CreatorStore(JsonStore):
    """Creator profiles, tiers, and subscriber grants. Owner-only JSON."""

    _FILENAME = "creator.json"

    def __init__(self, home: Optional[Path] = None):
        super().__init__(home)

    # -- creator profiles ------------------------------------------------

    def create_creator(
        self, creator_id: str, handle: str, display_name: str, bio: str = ""
    ) -> dict:
        """Register a creator profile. Handle unique store-wide."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        handle = valid_handle(handle)
        display_name = valid_text(display_name, "display_name", max_len=64)
        bio = valid_text(bio, "bio", max_len=500, allow_empty=True)
        data = self._load()
        creators = data.setdefault("creators", {})
        if creator_id in creators:
            raise PlatformError("creator %r already exists." % creator_id)
        if any(c["handle"] == handle for c in creators.values()):
            raise PlatformError("handle %r is already taken." % handle)
        creators[creator_id] = {
            "creator_id": creator_id,
            "handle": handle,
            "display_name": display_name,
            "bio": bio,
            "created_at": utcnow(),
        }
        self._save(data)
        return dict(creators[creator_id])

    def get_creator(self, creator_id: str) -> dict:
        """Fetch a creator profile."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        return dict(self._get_creator(self._load(), creator_id))

    @staticmethod
    def _get_creator(data: dict, creator_id: str) -> dict:
        creator = data.get("creators", {}).get(creator_id)
        if creator is None:
            raise ProfileNotFoundError("no creator %r." % creator_id)
        return creator

    # -- subscription tiers ----------------------------------------------

    def define_tier(
        self,
        creator_id: str,
        tier_id: str,
        name: str,
        price_cents: int,
        billing: str = "monthly",
        perks: tuple = (),
    ) -> dict:
        """Define (or redefine) a subscription tier for a creator."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        tier_id = valid_id(tier_id, "tier_id")
        fields = _validate_tier_fields(name, price_cents, billing, perks)
        data = self._load()
        self._get_creator(data, creator_id)
        tiers = data.setdefault("tiers", {}).setdefault(creator_id, {})
        tiers[tier_id] = {
            "tier_id": tier_id,
            "creator_id": creator_id,
            "retired": False,
            **fields,
            "defined_at": utcnow(),
        }
        self._save(data)
        return dict(tiers[tier_id])

    def retire_tier(self, creator_id: str, tier_id: str) -> dict:
        """Retire a tier. Marked retired, never deleted (L5); existing
        grants are untouched."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        tier_id = valid_id(tier_id, "tier_id")
        data = self._load()
        tier = self._get_tier(data, creator_id, tier_id)
        tier["retired"] = True
        tier["retired_at"] = utcnow()
        self._save(data)
        return dict(tier)

    def list_tiers(self, creator_id: str, include_retired: bool = False) -> list[dict]:
        """List a creator's tiers."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        data = self._load()
        self._get_creator(data, creator_id)
        tiers = data.get("tiers", {}).get(creator_id, {})
        return [
            dict(t) for t in tiers.values()
            if include_retired or not t.get("retired")
        ]

    @staticmethod
    def _get_tier(data: dict, creator_id: str, tier_id: str) -> dict:
        tier = data.get("tiers", {}).get(creator_id, {}).get(tier_id)
        if tier is None:
            raise ProfileNotFoundError(
                "no tier %r for creator %r." % (tier_id, creator_id)
            )
        return tier

    # -- grants (formed) vs charging (NOT_WIRED) --------------------------

    def red1_details_for(
        self, creator_id: str, subscriber_id: str, tier_id: str
    ) -> dict:
        """The exact ``details`` dict the RED-1 ceremony will consume for
        a subscription purchase. This is the handoff contract with the
        sibling enforcement worker — the platform never acts on it."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        tier_id = valid_id(tier_id, "tier_id")
        data = self._load()
        tier = self._get_tier(data, creator_id, tier_id)
        return build_red1_details(
            "subscription_purchase",
            creator_id=creator_id,
            subscriber_id=subscriber_id,
            tier_id=tier_id,
            tier_name=tier["name"],
            amount_cents=tier["price_cents"],
            billing=tier["billing"],
        )

    def subscribe(self, subscriber_id: str, creator_id: str, tier_id: str) -> dict:
        """Buyer-facing subscription purchase — NOT_WIRED.

        Raises NotWiredError fail-closed: nothing is charged, moved, or
        changed. The pending RED-1 details dict is attached to the error
        so the enforcement worker has the exact handoff it needs.
        """
        self._require_adult()
        details = self.red1_details_for(creator_id, subscriber_id, tier_id)
        raise NotWiredError(
            capability="creator.subscribe",
            missing="the enforcement worker's RED-1 payment ceremony — "
            "money moves through Cybrus only, and the ceremony is not "
            "wired yet.",
            details=details,
        )

    def grant_subscription(
        self,
        creator_id: str,
        subscriber_id: str,
        tier_id: str,
        granted_by: str,
        note: str = "",
    ) -> dict:
        """Record a subscriber grant (creator-issued / comped). FORMED.

        This is a record of access, not a charge: the money side stays a
        pending RED-1 details dict (L3). Only the creator (or an id
        matching the creator) may grant.
        """
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        tier_id = valid_id(tier_id, "tier_id")
        granted_by = valid_id(granted_by, "granted_by")
        note = valid_text(note, "note", max_len=200, allow_empty=True)
        if granted_by != creator_id:
            raise NotAdminError(
                "only the creator (%r) may grant subscriptions to their "
                "tiers." % creator_id
            )
        data = self._load()
        tier = self._get_tier(data, creator_id, tier_id)
        if tier.get("retired"):
            raise PlatformError("tier %r is retired." % tier_id)
        details = self.red1_details_for(creator_id, subscriber_id, tier_id)
        grants = data.setdefault("grants", {})
        key = "%s:%s:%s" % (creator_id, subscriber_id, tier_id)
        grants[key] = {
            "creator_id": creator_id,
            "subscriber_id": subscriber_id,
            "tier_id": tier_id,
            "granted_by": granted_by,
            "note": note,
            "status": "active",
            "revoked": False,
            "granted_at": utcnow(),
            "red1_details": details,  # the handoff; status stays pending
        }
        self._save(data)
        return dict(grants[key])

    def revoke_subscription(
        self, creator_id: str, subscriber_id: str, tier_id: str, by: str
    ) -> dict:
        """Revoke a grant. Marked revoked, never deleted (L5)."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        tier_id = valid_id(tier_id, "tier_id")
        by = valid_id(by, "by")
        if by != creator_id:
            raise NotAdminError(
                "only the creator (%r) may revoke their grants." % creator_id
            )
        data = self._load()
        key = "%s:%s:%s" % (creator_id, subscriber_id, tier_id)
        grant = data.get("grants", {}).get(key)
        if grant is None:
            raise ProfileNotFoundError("no such grant %r." % key)
        grant["revoked"] = True
        grant["status"] = "revoked"
        grant["revoked_at"] = utcnow()
        self._save(data)
        return dict(grant)

    def active_subscriptions(self, subscriber_id: str) -> list[dict]:
        """Grants currently active for a subscriber."""
        self._require_adult()
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        data = self._load()
        return [
            dict(g) for g in data.get("grants", {}).values()
            if g["subscriber_id"] == subscriber_id and not g.get("revoked")
        ]

    # -- payout destinations + prepared payment requests -------------------

    def set_payout_destination(
        self, creator_id: str, plugin: str, handle: str, by: str
    ) -> dict:
        """The creator chooses how THEY get paid (Chauncey's word).

        Only the creator may set their own payout destination. The
        destination is validated by the plugin and stored on the
        creator's profile — typed apart from the platform destination
        (payments.models.PM3). Nothing is charged or moved here.
        """
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        by = valid_id(by, "by")
        if by != creator_id:
            raise NotAdminError(
                "only the creator (%r) may set their payout destination."
                % creator_id
            )
        from levi.voidbox.payments.plugins import get_plugin

        plugin_obj = get_plugin(plugin)  # unknown plugins fail closed
        clean_handle = plugin_obj.validate_handle(handle)
        data = self._load()
        creator = self._get_creator(data, creator_id)
        creator["payout"] = {
            "plugin": plugin_obj.name,
            "handle": clean_handle,
            "set_at": utcnow(),
        }
        self._save(data)
        return dict(creator["payout"])

    def get_payout_destination(self, creator_id: str):
        """The creator's chosen payout destination, as a typed
        CreatorDestination. None when the creator hasn't chosen yet."""
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        creator = self._get_creator(self._load(), creator_id)
        payout = creator.get("payout")
        if not payout:
            return None
        from levi.voidbox.payments.models import CreatorDestination

        return CreatorDestination(
            plugin=payout["plugin"],
            handle=payout["handle"],
            creator_id=creator_id,
        )

    def set_pay_tier(self, creator_id: str, pay_tier: str, by: str) -> dict:
        """Set the creator's platform pay tier (drives the platform cut).

        The pay-tier table is PROVISIONAL until Chauncey confirms it —
        see levi.voidbox.payments.tiers. Only the creator may set their
        own pay tier; unknown tiers fail closed.
        """
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        by = valid_id(by, "by")
        if by != creator_id:
            raise NotAdminError(
                "only the creator (%r) may set their pay tier." % creator_id
            )
        from levi.voidbox.payments.tiers import rate_for_tier

        rate_for_tier(pay_tier)  # validates; unknown tiers fail closed
        data = self._load()
        creator = self._get_creator(data, creator_id)
        creator["pay_tier"] = pay_tier
        self._save(data)
        return {"creator_id": creator_id, "pay_tier": pay_tier}

    def prepare_subscribe_request(
        self,
        subscriber_id: str,
        creator_id: str,
        tier_id: str,
        platform_destination,
    ) -> dict:
        """Prepare the payment request for a tier subscription. INERT.

        Builds the PaymentRequest (split, deep link, QR text, RED-1
        details) WITHOUT charging anything. The buyer-facing
        subscribe() stays NOT_WIRED — this is the handoff the
        enforcement worker's ceremony will consume.
        """
        self._require_adult()
        creator_id = valid_id(creator_id, "creator_id")
        subscriber_id = valid_id(subscriber_id, "subscriber_id")
        tier_id = valid_id(tier_id, "tier_id")
        data = self._load()
        tier = self._get_tier(data, creator_id, tier_id)
        if tier.get("retired"):
            raise PlatformError("tier %r is retired." % tier_id)
        creator = self._get_creator(data, creator_id)
        pay_tier = creator.get("pay_tier") or "free"  # provisional default
        creator_dest = self.get_payout_destination(creator_id)

        from levi.voidbox.payments.requests import prepare_request

        req = prepare_request(
            kind="subscription",
            total_cents=tier["price_cents"],
            tier=pay_tier,
            platform_destination=platform_destination,
            creator_destination=creator_dest,
            memo="subscribe %s -> %s tier %s" % (subscriber_id, creator_id, tier_id),
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
