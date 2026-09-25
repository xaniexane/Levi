"""Void Box payments — request preparation. The money never moves here.

``prepare_request()`` is the single front door: given the kind of
payment, the amount, the creator's tier and destination, and the
platform destination, it computes the split, builds the plugin deep
link, and attaches the RED-1 details dict the enforcement worker's
ceremony will consume.

What it does NOT do: no network, no charge, no credential use, no
webhooks. The returned PaymentRequest is inert (models.PM4). The
actual money movement stays NOT_WIRED until Chauncey activates it —
``subscribe()`` / ``purchase()`` / ``checkout()`` keep raising
NotWiredError.

LAWS (P-requests):
- PR1 — One front door: every prepared request goes through
  prepare_request(), so the split math and RED-1 shape cannot drift.
- PR2 — Platform destination required: a request without Chauncey's
  destination is refused — the platform cut always has somewhere to go.
- PR3 — Creator destination optional but typed: when present it must
  be a CreatorDestination (never a bare string, never the platform's).
- PR4 — RED-1 attached: every request carries the exact details dict
  the ceremony will consume, status pending_enforcement.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from levi.voidbox.payments.models import (
    CreatorDestination,
    PaymentError,
    PaymentRequest,
    PlatformDestination,
    cents,
)
from levi.voidbox.payments.plugins import get_plugin
from levi.voidbox.payments.qr import payment_qr_text
from levi.voidbox.payments.tiers import TABLE_VERSION, confirmation, is_provisional, price_split

#: Declared laws, machine-readable.
LAWS = (
    ("PR1", "One front door: every prepared request goes through prepare_request()."),
    ("PR2", "Platform destination required: the platform cut always has somewhere to go."),
    ("PR3", "Creator destination optional but typed: CreatorDestination or None, never a bare string."),
    ("PR4", "RED-1 attached: every request carries the ceremony details, status pending_enforcement."),
)

_KINDS = ("subscription", "classified", "resale")


def prepare_request(
    kind: str,
    total_cents: int,
    tier: str,
    platform_destination: PlatformDestination,
    creator_destination: Optional[CreatorDestination] = None,
    memo: str = "",
) -> PaymentRequest:
    """Prepare a payment request. Inert — moves nothing.

    The deep link is built for the PLATFORM destination (Chauncey's
    Cash App / PayPal): the payer pays the platform, and the ledger
    records the creator's share owed from the split. The creator is
    paid out from the platform side — their CreatorDestination is
    recorded on the request so the payout can never go to the wrong
    place, but no payout happens here.
    """
    if kind not in _KINDS:
        raise PaymentError("payment kind must be one of %s." % (_KINDS,))
    total_cents = cents(total_cents, "total_cents")
    if not isinstance(platform_destination, PlatformDestination):
        raise PaymentError(
            "platform_destination must be a PlatformDestination — the "
            "platform cut always has somewhere to go (PR2)."
        )
    if creator_destination is not None and not isinstance(
        creator_destination, CreatorDestination
    ):
        raise PaymentError(
            "creator_destination must be a CreatorDestination or None — "
            "never a bare string (PR3)."
        )

    split = price_split(total_cents, tier)
    plugin = get_plugin(platform_destination.plugin)
    deep_link = plugin.build_request_link(
        platform_destination.handle, total_cents, memo=memo
    )
    qr_text = payment_qr_text(plugin.name, deep_link)

    request_id = "pay_%s" % uuid4().hex[:16]
    red1_details: Dict[str, Any] = {
        "ceremony": "RED-1",
        "kind": "payment." + kind,
        "currency": "USD",
        "total_cents": total_cents,
        "split": split.as_dict(),
        "tier_table": TABLE_VERSION,
        "tier_provisional": is_provisional(),
        "tier_confirmation": confirmation(),
        "plugin": plugin.name,
        "platform_destination": {
            "plugin": platform_destination.plugin,
            "handle": platform_destination.handle,
        },
        "creator_destination": (
            {
                "plugin": creator_destination.plugin,
                "handle": creator_destination.handle,
                "creator_id": creator_destination.creator_id,
            }
            if creator_destination
            else None
        ),
        "memo": memo,
        "status": "pending_enforcement",
    }
    return PaymentRequest(
        request_id=request_id,
        kind=kind,
        plugin=plugin.name,
        deep_link=deep_link,
        qr_text=qr_text,
        split=split,
        creator_destination=creator_destination,
        platform_destination=platform_destination,
        memo=memo or "",
        red1_details=red1_details,
    )


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked request invariants."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    pd = PlatformDestination(plugin="cashapp", handle="$chauncey")
    cd = CreatorDestination(plugin="paypal", handle="creator-handle", creator_id="c1")

    # PR1/PR4: one front door, RED-1 attached, pending.
    r = prepare_request("subscription", 2500, "free", pd, cd, memo="tier sub")
    check("PR1", r.request_id.startswith("pay_") and r.kind == "subscription",
          "request prepared: %s" % r.request_id)
    check("PR4", r.red1_details.get("ceremony") == "RED-1"
          and r.red1_details.get("status") == "pending_enforcement",
          "RED-1 details attached, pending_enforcement")
    check("PR4", r.split.total_cents == 2500
          and r.split.platform_cents + r.split.creator_cents == 2500,
          "split on the request sums exactly")

    # PR2: platform destination required.
    try:
        prepare_request("resale", 100, "free", None)  # type: ignore[arg-type]
        check("PR2", False, "request without platform destination accepted")
    except PaymentError:
        check("PR2", True, "request without platform destination refused")

    # PR3: creator destination typed.
    try:
        prepare_request("classified", 100, "free", pd, "$bare-string")  # type: ignore[arg-type]
        check("PR3", False, "bare-string creator destination accepted")
    except PaymentError:
        check("PR3", True, "bare-string creator destination refused")
    r2 = prepare_request("classified", 100, "free", pd, None)
    check("PR3", r2.creator_destination is None, "None creator destination allowed")

    # Deep link targets the PLATFORM (Chauncey), not the creator.
    check("PR2", "$chauncey" in r.deep_link and "creator-handle" not in r.deep_link,
          "payer pays the platform: %s" % r.deep_link)

    return results
