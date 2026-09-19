"""Project 06 — Chatbot builds for small businesses.

Income mechanism: one-time setup fee + monthly maintenance retainer.
LEVI works offline: conversation-flow blueprints, quoting, retainer
math. Building on third-party bot platforms and client handover are
Chauncey-gated (accounts, credentials, and the client's platform bill
are theirs).

Risk band: medium — recurring retainers, but each client is custom
work and platforms can change pricing.
"""

from __future__ import annotations

from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "chatbot-service",
    "name": "Chatbot Building Service",
    "automation": "semi",
    "setup_hours": "3-5 per client",
    "days_to_first_dollar": "7-14",
    "daily_time_min": "10 monitoring",
    "month3_range": (375, 750),
    "risk_band": "medium",
    "mechanism": "Setup fee + monthly maintenance retainer per business.",
    "pricing": {
        "setup": (75, 150),
        "retainer_monthly": (25, 50),
        "emergency_update": 30,
        "feature_addon": 50,
    },
    "chauncey_gated": [
        "Onboarding call with the business (their needs, their answers).",
        "Build on the bot platform under the client's account/plan.",
        "Hand over credentials and train them on the dashboard.",
    ],
}

MENU_OPTIONS = ["Hours", "Pricing", "Book Appointment", "Services", "Talk to Owner"]


def build_flow(business_type: str, faqs: List[Dict]) -> Dict:
    """Conversation-flow blueprint: greeting, menu, FAQ branches, lead capture.

    faqs: list of {"q": ..., "a": ...} — the business's real answers,
    collected from the owner during onboarding.
    """
    if not faqs:
        raise ValueError("faqs must be non-empty — the owner supplies the answers")
    for f in faqs:
        if "q" not in f or "a" not in f:
            raise ValueError("each faq needs 'q' and 'a' keys")
    branches = [
        {"menu": opt, "action": f"answer or route for '{opt}'"} for opt in MENU_OPTIONS
    ]
    branches += [{"faq": f["q"], "answer": f["a"]} for f in faqs]
    return {
        "business_type": business_type,
        "greeting": "Welcome! I can help with hours, pricing, booking, and services — pick one below.",
        "branches": branches,
        "lead_capture": "End every path with: name + phone number, consent to contact.",
        "escalation": "High-intent lead -> notify the owner immediately.",
        "qa_checklist": [
            "Walk every branch on your own device.",
            "No dead ends: every path ends in lead capture or a clear next action.",
            "Confirm the owner's notification path works.",
        ],
        "status": "blueprint — build and handover are Chauncey-gated",
    }


def quote(setup: int = 100, retainer: int = 35, months: int = 12) -> Dict:
    lo_s, hi_s = PROJECT["pricing"]["setup"]
    lo_r, hi_r = PROJECT["pricing"]["retainer_monthly"]
    if not (lo_s <= setup <= hi_s) or not (lo_r <= retainer <= hi_r):
        raise ValueError(f"setup must be {lo_s}-{hi_s}, retainer {lo_r}-{hi_r}")
    return {
        "setup_fee": setup,
        "retainer_monthly": retainer,
        "first_year_total": setup + retainer * months,
        "addons": {
            "emergency_update": PROJECT["pricing"]["emergency_update"],
            "feature_addon": PROJECT["pricing"]["feature_addon"],
        },
    }


def retainer_book(clients: int, retainer: int = 35) -> Dict:
    """Monthly recurring math across N clients."""
    return {
        "clients": clients,
        "monthly_recurring": clients * retainer,
        "monthly_monitoring_min": clients * 10,
        "yearly_recurring": clients * retainer * 12,
    }


def log_setup(client: str, amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=amount,
        note=note or f"chatbot setup — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def log_retainer(client: str, amount: float, note: str = "", home=None) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="recurring",
        amount=amount,
        note=note or f"chatbot retainer — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {"step": "Pick one no-code bot platform to standardize on.", "gated": False},
        {
            "step": "Draft build_flow() for your first prospect's business type.",
            "gated": False,
        },
        {
            "step": "Onboarding call; collect their 10 FAQs and booking link.",
            "gated": True,
        },
        {
            "step": "Build, test every branch, deploy under their account.",
            "gated": True,
        },
        {"step": "Monthly 10-min check per client; log retainers.", "gated": True},
    ]
