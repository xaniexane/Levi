"""Project 09 — Data collection & web scraping service (defensive posture).

Income mechanism: per-job fees for collecting PUBLIC data into
spreadsheets, plus recurring refresh contracts. LEVI stays strictly
defensive/blue-team: only publicly accessible pages, always check
robots.txt, never touch login-protected pages, payment info, or
personal PII. Any questionable target is refused by default and
escalated to Chauncey.

Risk band: medium — recurring contracts are sticky, but the legal
and reputational risk of careless scraping is real; the guards below
are the product.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from typing import Dict, List

from ..ledger import log_event

PROJECT = {
    "slug": "data-scraping",
    "name": "Data Collection Service",
    "automation": "semi",
    "setup_hours": "2-3 days for the base template",
    "days_to_first_dollar": "7",
    "daily_time_min": "15-30",
    "month3_range": (400, 800),
    "risk_band": "medium",
    "mechanism": "Per-job fees for public-data collection; recurring weekly refreshes.",
    "pricing": {"small_job": (15, 50), "large_job": (50, 200), "recurring_monthly": 75},
    "chauncey_gated": [
        "Approve every target site before a job is accepted.",
        "Accept or reject any target the guards flag.",
        "Deliver results and invoice the client.",
    ],
}

# Field names we will never extract — hard refusal, no override path.
FORBIDDEN_FIELDS = {
    "password",
    "passwd",
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
    "bank_account",
    "routing_number",
    "private_key",
    "api_key",
    "token",
    "session",
    "cookie",
    "dob",
    "date_of_birth",
}


def guard_fields(requested_fields: List[str]) -> Dict:
    """Refuse forbidden fields outright. Public business data only."""
    bad = [
        f
        for f in requested_fields
        if f.strip().lower().replace(" ", "_") in FORBIDDEN_FIELDS
    ]
    if bad:
        return {
            "allowed": False,
            "reason": f"refused forbidden fields: {bad}. Personal/financial data is never collected.",
        }
    return {"allowed": True, "fields": requested_fields}


def robots_allows(url: str, user_agent: str = "LEVI-data-service") -> Dict:
    """Fetch and parse robots.txt for the target host. Advisory, not legal advice."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"not a valid http(s) URL: {url!r}")
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return {
            "checked": False,
            "allows": False,
            "reason": f"could not fetch robots.txt ({type(exc).__name__}); treat as DISALLOW until Chauncey approves.",
        }
    path = parsed.path or "/"
    disallowed: List[str] = []
    applies = False
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            ua = line.split(":", 1)[1].strip()
            applies = ua in ("*", user_agent)
        elif applies and line.lower().startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule:
                disallowed.append(rule)
    blocked = any(path.startswith(rule) for rule in disallowed)
    return {
        "checked": True,
        "allows": not blocked,
        "disallowed_rules": disallowed,
        "reason": "path blocked by robots.txt"
        if blocked
        else "no blocking rule for this path",
    }


def preflight(url: str, requested_fields: List[str]) -> Dict:
    """Run every guard before a job is accepted. All must pass."""
    field_check = guard_fields(requested_fields)
    if not field_check["allowed"]:
        return {"accepted": False, **field_check}
    robot_check = robots_allows(url)
    if not robot_check["allows"]:
        return {
            "accepted": False,
            "reason": robot_check["reason"],
            "robots": robot_check,
        }
    return {
        "accepted": True,
        "fields": requested_fields,
        "robots": robot_check,
        "note": "Guards passed. Final approval is still Chauncey's.",
    }


def quote(rows: int, complexity: str = "simple") -> Dict:
    """Job pricing: small jobs by row count, large/complex by band."""
    if rows < 0:
        raise ValueError("rows must be >= 0")
    if complexity not in ("simple", "complex"):
        raise ValueError("complexity must be 'simple' or 'complex'")
    lo, hi = (
        PROJECT["pricing"]["small_job"]
        if rows < 500
        else PROJECT["pricing"]["large_job"]
    )
    if complexity == "complex":
        lo, hi = hi, hi * 2
    mid = round((lo + hi) / 2, 2)
    return {"rows": rows, "complexity": complexity, "range": (lo, hi), "suggested": mid}


def to_csv(rows: List[Dict], fieldnames: List[str]) -> str:
    """Serialize collected rows to CSV text for delivery."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    return buf.getvalue()


def log_job(
    client: str, amount: float, recurring: bool = False, note: str = "", home=None
) -> Dict:
    return log_event(
        project=PROJECT["slug"],
        kind="recurring" if recurring else "sale",
        amount=amount,
        note=note or f"data job — {client}",
        counterparty=client,
        risk_band=PROJECT["risk_band"],
        home=home,
    )


def setup_checklist() -> List[Dict]:
    return [
        {
            "step": "Read and internalize the guards: public data only, robots.txt, no PII.",
            "gated": False,
        },
        {"step": "Test preflight() on 2-3 candidate public sites.", "gated": False},
        {
            "step": "List the service; Chauncey approves each target before quoting.",
            "gated": True,
        },
        {"step": "Deliver CSV via to_csv(); invoice; log the job.", "gated": True},
        {
            "step": "Offer weekly refresh contracts ($75/mo) to happy clients.",
            "gated": True,
        },
    ]
