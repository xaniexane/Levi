"""Payments + entitlements for the DemandPulse customer product — STUBBED.

OWNER GATE (explicit, non-negotiable):
  * No live payments. No real processor is wired. ``PAYMENT_PROCESSOR`` is
    None by design.
  * ``charge()`` and ``create_entitlement()`` REFUSE to run and raise
    ``PaymentNotAuthorized``. The refusal names the gate: Chauncey must
    approve (a) the payment destination, (b) the account, (c) the terms,
    (d) the entitlement design, and (e) the customer copy — per the
    publication-hold rule — before any charge path is built.
  * ``check_entitlement()`` is informational only: it always reports the
    ungated state and NEVER blocks the product. Entitlement enforcement is
    not authorized in this build; the product runs fully functional until
    the owner says otherwise.

When Chauncey approves the charge path, a future milestone wires a real
processor here, replaces this stub, and turns enforcement on — under his
explicit per-action word. Until then this file is the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, NoReturn, Optional

from levi.demandpulse.product import PRICE_CURRENCY, PRICE_MONTHLY


class PaymentNotAuthorized(Exception):
    """Raised when money is asked to move without the owner's approval."""


# No processor wired — this is the charge path staying dark.
PAYMENT_PROCESSOR = None

# ---------------------------------------------------------------------------
# HQ Decision 3 — billing terms (APPROVED 2026-09-24, Chauncey's word).
# Written for manual payments (no automation exists). Shipped verbatim in
# the customer bundle's TERMS.md. Do not paraphrase.
# ---------------------------------------------------------------------------
TERMS_HQ3 = """**DemandPulse — Billing Terms**

Price: $6/month USD. One tier. No free tier, no trial.

How you pay: send $6 to $DirectDepositDaemon on Cash App (PayPal works too —
ask for the address). Put "DemandPulse" and your email in the payment note.
Your month starts the day your payment is confirmed.

No auto-renewal: nothing charges you automatically. No card on file, no
subscription to cancel. To keep going, pay again before your month ends.
To stop, just don't pay — your access runs to the end of your paid month,
then pauses. Your settings and history are kept.

Missed payment: 7-day grace after your month ends. After that, access is
revoked until you pay again.

Refunds: 7 days, full $6, no questions. Ask within 7 days of payment and the
$6 comes back the same way it came, within 3 days. After day 7, no refunds —
the month's access was delivered.

What the $6 buys is the customer cut on the product sheet — the DemandPulse
engine, scan/score/surface, packaging. Nothing else is promised.

Disputes: talk to us first. These terms are plain speech on purpose — if
anything is unclear, ask before you pay."""


OWNER_GATE_NOTE = (
    "Payments are owner-gated: no live processor is wired and no charge is "
    "authorized. To activate billing, Chauncey must approve the payment "
    "destination, the account, the terms, the entitlement design, and the "
    "customer copy — each by explicit per-action word (publication hold "
    "stands). Until then every charge() call refuses."
)


@dataclass(frozen=True)
class EntitlementStatus:
    """What the stub knows about a customer's entitlement.

    ``active`` is always False here and ``enforced`` is always False:
    nothing in the product reads this to block features. Informational
    only, so the shape is ready when the owner approves real billing.
    """

    customer_id: str
    active: bool = False
    tier: str = "ungated"
    enforced: bool = False
    checked_at: str = ""
    reason: str = ""

    def to_record(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "active": self.active,
            "tier": self.tier,
            "enforced": self.enforced,
            "checked_at": self.checked_at,
            "reason": self.reason,
        }


def _refusal(action: str) -> NoReturn:
    raise PaymentNotAuthorized(
        f"{action} refused: {OWNER_GATE_NOTE} "
        f"(amount in question: {PRICE_MONTHLY:.2f} {PRICE_CURRENCY}/month)"
    )


def charge(customer_id: str, amount: Optional[float] = None) -> NoReturn:
    """Attempt a charge — always refuses. The charge path is dark."""
    # MONEY LAW: fail-closed stub. PAYMENT_PROCESSOR is None; every call
    # raises PaymentNotAuthorized. No charge path exists to wire.
    _ = (customer_id, amount)
    _refusal("charge")


def create_entitlement(customer_id: str) -> NoReturn:
    """Issue an entitlement — always refuses; no entitlement design approved."""
    _ = customer_id
    _refusal("create_entitlement")


def check_entitlement(customer_id: str) -> EntitlementStatus:
    """Informational entitlement check. Never blocks; always ungated."""
    return EntitlementStatus(
        customer_id=customer_id,
        active=False,
        tier="ungated",
        enforced=False,
        checked_at=datetime.now(timezone.utc).isoformat(),
        reason=(
            "payments owner-gated — product runs fully functional and ungated "
            "until Chauncey approves the charge path"
        ),
    )


def activation_checklist() -> Dict[str, Any]:
    """The five specifics the owner must decide before billing activates."""
    return {
        "price_anchor": f"{PRICE_MONTHLY:.2f} {PRICE_CURRENCY}/month",
        "processor": PAYMENT_PROCESSOR,
        "owner_decisions_required": [
            "payment destination (where the $6 goes)",
            "payment account (whose account receives it)",
            "terms (billing terms, refund policy)",
            "entitlement design (how a paying customer is recognized)",
            "customer copy approval (product sheet, pricing claims)",
        ],
        "gate_note": OWNER_GATE_NOTE,
        "status": "dark — no charges possible in this build",
    }
