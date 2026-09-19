"""Project 01 — Document-polish service (resumes, cover letters, LinkedIn).

Income mechanism: client pays per document package. LEVI does the
tedious parts offline: ATS keyword-gap analysis, package quoting, and
order tracking. Writing itself is assisted, never claimed as human-only.
Marketplace listing (Fiverr/etc.) and delivery are Chauncey-gated steps.

Risk band: low — paid-upfront client service, no platform lock-in beyond
the listing channel.
"""

from __future__ import annotations

import re
from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "resume-service",
    "name": "Document Polish Service",
    "automation": "semi",
    "setup_hours": 2,
    "days_to_first_dollar": "1-2",
    "daily_time_min": "20-30",
    "month3_range": (400, 1500),
    "risk_band": "low",
    "mechanism": "Per-order client payments for polished job-application documents.",
    "pricing": {
        "basic": {"price": 15, "delivery": "48h", "includes": "resume rewrite only"},
        "standard": {
            "price": 30,
            "delivery": "24h",
            "includes": "resume + tailored cover letter",
        },
        "premium": {
            "price": 50,
            "delivery": "same-day",
            "includes": "resume + cover letter + LinkedIn headline + summary",
        },
        "linkedin_addon": {
            "price": 20,
            "delivery": "24h",
            "includes": "bio, summary, headline",
        },
    },
    "chauncey_gated": [
        "Create the marketplace listing / gig page (account is yours).",
        "Review every document before delivery — you are the quality bar.",
        "Collect payment and confirm receipt before logging it.",
    ],
}

_STOP = set(
    "a an the and or of to in for with on at by from is are was were be been it its "
    "this that these those you your we our they their he she his her as at so if no "
    "not do does did will would can could should have has had having who what when "
    "where which how about into over after before between under within per etc us me my".split()
)


def _keywords(text: str) -> Dict[str, int]:
    words = re.findall(r"[a-z][a-z0-9+#.\-]{1,}", text.lower())
    counts: Dict[str, int] = {}
    for w in words:
        w = w.strip(".-")
        if len(w) < 3 or w in _STOP:
            continue
        counts[w] = counts.get(w, 0) + 1
    return counts


def ats_keyword_gap(resume_text: str, job_posting: str, top_n: int = 15) -> Dict:
    """Offline keyword-gap analysis.

    Finds substantive keywords that appear in the job posting but are
    missing (or rare) in the resume. Honest framing: this measures
    vocabulary overlap, not qualification — a gap is a prompt to add
    real experience, not to fabricate it.
    """
    if not resume_text.strip() or not job_posting.strip():
        raise ValueError("resume_text and job_posting must be non-empty")
    resume = _keywords(resume_text)
    posting = _keywords(job_posting)
    gaps: List[Dict] = []
    for word, count in sorted(posting.items(), key=lambda kv: -kv[1]):
        if word not in resume:
            gaps.append({"keyword": word, "posting_hits": count, "resume_hits": 0})
        if len(gaps) >= top_n:
            break
    shared = [w for w in posting if w in resume]
    coverage = len(shared) / max(len(posting), 1)
    return {
        "coverage": round(coverage, 3),
        "shared_keywords": len(shared),
        "posting_keywords": len(posting),
        "gaps": gaps,
        "note": "Gaps are vocabulary prompts — fill only with genuine experience.",
    }


def quote(tier: str, linkedin_addon: bool = False) -> Dict:
    """Package price for a tier (addon adds the LinkedIn rewrite)."""
    if tier not in PROJECT["pricing"]:
        raise ValueError(
            f"unknown tier {tier!r}; choose from {sorted(PROJECT['pricing'])}"
        )
    pkg = PROJECT["pricing"][tier]
    price = pkg["price"] + (
        PROJECT["pricing"]["linkedin_addon"]["price"]
        if linkedin_addon and tier != "linkedin_addon"
        else 0
    )
    return {
        "tier": tier,
        "price": price,
        "delivery": pkg["delivery"],
        "includes": pkg["includes"],
    }


def create_order(client: str, tier: str, linkedin_addon: bool = False) -> Dict:
    """Draft an order (no charge, no contact). Payment is Chauncey-confirmed."""
    q = quote(tier, linkedin_addon)
    return {
        "client": client,
        "tier": tier,
        "linkedin_addon": linkedin_addon,
        "price": q["price"],
        "delivery": q["delivery"],
        "status": "draft",
        "steps": [
            "Client sends current resume + target job posting.",
            "Rewrite for the posting: action verbs, quantified results, ATS-safe format.",
            "Run ats_keyword_gap; add missing keywords only from real experience.",
            "Format in a clean template; export DOCX.",
            "Chauncey reviews; then deliver via agreed channel.",
        ],
    }


def log_sale(order: Dict, note: str = "", home=None) -> Dict:
    """Receipt the payment Chauncey confirmed for a completed order."""
    return log_event(
        project=PROJECT["slug"],
        kind="sale",
        amount=order["price"],
        note=note or f"{order['tier']} package for {order['client']}",
        counterparty=order["client"],
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Pick your 3 package tiers and prices (defaults above).",
            "gated": False,
        },
        {
            "step": "Save a clean resume template (DOCX) you can reuse per order.",
            "gated": False,
        },
        {"step": "Create the marketplace listing / gig page.", "gated": True},
        {
            "step": "Post the offer in 2-3 job-seeker communities where allowed.",
            "gated": True,
        },
        {
            "step": "Fulfill first order end-to-end to time your workflow.",
            "gated": True,
        },
    ]
