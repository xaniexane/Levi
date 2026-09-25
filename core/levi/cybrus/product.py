"""Cybrus standalone product definition (LEVI-original).

The customer-facing product surface for Cybrus as a standalone product —
mirroring the DemandPulse product pattern (product.py / quickstart.py /
payments-gate / production doc), not its content.

Pricing is EXPLICITLY UNDECIDED: ``PRICE_MONTHLY`` is ``None`` and every
price surface says so. DemandPulse's $6/mo anchor was Chauncey's call;
Cybrus pricing is his call too — this module must never invent it.
"""

from __future__ import annotations

PRODUCT_NAME = "Cybrus"
PRODUCT_TAGLINE = "Your credentials, held like they matter. Automated Bitwarden-grade vault, third-party broker, and OAuth layer — local-first."
PRODUCT_VERSION = "0.1.0"

# Pricing: UNDECIDED — flagged for Chauncey. Do not invent a number here.
PRICE_MONTHLY = None
PRICE_CURRENCY = "USD"
PRICE_STATUS = (
    "Pricing is Chauncey's decision — not set in this build. "
    "DemandPulse's $6/mo anchor does not transfer automatically."
)

FEATURES = (
    "Encrypted credential vault (AES-128/Fernet when available, labeled stdlib fallback)",
    "Password generation — strong, local, never leaves the machine",
    "Third-party credential broker — provision and track accounts on external platforms",
    "Platform OAuth layer — authorization flows, token vault, refresh tracking",
    "Scoped API tokens — issued once, hashed at rest, rotated and revoked on demand",
    "Human approval gates on consequential actions",
    "Tier-based anti-spam rate limits on automated retrieval (free tier: vault only)",
    "Tamper-evident audit log for every vault and broker event",
    "Money-law compliance — Cybrus remains the only money-handler on the platform",
)


def broker_status() -> str:
    """Whether the third-party broker module has landed yet."""
    try:
        import levi.cybrus.broker  # noqa: F401

        return "landed"
    except ImportError:
        return "landing — hookup points ready, module in flight"


def price_line() -> str:
    return f"{PRODUCT_NAME}: {PRICE_STATUS}"


def product_sheet() -> str:
    lines = [
        f"{PRODUCT_NAME} v{PRODUCT_VERSION}",
        PRODUCT_TAGLINE,
        "",
        "What you get:",
    ]
    lines.extend(f"  - {feature}" for feature in FEATURES)
    lines += [
        "",
        "Security model:",
        "  - Encrypted at rest. Master password never stored.",
        "  - Secrets are never taken via argv, never printed to logs,",
        "    and never leave the machine.",
        "  - Consequential actions wait on your approval; every event",
        "    is written to a tamper-evident audit log.",
        "",
        f"Broker module: {broker_status()}",
        "",
        price_line(),
    ]
    return "\n".join(lines)
