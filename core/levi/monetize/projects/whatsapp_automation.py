"""Project 10 — WhatsApp business messaging automation.

Income mechanism: setup fee + monthly retainer, optionally reselling a
messaging platform seat at a margin. LEVI works offline: message-flow
sequences, margin math, retainer books. Platform accounts, API keys,
and anything touching real customer messages are Chauncey-gated.

Risk band: medium — customer messages are trust-bearing; flows run
24/7 and must never spam or misrepresent the business.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "whatsapp-automation",
    "name": "WhatsApp Business Automation",
    "automation": "semi",
    "setup_hours": "2-4 per client",
    "days_to_first_dollar": "7-14",
    "daily_time_min": "10 monitoring",
    "month3_range": (300, 600),
    "risk_band": "medium",
    "mechanism": "Setup fee + monthly retainer; optional platform resell margin.",
    "platforms": {
        "managed_basic": {
            "client_cost": 39,
            "resell": (75, 100),
            "label": "managed seat, basic",
        },
        "managed_pro": {
            "client_cost": 79,
            "resell": (120, 150),
            "label": "managed seat, pro",
        },
        "custom_api": {
            "setup": (100, 200),
            "retainer": (30, 75),
            "label": "custom API build",
        },
    },
    "chauncey_gated": [
        "Platform accounts and API keys live with the client, never with LEVI.",
        "The business owner approves every automated message template.",
        "Opt-in/opt-out handling must comply with messaging rules (owner's responsibility).",
    ],
}

SEQUENCE_STEPS = [
    ("welcome", "New contact -> greeting + what this business offers."),
    ("faq", "Top-10 questions auto-answered from the owner's answers."),
    ("appointment_reminder", "24h before + 1h before, with confirm/cancel."),
    ("order_updates", "Confirmation + delivery status messages."),
    ("review_request", "Post-purchase follow-up asking for a review."),
    ("hot_lead_alert", "High-intent message -> immediate ping to the owner."),
]


def flow_sequence(business_type: str) -> Dict:
    """Standard messaging sequence blueprint for a business type."""
    return {
        "business_type": business_type,
        "steps": [{"name": name, "job": job} for name, job in SEQUENCE_STEPS],
        "rules": [
            "Only reply to messages the customer initiated or opted into.",
            "Every flow has an escape hatch to a human.",
            "Owner approves all templates before go-live.",
        ],
        "status": "blueprint — build and approval are Chauncey-gated",
    }


def resell_margin(platform: str, resell_price: float) -> Dict:
    """Monthly margin when reselling a managed platform seat."""
    if platform not in ("managed_basic", "managed_pro"):
        raise ValueError("platform must be 'managed_basic' or 'managed_pro'")
    spec = PROJECT["platforms"][platform]
    lo, hi = spec["resell"]
    if not (lo <= resell_price <= hi):
        raise ValueError(f"resell_price must be {lo}-{hi} for {platform}")
    margin = resell_price - spec["client_cost"]
    return {
        "platform": platform,
        "platform_cost": spec["client_cost"],
        "resell_price": resell_price,
        "monthly_margin": round(margin, 2),
        "yearly_margin": round(margin * 12, 2),
    }


def quote(platform: str, resell_price: float | None = None, setup: float = 0.0) -> Dict:
    """Client quote: platform pass-through (client pays) + your margin/setup."""
    if platform == "custom_api":
        lo_s, hi_s = PROJECT["platforms"]["custom_api"]["setup"]
        lo_r, hi_r = PROJECT["platforms"]["custom_api"]["retainer"]
        return {
            "platform": platform,
            "setup_fee": (lo_s, hi_s),
            "retainer_monthly": (lo_r, hi_r),
            "note": "Custom build: Chauncey codes it; client owns the API account.",
        }
    if resell_price is None:
        raise ValueError("resell_price required for managed platforms")
    m = resell_margin(platform, resell_price)
    return {
        **m,
        "setup_fee": setup,
        "note": "Client pays the platform directly; you keep the margin.",
    }


def log_setup(client: str, amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=amount,
        note=note or f"WhatsApp setup — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def log_retainer(client: str, amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="recurring",
        amount=amount,
        note=note or f"WhatsApp retainer — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {"step": "Standardize on one platform tier to resell.", "gated": False},
        {
            "step": "Draft flow_sequence() for your first prospect's business.",
            "gated": False,
        },
        {
            "step": "Client creates their platform account; owner approves templates.",
            "gated": True,
        },
        {
            "step": "Build flows; test welcome/FAQ/reminder paths end-to-end.",
            "gated": True,
        },
        {"step": "Go live; monitor 10 min/day; log retainers.", "gated": True},
    ]
