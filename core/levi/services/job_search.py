"""Job search as a first-class service offering.

The job search lives and originates in the services system. This
module wraps the existing job organ (levi.jobs) as a service
offering through the standard pipeline:

    analyze (opportunity scan) -> quote (advisor-composed)
    -> deliver (application package) -> paid -> showcase

Two paths, one pipeline:

- Chauncey's own search: provider "levi" — internal. The quote
  stage records the advisor's valuation, labeled "no charge, not
  a sale". Delivery is the application package; paid/showcase do
  not apply.
- Client service: any organ provider — the full pipeline: advisor
  quote, paid through the Cybrus money gateway only, showcase on
  verified delivery + confirmed payment.

Hard boundaries (structural, not advisory):
- This module NEVER imports levi.jobs.apply. Submission stays
  human-gated through the jobs organ's own apply gate; the
  service's deliver stage produces the package, never submits.
- No money moves except through the Cybrus money gateway. A
  quote is never a charge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from levi.services.offering import (
    ServiceError,
    ServiceOffering,
    attach_analysis,
    deliver_service,
    offer_service,
    quote_service,
    showcase_service,
)

SERVICE_TYPE = "job-search"

# NOTE: levi.jobs.apply is deliberately never imported here.
# Submission authorization lives in the job organ alone.


def _load_profile(profile_name: str, home: Optional[Path] = None):
    from levi.jobs.profiles import ProfileStore

    # ProfileStore defaults to ~/.levi/jobs; when the service is run
    # against an explicit home (tests, isolation), keep profiles
    # under that home's jobs dir.
    kwargs = {"jobs_dir": Path(home) / "jobs"} if home else {}
    store = ProfileStore(**kwargs)
    try:
        return store.get(profile_name)
    except Exception:
        raise ServiceError(
            f"no job profile {profile_name!r} in the store — "
            "create one with the jobs organ first; the service "
            "never fabricates a profile"
        )


def _scan(listings: List[Mapping[str, Any]], profile) -> List[Dict[str, Any]]:
    from levi.jobs.sourcing import normalize_listing
    from levi.jobs.triage import score_listing

    scored: List[Dict[str, Any]] = []
    for raw in listings:
        listing = normalize_listing(dict(raw))
        result = score_listing(listing, profile)
        scored.append({"listing": listing, **result})
    scored.sort(key=lambda r: r.get("score", 0), reverse=True)
    return scored


def offer_job_search(
    *,
    provider: str,
    title: str,
    profile_name: str,
    problem: str = "",
    scope: str = "",
    deadline: str = "",
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 1 — offer a job-search service.

    provider "levi" = Chauncey's own search (internal).
    Any other provider = a client service.
    """
    offering = offer_service(
        provider=provider,
        service_type=SERVICE_TYPE,
        title=title,
        problem=problem or f"job search for profile {profile_name!r}",
        scope=scope,
        deadline=deadline,
        client="self" if provider == "levi" else "",
        home=home,
    )
    mode = "internal" if provider == "levi" else "client"
    offering.log("mode", f"job-search {mode} path (profile {profile_name!r})")
    from levi.services.offering import ServiceStore

    return ServiceStore(home=home).save(offering)


def _is_internal(offering: ServiceOffering) -> bool:
    return offering.provider == "levi"


