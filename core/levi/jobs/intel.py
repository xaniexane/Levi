"""LEVI job organ — ENGINE 4 / INTEL. Target-company research and exclusion.

Intel keeps three things: the company intel table (industry, size,
felony-friendly, remote policy, watchlist), the blacklist (hard/soft
exclusions by company or role), and the restrictions/filters table
(hard/soft constraints such as "no valid driver license").

Nothing here touches the network. Enrichment is local: what the profile
and the warehouse already know. Anything unknown is reported as unknown,
never invented.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .store import Warehouse

_HARD = "hard"


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def check_blacklist(
    warehouse: Warehouse, company: str = "", role: str = ""
) -> Tuple[bool, str]:
    """True + reason if the company or role is actively blacklisted."""
    company_n, role_n = _norm(company), _norm(role)
    for entry in warehouse.list_rows("blacklist"):
        if _norm(entry.get("active")) not in ("y", "yes", "true", "1", "active"):
            continue
        etype, name = _norm(entry.get("entry_type")), _norm(entry.get("name"))
        reason = str(entry.get("reason") or "blacklisted")
        if etype == "company" and name and name in company_n:
            return True, f"company blacklisted: {reason}"
        if etype == "role" and name and (name in role_n or name in company_n):
            return True, f"role blacklisted: {reason}"
        if etype == "board" and name and name in company_n:
            return True, f"board blacklisted: {reason}"
    return False, ""


def check_restrictions(
    warehouse: Warehouse, listing: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Return active restrictions that fire against this listing.

    Hard restrictions are disqualifying; soft ones are warnings. A
    restriction fires when its detail keywords appear in the listing
    text (title + company + notes + pay/location fields). Matching is
    conservative substring matching over normalized text — reported as
    a candidate hit, never as certainty.
    """
    text = " ".join(
        str(listing.get(k) or "")
        for k in ("job_title", "company", "pay_range", "location_remote", "notes")
    ).lower()
    hits: List[Dict[str, str]] = []
    for entry in warehouse.list_rows("restrictions_filters"):
        if _norm(entry.get("active")) not in ("y", "yes", "true", "1", "active"):
            continue
        detail = str(entry.get("restriction_detail") or "")
        if not detail:
            continue
        keywords = [w for w in detail.lower().replace("/", " ").split() if len(w) > 3]
        if any(k in text for k in keywords):
            hits.append(
                {
                    "type": str(entry.get("restriction_type") or ""),
                    "detail": detail,
                    "severity": str(entry.get("severity") or "soft").lower(),
                    "reason": str(entry.get("reason") or ""),
                }
            )
    return hits


def enrich_listing(warehouse: Warehouse, listing: Dict[str, Any]) -> Dict[str, Any]:
    """Attach known company intel to a listing. Unknown companies get an
    explicit ``intel: null`` — the engine reports the gap, never a guess."""
    company_n = _norm(listing.get("company"))
    intel: Optional[Dict[str, Any]] = None
    for row in warehouse.list_rows("company_intel"):
        if _norm(row.get("company_name")) == company_n and company_n:
            intel = row
            break
    enriched = dict(listing)
    enriched["intel"] = intel
    enriched["on_watchlist"] = bool(intel) and _norm(intel.get("watchlist")) in (
        "y",
        "yes",
        "true",
        "1",
    )
    return enriched


def add_company(
    warehouse: Warehouse, company_name: str, **fields: Any
) -> Dict[str, Any]:
    if not company_name or not company_name.strip():
        raise ValueError("company_name is required")
    existing = [
        r
        for r in warehouse.list_rows("company_intel")
        if _norm(r.get("company_name")) == _norm(company_name)
    ]
    if existing:
        return warehouse.update_row("company_intel", existing[0]["id"], fields)
    row = {"company_name": company_name.strip()}
    row.update(fields)
    return warehouse.add_row("company_intel", row)


def add_blacklist(
    warehouse: Warehouse,
    entry_type: str,
    name: str,
    reason: str = "",
    severity: str = "hard",
) -> Dict[str, Any]:
    if entry_type.lower() not in ("company", "role", "board"):
        raise ValueError("entry_type must be company, role, or board")
    if severity.lower() not in ("hard", "soft"):
        raise ValueError("severity must be hard or soft")
    return warehouse.add_row(
        "blacklist",
        {
            "entry_type": entry_type.lower(),
            "name": name.strip(),
            "reason": reason,
            "severity": severity.lower(),
            "active": "Y",
        },
    )


def add_restriction(
    warehouse: Warehouse,
    restriction_type: str,
    restriction_detail: str,
    severity: str = "hard",
    reason: str = "",
) -> Dict[str, Any]:
    if severity.lower() not in ("hard", "soft"):
        raise ValueError("severity must be hard or soft")
    return warehouse.add_row(
        "restrictions_filters",
        {
            "restriction_type": restriction_type,
            "restriction_detail": restriction_detail,
            "severity": severity.lower(),
            "reason": reason,
            "active": "Y",
        },
    )


def watchlist(warehouse: Warehouse) -> List[Dict[str, Any]]:
    return [
        r
        for r in warehouse.list_rows("company_intel")
        if _norm(r.get("watchlist")) in ("y", "yes", "true", "1")
    ]
