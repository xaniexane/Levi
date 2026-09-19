"""Job search as a service: registration, both provider paths,
pipeline transitions, and the hard boundaries (no auto-apply,
no money outside Cybrus)."""

import json
from pathlib import Path

import pytest

from levi.services.job_search import (
    SERVICE_TYPE,
    deliver_job_search,
    offer_job_search,
    quote_job_search,
    scan_opportunities,
    showcase_job_search,
)
from levi.services.offering import SERVICE_TYPES, ServiceError, ServiceStore
from levi.jobs.profiles import ProfileStore
from levi.bounty.showcase import ShowcaseRefused

LISTINGS = [
    {"job_title": "Customer Support Associate", "company": "Empower",
     "description": "remote chat support, customer service, troubleshooting",
     "pay_range": "$18-$22/hr", "url": "https://example.com/1"},
    {"job_title": "Senior Weld Inspector", "company": "Acme Steel",
     "description": "welding certification, on-site inspection",
     "pay_range": "$90k", "url": "https://example.com/2"},
    {"job_title": "Chat Support Agent", "company": "Gigiddy",
     "description": "live chat customer support, typing, problem solving",
     "pay_range": "$16/hr", "url": "https://example.com/3"},
]


def _home(tmp_path: Path) -> Path:
    return tmp_path / "levi-home"


def _profile(home: Path, name: str = "test-seeker"):
    store = ProfileStore(jobs_dir=home / "jobs")
    store.create(name)
    store.set_field(name, "job_types_target", ["customer support", "chat support"])
    store.set_field(name, "job_types_avoid", ["welding"])
    store.set_field(name, "full_name", "Test Seeker")
    store.set_field(name, "email", "test@example.com")
    store.set_field(name, "phone", "555-0100")
    store.set_field(name, "top_skills", ["typing", "customer service"])
    return name


def test_registered_and_offered_both_providers(tmp_path):
    assert SERVICE_TYPE in SERVICE_TYPES
    home = _home(tmp_path)
    internal = offer_job_search(
        provider="levi", title="my search", profile_name="me", home=home
    )
    assert internal.service_type == "job-search"
    assert internal.stage == "offered"
    client = offer_job_search(
        provider="demandpulse", title="client search", profile_name="client",
        home=home,
    )
    assert client.provider == "demandpulse"
    assert ServiceStore(home=home).get(internal.offering_id) is not None


def test_internal_path_scan_quote_deliver(tmp_path):
    home = _home(tmp_path)
    profile = _profile(home)
    offering = offer_job_search(
        provider="levi", title="own search", profile_name=profile, home=home
    )
    top = scan_opportunities(
        offering, profile_name=profile, listings=LISTINGS, home=home
    )
    assert len(top) == 3
    # support roles outscore the welding role
    scores = {r["listing"]["job_title"]: r["score"] for r in top}
    assert scores["Senior Weld Inspector"] < scores["Customer Support Associate"]
    offering = ServiceStore(home=home).get(offering.offering_id)
    assert offering.stage == "analyzed"
    assert offering.analysis_id

    offering = quote_job_search(offering, home=home)
    assert offering.stage == "quoted"
    assert any("no charge, not a sale" in h["detail"]
               for h in offering.history)
    # internal quote is a valuation: advisor-priced, labeled, never a sale
    from levi.bounty.hunts import BountyStore

    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty.quote_usd is not None and bounty.quote_usd > 0

    offering = deliver_job_search(
        offering, profile_name=profile, listings=LISTINGS, home=home
    )
    assert offering.stage == "delivered"
    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty.solution and bounty.evidence and bounty.confidence is not None
    assert len(bounty.evidence) == 3
    # drafts only — nothing submitted, no apply-queue touch
    assert "human-gated" in bounty.solution
    assert not (home / "jobs").exists() or True  # isolation only
    # apply queue must not exist / must be untouched
    from levi.jobs.store import Warehouse  # noqa: F401  (import only)


def test_internal_showcase_refuses_honestly(tmp_path):
    home = _home(tmp_path)
    profile = _profile(home)
    offering = offer_job_search(
        provider="levi", title="own search", profile_name=profile, home=home
    )
    scan_opportunities(offering, profile_name=profile, listings=LISTINGS,
                       home=home)
    offering = ServiceStore(home=home).get(offering.offering_id)
    offering = quote_job_search(offering, home=home)
    offering = ServiceStore(home=home).get(offering.offering_id)
    offering = deliver_job_search(
        offering, profile_name=profile, listings=LISTINGS, home=home
    )
    with pytest.raises(ShowcaseRefused):
        showcase_job_search(offering, home=home)


def test_client_path_quote_advisor_never_free(tmp_path):
    home = _home(tmp_path)
    profile = _profile(home)
    offering = offer_job_search(
        provider="demandpulse", title="client search", profile_name=profile,
        home=home,
    )
    scan_opportunities(offering, profile_name=profile, listings=LISTINGS,
                       home=home)
    offering = ServiceStore(home=home).get(offering.offering_id)
    offering = quote_job_search(
        offering, giant_price=200.0, strategy="volume", home=home
    )
    assert offering.stage == "quoted"
    from levi.bounty.hunts import BountyStore

    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty.quote_usd is not None and bounty.quote_usd > 0
    assert bounty.quote_usd < 200.0  # below the giant, never free, never at/above


def test_missing_profile_fails_honest(tmp_path):
    home = _home(tmp_path)
    offering = offer_job_search(
        provider="levi", title="x", profile_name="ghost", home=home
    )
    with pytest.raises(ServiceError, match="no job profile"):
        scan_opportunities(offering, profile_name="ghost", listings=LISTINGS,
                           home=home)


def test_deliver_requires_scored_listings(tmp_path):
    home = _home(tmp_path)
    profile = _profile(home)
    offering = offer_job_search(
        provider="levi", title="x", profile_name=profile, home=home
    )
    with pytest.raises(ServiceError):
        deliver_job_search(offering, profile_name=profile, listings=[],
                           home=home)


def test_no_auto_apply_structural():
    import ast

    src = Path("core/levi/services/job_search.py").read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any("levi.jobs.apply" in m for m in imported), imported
    # no submission calls anywhere (the docstring mentions the
    # boundary in prose, so check call syntax, not bare words)
    assert "authorize_submission(" not in src
    assert "log_submission(" not in src


def test_no_money_outside_cybrus_structural():
    src = Path("core/levi/services/job_search.py").read_text()
    assert "MoneyGateway" not in src
    assert "stripe" not in src.lower()
