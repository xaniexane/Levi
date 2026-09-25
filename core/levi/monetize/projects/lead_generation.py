"""Project 07 — Local lead generation service.

Income mechanism: per-qualified-lead fees from local businesses
($25-$300 depending on niche). LEVI works offline: lead records,
invoice math, campaign ROI. Outreach, ad spend, and lead delivery are
Chauncey-gated — Chauncey sets the per-lead price and approves every
business relationship.

Risk band: medium — income depends on lead flow and buyer payment
discipline; rule: no invoice, no lead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "lead-generation",
    "name": "Local Lead Generation",
    "automation": "semi",
    "setup_hours": "2-3 per campaign",
    "days_to_first_dollar": "7-14",
    "daily_time_min": "20 monitoring",
    "month3_range": (800, 1500),
    "risk_band": "medium",
    "mechanism": "Businesses pay per qualified lead delivered (name, phone, service need).",
    "lead_price_range": {"home_services": (25, 100), "legal_financial": (50, 300)},
    "chauncey_gated": [
        "Negotiate per-lead price and payment terms with each business (your call).",
        "Publish the landing page and any paid ads (your spend).",
        "Deliver leads to the buyer; enforce the no-invoice-no-lead rule.",
    ],
}


def record_lead(
    campaign: str, name: str, phone: str, need: str, email: str = ""
) -> Dict:
    """A lead intake record. Consent to contact the lead is the buyer's job."""
    if not all([campaign.strip(), name.strip(), phone.strip(), need.strip()]):
        raise ValueError("campaign, name, phone, and need are required")
    return {
        "campaign": campaign,
        "name": name,
        "phone": phone,
        "email": email,
        "need": need,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "new",
        "delivered": False,
    }


def invoice(lead: Dict, price_per_lead: float) -> Dict:
    """Per-lead invoice draft — Chauncey sends it; payment must land first."""
    if price_per_lead <= 0:
        raise ValueError("price_per_lead must be positive")
    return {
        "lead": lead["name"],
        "campaign": lead["campaign"],
        "amount": round(price_per_lead, 2),
        "status": "unpaid — no lead delivered until paid",
    }


def campaign_roi(leads: int, price_per_lead: float, ad_spend: float = 0.0) -> Dict:
    """Honest campaign math: revenue, spend, net, cost per lead."""
    if leads < 0 or price_per_lead < 0 or ad_spend < 0:
        raise ValueError("inputs must be non-negative")
    revenue = leads * price_per_lead
    net = revenue - ad_spend
    return {
        "leads": leads,
        "revenue": round(revenue, 2),
        "ad_spend": round(ad_spend, 2),
        "net": round(net, 2),
        "cost_per_lead": round(ad_spend / leads, 2) if leads else 0.0,
        "profitable": net > 0,
    }


def log_lead_payment(
    client: str, leads: int, amount: float, note: str = "", home=None
) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=amount,
        note=note or f"{leads} leads — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Pick one high-value niche (roofing, HVAC, plumbing...).",
            "gated": False,
        },
        {"step": "Call/visit 3 businesses; negotiate per-lead price.", "gated": True},
        {"step": "Publish a one-page lead-capture landing page.", "gated": True},
        {
            "step": "Drive traffic (community posts first, paid ads only if you approve).",
            "gated": True,
        },
        {"step": "Invoice weekly; deliver on payment; log receipts.", "gated": True},
    ]