def scan_opportunities(
    offering: ServiceOffering,
    *,
    profile_name: str,
    listings: List[Mapping[str, Any]],
    top_n: int = 10,
    home: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Stage 2 — analyze: score listings against the stored profile.

    The profile is loaded from the jobs organ's store, never
    constructed here. Findings report real scores with real
    evidence; nothing is invented.
    """
    if offering.service_type != SERVICE_TYPE:
        raise ServiceError("scan_opportunities is for job-search offerings")
    profile = _load_profile(profile_name, home)
    scored = _scan(listings, profile)
    top = scored[: max(1, top_n)]
    findings = []
    for row in top:
        listing = row["listing"]
        title = str(listing.get("job_title") or "untitled")
        company = str(listing.get("company") or "unknown")
        breakdown = json.dumps(row.get("breakdown", {}), sort_keys=True)
        findings.append(
            {
                "finding": f"{title} @ {company} — score {row.get('score')}/10",
                "severity": "info",
                "evidence": f"triage score {row.get('score')}/10, breakdown {breakdown}",
                "recommendation": "consider for the application package",
            }
        )
    if not findings:
        findings = [
            {
                "finding": "no listings scored — nothing to analyze",
                "severity": "info",
                "evidence": f"{len(listings)} listings supplied, none scorable",
                "recommendation": "supply listings and re-scan",
            }
        ]
    attach_analysis(
        offering,
        subject=f"job search scan for profile {profile_name!r}",
        summary=f"{len(scored)} listings scored, top {len(top)} reported",
        findings=findings,
        confidence=None,
        sensed_from="job-search scan",
        home=home,
    )
    return top


def quote_job_search(
    offering: ServiceOffering,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    founder_commission: float = 0.0,
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 3 — quote.

    Internal (provider "levi"): records "internal — no charge, not
    a sale". No advisor call, no money anywhere.
    Client: advisor-composed quote (quote, never a charge).
    """
    if offering.service_type != SERVICE_TYPE:
        raise ServiceError("quote_job_search is for job-search offerings")
    if _is_internal(offering):
        # Internal: the pipeline stays uniform — the advisor quote is
        # a genuine valuation of the work, labeled as no-charge.
        # Valuation only: nothing is owed, nothing moves.
        from levi.services.offering import ServiceStore

        offering = quote_service(
            offering,
            giant_price=giant_price,
            strategy=strategy,
            founder_commission=founder_commission,
            home=home,
        )
        offering.log(
            "internal",
            "no charge, not a sale — quote is valuation only",
        )
        return ServiceStore(home=home).save(offering)
    return quote_service(
        offering,
        giant_price=giant_price,
        strategy=strategy,
        founder_commission=founder_commission,
        home=home,
    )


def deliver_job_search(
    offering: ServiceOffering,
    *,
    profile_name: str,
    listings: List[Mapping[str, Any]],
    top_n: int = 5,
    template: Optional[Mapping[str, Any]] = None,
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 4 — deliver: the application package.

    Scores listings, takes the top N, and drafts a cover letter
    for each (drafts, never submissions — unknown placeholders
    stay visible). Confidence is score-derived and labeled as
    such. Submission itself stays human-gated in the job organ;
    this function never authorizes or records a submission.
    """
    if offering.service_type != SERVICE_TYPE:
        raise ServiceError("deliver_job_search is for job-search offerings")
    from levi.jobs.prep import compose_cover_letter

    profile = _load_profile(profile_name, home)
    scored = _scan(listings, profile)[: max(1, top_n)]
    if not scored:
        raise ServiceError("nothing scorable to deliver — scan first")
    tpl = dict(template or {})
    packages = []
    for row in scored:
        listing = row["listing"]
        letter = compose_cover_letter(profile, listing, tpl)
        packages.append(
            {
                "job_title": letter["job_title"],
                "company": letter["company"],
                "score": row.get("score"),
                "cover_letter_draft": letter.get("text", ""),
                "draft": True,
            }
        )
    mean_score = sum(r.get("score", 0) for r in scored) / len(scored)
    solution = (
        f"Application package: {len(packages)} cover-letter drafts for the "
        f"top-scored matches (profile {profile_name!r}). "
        "Drafts only — submission stays human-gated in the job organ's "
        "apply gate; nothing was submitted."
    )
    evidence = [
        f"{p['job_title']} @ {p['company']}: triage {p['score']}/10, "
        f"cover-letter draft prepared (draft=True)"
        for p in packages
    ]
    return deliver_service(
        offering,
        solution=solution,
        evidence=evidence,
        confidence=round(mean_score / 10, 3),
        verification="triage-scored matches + visible-placeholder drafts; "
        "submission requires the human apply gate",
        home=home,
    )


def showcase_job_search(
    offering: ServiceOffering,
    *,
    home: Optional[Path] = None,
):
    """Stage 6 — showcase (client path only).

    Admits only PAID bounties with a Cybrus gateway receipt.
    Internal offerings are honestly refused (not paid, not a sale).
    """
    return showcase_service(offering, home=home)
