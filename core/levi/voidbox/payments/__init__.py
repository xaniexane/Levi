"""Void Box payments — the money layer that does not move money.

WHAT THIS PACKAGE IS:
- A payment plugin registry (Cash App, PayPal — Chauncey's word).
- Request preparation: deep links + QR payloads, computed splits.
- Tier-based platform-cut accounting in integer cents (provisional table).
- Creator-chosen payout destinations, typed apart from the platform's.
- Receipt records that fail closed on verification.

WHAT THIS PACKAGE IS NOT (until Chauncey activates it):
- It does not charge, move, or settle money. subscribe()/purchase()/
  checkout() still raise NotWiredError.
- It holds no credentials, makes no API calls, runs no webhooks.
- Receipt verification always fails closed (no credentials to verify with).

MONEY FLOW (platform-collects — Chauncey's cut is taken at collection):
The payer pays the PLATFORM (Chauncey's Cash App/PayPal). The ledger
records the split: platform_cents to Chauncey, creator_cents owed to
the creator at their chosen CreatorDestination. The creator's payout
happens through the enforcement worker's RED-1 ceremony, not here.

LAWS live per module (LAWS tuples) and are machine-checked by
verify_laws(). Honestly named: invariant checks, not formal proof.

ONE ORGANISM: this package is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from levi.voidbox.payments import models, plugins, qr, requests, tiers

# Re-export the working surface.
from levi.voidbox.payments.models import (
    CreatorDestination,
    PaymentError,
    PaymentRequest,
    PaymentSplit,
    PlatformDestination,
    Receipt,
    cents,
    format_cents,
)
from levi.voidbox.payments.plugins import (
    CashAppPlugin,
    PaymentPlugin,
    PayPalPlugin,
    get_plugin,
    register,
    registered_names,
)
from levi.voidbox.payments.qr import (
    QRCode,
    QRCapacityError,
    QRError,
    QRRenderError,
    encode_qr,
    invite_qr,
    invite_qr_text,
    payment_qr,
    payment_qr_text,
    profile_qr,
    profile_qr_text,
)
from levi.voidbox.payments.requests import prepare_request
from levi.voidbox.payments.tiers import (
    TABLE_VERSION,
    confirm_table,
    confirmation,
    is_delegated,
    is_provisional,
    price_split,
    rate_for_tier,
)

#: All declared laws, machine-readable, namespaced by module.
LAWS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "models": models.LAWS,
    "plugins": plugins.LAWS,
    "qr": qr.LAWS,
    "requests": requests.LAWS,
    "tiers": tiers.LAWS,
}

__all__ = [
    "CreatorDestination", "PaymentError", "PaymentRequest", "PaymentSplit",
    "PlatformDestination", "Receipt", "cents", "format_cents",
    "CashAppPlugin", "PaymentPlugin", "PayPalPlugin",
    "get_plugin", "register", "registered_names",
    "QRCode", "QRCapacityError", "QRError", "QRRenderError",
    "encode_qr", "invite_qr", "invite_qr_text",
    "payment_qr", "payment_qr_text", "profile_qr", "profile_qr_text",
    "prepare_request",
    "TABLE_VERSION", "confirm_table", "confirmation", "is_delegated",
    "is_provisional", "price_split", "rate_for_tier",
    "LAWS", "verify_laws", "wiring_report",
]


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Run every module's machine-checked invariants. Returns
    (law_id, holds, detail). A single False fails the gate."""
    out: List[Tuple[str, bool, str]] = []
    for name, mod in (("models", models), ("plugins", plugins), ("qr", qr),
                      ("requests", requests), ("tiers", tiers)):
        for law_id, holds, detail in mod.verify_laws():
            out.append(("%s.%s" % (name, law_id), holds, detail))
    return out


def wiring_report() -> List[Tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("plugin_registry", True, "cashapp + paypal registered; pure link builders."),
        ("request_preparation", True, "prepare_request() builds inert requests with splits."),
        ("tier_cut_accounting", True, "integer-cent splits; table PROVISIONAL until Chauncey confirms."),
        ("creator_payout_destination", True, "typed CreatorDestination, separate from platform's."),
        ("qr_payment_payloads", True, "vendored QR: payment/invite/profile/listing texts."),
        ("receipt_records", True, "Receipt records claims; starts unverified."),
        ("receipt_verification", False,
         "needs provider credentials + webhooks; Chauncey has not activated. Fails closed."),
        ("money_movement", False,
         "charging/settlement needs the enforcement worker's RED-1 ceremony; NOT_WIRED."),
    ]
