"""The tailored-team offer: Site Lift analysis + installed crew, as one
offer.

Consumes a Site Lift report (``levi.services.site_lift.LiftReport`` or
its dict/JSON form) and proposes the matching crew: every failed
*measured* check maps to a crew need; uncovered needs join the team's
needs list; the suggested add-on pack follows the business type.

ADAPTER SEAM: this module accepts a real LiftReport, a dict with the
same shape (report_id, site, rounds[] -> checks[]), or a JSON string.
``fixture_report()`` builds a deterministic fixture for tests. Any
check this module cannot map is reported in ``unmapped`` — never
silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .product import LegionError
from .team import (
    NEED_TO_CATEGORY,
    BusinessProfile,
    Team,
    assemble_team,
)

# failed measured check -> crew need. Goals come from the five lift
# goals (bring, retain, intrigue, income, feature); the crew covers the
# gaps the site can't close on its own.
CHECK_TO_NEED: Dict[str, str] = {
    "f-contact": "contact",
    "f-cta": "contact",
    "f-title": "contact",      # findability -> the face answers
    "t-booking": "booking",
    "t-pricing": "pricing",
    "t-proof": "reviews",
    "t-gallery": "gallery",
    "t-faq": "faq",
    "t-social": "social",
    "t-analytics": "insights",
    "c-goal-income": "pricing",
    "c-goal-bring": "social",
    "c-goal-retain": "contact",
    "c-goal-intrigue": "gallery",
    "c-goal-feature": "insights",
}

# business-type hints read off the report's site text, in priority
# order. First hint wins; nothing matches -> "generic".
_TYPE_HINTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("restaurant", ("restaurant", "menu", "cuisine", "dining", "cafe", "pizza", "taco")),
    ("salon", ("salon", "barber", "stylist", "hair", "nails", "spa")),
    ("shop", ("shop", "store", "boutique", "retail", "merch")),
)


def _normalize_report(
    report: Union[Any, Mapping[str, Any], str]
) -> Dict[str, Any]:
    """ADAPTER: accept a LiftReport, a mapping, or a JSON string."""
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except json.JSONDecodeError as exc:
            raise LegionError(f"sitelift adapter: not JSON: {exc}")
    if hasattr(report, "to_dict"):
        report = report.to_dict()
    if not isinstance(report, Mapping):
        raise LegionError(
            "sitelift adapter: expected LiftReport, mapping, or JSON; "
            f"got {type(report).__name__}"
        )
    data = dict(report)
    if "report_id" not in data or "rounds" not in data:
        raise LegionError(
            "sitelift adapter: report lacks report_id/rounds — "
            "not a Site Lift report"
        )
    return data


def failed_checks(report: Union[Any, Mapping[str, Any], str]) -> List[Dict[str, Any]]:
    """List every failed *measured* check in the report.

    Attested checks are the owner's word, not gaps — only measured
    failures drive crew selection. Each entry carries check_id, label,
    round, and evidence.
    """
    data = _normalize_report(report)
    out: List[Dict[str, Any]] = []
    for rnd in data.get("rounds") or []:
        for chk in (rnd.get("checks") or []):
            if chk.get("kind") != "measured":
                continue
            if not chk.get("passed", False):
                out.append(
                    {
                        "check_id": chk.get("check_id", "?"),
                        "label": chk.get("label", ""),
                        "round": rnd.get("round_id", ""),
                        "evidence": chk.get("evidence", ""),
                    }
                )
    return out


def detect_business_type(report: Union[Any, Mapping[str, Any], str]) -> str:
    """Guess the business type from site text inside the report.

    Site Lift reports carry no business-type field, so this is a hint
    reader over the site/label text — honest about being a guess, never
    asserted. Returns restaurant|salon|shop|generic.
    """
    data = _normalize_report(report)
    blob_parts = [str(data.get("site", ""))]
    for rnd in data.get("rounds") or []:
        for chk in (rnd.get("checks") or []):
            blob_parts.append(str(chk.get("label", "")))
            blob_parts.append(str(chk.get("evidence", "")))
    blob = " ".join(blob_parts).lower()
    for btype, hints in _TYPE_HINTS:
        if any(h in blob for h in hints):
            return btype
    return "generic"


def propose_team(
    report: Union[Any, Mapping[str, Any], str],
    *,
    business_name: str = "",
    business_type: Optional[str] = None,
    size: str = "small",
) -> Dict[str, Any]:
    """The tailored-team offer: LiftReport -> proposed Legion crew.

    Returns a proposal dict: report_id, failed_checks, gaps mapped to
    crew needs (plus unmapped ones, never dropped), the detected or
    supplied business type, the suggested pack, and the assembled Team.
    """
    data = _normalize_report(report)
    fails = failed_checks(data)
    gaps: List[Dict[str, str]] = []
    unmapped: List[Dict[str, Any]] = []
    for fc in fails:
        cid = fc["check_id"]
        base = cid.split(":")[-1]  # crown regressions are "c-reg:<id>"
        need = CHECK_TO_NEED.get(cid) or CHECK_TO_NEED.get(base)
        entry = {"check_id": cid, "label": fc["label"], "round": fc["round"]}
        if need is None:
            unmapped.append(fc)
            entry["need"] = "UNMAPPED"
        else:
            entry["need"] = need
        gaps.append(entry)
    btype = business_type or detect_business_type(data)
    if btype not in ("restaurant", "salon", "shop", "generic"):
        raise LegionError(f"business_type must be restaurant|salon|shop|generic")
    mapped_needs = [g["need"] for g in gaps if g["need"] != "UNMAPPED"]
    profile = BusinessProfile(
        business_type=btype,
        size=size,
        needs=mapped_needs,
        business_name=business_name,
        notes=f"proposed from Site Lift report {data['report_id']}",
    )
    team = assemble_team(profile)
    return {
        "offer": "tailored team = Site Lift analysis + installed crew",
        "report_id": data["report_id"],
        "site": data.get("site", ""),
        "failed_checks": len(fails),
        "gaps": gaps,
        "unmapped": unmapped,
        "business_type": btype,
        "business_type_source": "supplied" if business_type else "detected-hint",
        "suggested_pack": btype,
        "team": team.to_dict(),
    }


def fixture_report(
    *,
    report_id: str = "lift_fixture_1",
    site: str = "example-restaurant-site",
    failed: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Deterministic Site Lift-shaped fixture for tests and demos.

    failed: check ids to mark failed; all others pass. Unknown ids
    raise LegionError so a fixture can never drift from the seam.
    """
    fails = set(failed or [])
    known = {
        "f-title", "f-meta-desc", "f-viewport", "f-h1", "f-contact",
        "f-cta", "f-alt", "f-pages", "t-booking", "t-pricing",
        "t-proof", "t-gallery", "t-faq", "t-social", "t-og",
        "t-analytics",
    }
    unknown = fails - known
    if unknown:
        raise LegionError(f"fixture: unknown check ids {sorted(unknown)}")

    def chk(cid: str, label: str) -> Dict[str, Any]:
        return {
            "check_id": cid, "label": label, "goals": ("income",),
            "kind": "measured", "passed": cid not in fails,
            "evidence": "fixture",
        }

    labels = {
        "f-title": "page has a real <title>", "f-meta-desc": "meta description",
        "f-viewport": "mobile viewport", "f-h1": "page has an h1",
        "f-contact": "a contact path exists", "f-cta": "a call-to-action",
        "f-alt": "images carry alt text", "f-pages": "site has depth",
        "t-booking": "booking / scheduling path", "t-pricing": "prices visible",
        "t-proof": "social proof", "t-gallery": "gallery / portfolio",
        "t-faq": "FAQ", "t-social": "social links",
        "t-og": "open-graph tags", "t-analytics": "analytics hook",
    }
    foundation = [cid for cid in labels if cid.startswith("f-")]
    feature = [cid for cid in labels if cid.startswith("t-")]
    return {
        "report_id": report_id,
        "site": site,
        "provider": "levi",
        "rounds": [
            {
                "round_id": "round-1", "name": "Round 1 — foundation lift",
                "kind": "lift",
                "checks": [chk(cid, labels[cid]) for cid in foundation],
            },
            {
                "round_id": "round-2", "name": "Round 2 — feature lift",
                "kind": "lift",
                "checks": [chk(cid, labels[cid]) for cid in feature],
            },
        ],
        "goal_tally": {},
        "created_at": "2026-09-18T00:00:00",
    }
