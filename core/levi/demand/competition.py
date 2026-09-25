"""DemandPulse competitive + market intelligence and upgrade recommender.

The "competitive edge" layer: tracks named competitors, detects changes on
their public pages, maps the feature gap between DemandPulse and each rival
from what the demand module *actually does*, and proposes upgrades.

ADVISORY ONLY — hard gates, read them:
  - This module never executes a proposal, never buys anything, never moves
    money, and never takes external action beyond polite reads of public
    web pages (one request per page per run, proper User-Agent, graceful
    failure, no retries, no hammering).
  - Every proposal is labeled HYPOTHESIS. Applying anything consequential
    requires the founder's explicit word. The module cannot self-apply and
    says so on every proposal it emits.
  - Competitor facts are seeded only from honestly-known public facts.
    Each carries label OBSERVED + source + date + confidence. Anything
    uncertain is marked uncertain (verified: false). The old pitch deck's
    market claims ($4.8B TAM, 33M underserved SMBs, $2.1M ARR, $15-21M exit)
    are NOT in here — they are unverified and are never presented as facts.
  - DemandPulse's own feature column is derived ONLY from what the demand
    module code does. No invented capabilities.

Current product price anchor: $6/month subscription (founder's word,
2026-09-21). Reprice proposals reason from that anchor.

stdlib-only. Local state lives under ~/.levi/demandpulse/competitors/
(override with DEMANDPULSE_COMPETITORS_DIR or --store).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_PRICE_MONTHLY = 6.0  # founder's word, 2026-09-21 — reprice anchor
PRICE_ANCHOR_NOTE = (
    "founder-set 2026-09-21: $6/month subscription; "
    "reprice proposals reason from this anchor"
)

DEFAULT_STORE = (
    Path(os.environ.get("DEMANDPULSE_COMPETITORS_DIR", ""))
    if os.environ.get("DEMANDPULSE_COMPETITORS_DIR")
    else Path.home() / ".levi" / "demandpulse" / "competitors"
)

_UA = (
    "levi-demandpulse/1.0 (+competitive watch; one polite request per page; "
    "stdlib urllib)"
)

GATE_TEXT = (
    "ADVISORY ONLY: proposals are HYPOTHESIS and never self-apply. "
    "They execute nothing, buy nothing, and move no money. "
    "Applying anything consequential requires the founder's explicit word."
)

_DECK_CLAIMS_DISCLAIMER = (
    "The legacy pitch deck's market claims (its TAM, underserved-SMB, ARR, "
    "and exit-valuation figures) are UNVERIFIED. They are not seeded here "
    "and must never be presented as validated facts."
)

# ---------------------------------------------------------------------------
# Seeded competitor profiles — honestly-known public facts only.
# ---------------------------------------------------------------------------


def _fact(
    claim: str,
    source: str,
    confidence: str,
    verified: bool = True,
    note: str = "",
) -> Dict[str, Any]:
    return {
        "claim": claim,
        "label": "OBSERVED",
        "source": source,
        "observed": "2026-09-21",
        "confidence": confidence,  # high | medium | low
        "verified": verified,
        "note": note,
    }


SEED_PROFILES: List[Dict[str, Any]] = [
    {
        "slug": "google-trends",
        "name": "Google Trends",
        "site": "https://trends.google.com",
        "facts": [
            _fact(
                "Free to use, no account required.",
                "trends.google.com (public product)",
                "high",
            ),
            _fact(
                "Shows relative search interest (0-100 normalized) over time "
                "and by region.",
                "trends.google.com (public product)",
                "high",
            ),
            _fact(
                "Does not score business opportunities (no five-factor or "
                "equivalent demand scoring).",
                "product nature: search-interest visualization",
                "high",
            ),
            _fact(
                "No pain-point mining, industry classification, or industry "
                "heatmap features.",
                "product nature: search-interest visualization",
                "high",
            ),
        ],
        "features": {
            "trend_visualization": "yes",
            "free": "yes",
            "paid_tiers": "no",
            "public_pricing": "n/a",
            "demand_opportunity_scoring": "no",
            "pain_point_mining": "no",
            "proactive_demand_alerts": "unknown",
        },
        "pages": ["https://trends.google.com/trends"],
    },
    {
        "slug": "exploding-topics",
        "name": "Exploding Topics",
        "site": "https://explodingtopics.com",
        "facts": [
            _fact(
                "Trend-discovery product with a free email newsletter.",
                "explodingtopics.com (public product)",
                "high",
            ),
            _fact(
                "Paid 'Pro' tier exists with a trend database.",
                "explodingtopics.com (public product)",
                "high",
            ),
            _fact(
                "Pro listed around $39/month billed annually (from public "
                "memory; confirm via snapshot).",
                "public pricing page (unconfirmed)",
                "medium",
                verified=False,
                note="Run `competition track` then `competition diff` to "
                "confirm the live figure before quoting it.",
            ),
            _fact(
                "No five-factor demand-opportunity scoring; it ranks trends, "
                "not scored business opportunities.",
                "product nature: trend discovery",
                "medium",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "newsletter": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "demand_opportunity_scoring": "no",
            "pain_point_mining": "unknown",
            "proactive_demand_alerts": "unknown",
        },
        "pages": [
            "https://explodingtopics.com",
            "https://explodingtopics.com/pro",
        ],
    },
    {
        "slug": "crayon",
        "name": "Crayon",
        "site": "https://www.crayon.co",
        "facts": [
            _fact(
                "Enterprise competitive-intelligence platform.",
                "crayon.co (public product)",
                "high",
            ),
            _fact(
                "Headline capability: tracks competitors' website, product, "
                "and marketing changes.",
                "crayon.co (public product)",
                "high",
            ),
            _fact(
                "Pricing not public; sales-led / quote-based.",
                "crayon.co (public pricing page absent)",
                "high",
            ),
            _fact(
                "Built for B2B competitive intel teams, not SMB "
                "demand-opportunity scoring.",
                "product nature: enterprise CI",
                "high",
            ),
        ],
        "features": {
            "competitor_change_tracking": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://www.crayon.co"],
    },
    {
        "slug": "klue",
        "name": "Klue",
        "site": "https://klue.com",
        "facts": [
            _fact(
                "Enterprise competitive-enablement platform; battlecards for "
                "sales teams.",
                "klue.com (public product)",
                "high",
            ),
            _fact(
                "Pricing not public; quote-based.",
                "klue.com (public pricing page absent)",
                "high",
            ),
            _fact(
                "Sales-enablement focus, not demand-opportunity scoring.",
                "product nature: competitive enablement",
                "high",
            ),
        ],
        "features": {
            "battlecards_enablement": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://klue.com"],
    },
    {
        "slug": "6sense",
        "name": "6sense",
        "site": "https://6sense.com",
        "facts": [
            _fact(
                "B2B account-based marketing / buyer-intent data platform.",
                "6sense.com (public product)",
                "high",
            ),
            _fact(
                "Enterprise, quote-based pricing; no public tiers.",
                "6sense.com (public pricing page absent)",
                "high",
            ),
            _fact(
                "Intent data for sales/marketing teams, not SMB "
                "demand-opportunity scoring.",
                "product nature: ABM intent data",
                "high",
            ),
        ],
        "features": {
            "buyer_intent_data": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://6sense.com"],
    },
    {
        "slug": "cb-insights",
        "name": "CB Insights",
        "site": "https://www.cbinsights.com",
        "facts": [
            _fact(
                "Market-intelligence / research platform covering startups "
                "and markets.",
                "cbinsights.com (public product)",
                "high",
            ),
            _fact(
                "Paid; pricing not public (quote-based). Free newsletter exists.",
                "cbinsights.com (public product)",
                "high",
            ),
            _fact(
                "Research database, not a five-factor SMB demand scorer.",
                "product nature: market research",
                "medium",
            ),
        ],
        "features": {
            "market_research_db": "yes",
            "newsletter": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "partial",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "unknown",
        },
        "pages": ["https://www.cbinsights.com"],
    },
    {
        "slug": "trendwatching",
        "name": "TrendWatching",
        "site": "https://www.trendwatching.com",
        "facts": [
            _fact(
                "Trend intelligence firm publishing consumer trend reports "
                "for brands.",
                "trendwatching.com (public product)",
                "high",
            ),
            _fact(
                "Free newsletter exists; paid reports and memberships are "
                "the business.",
                "trendwatching.com (public product)",
                "high",
            ),
            _fact(
                "Pricing is quote/custom, not public self-serve tiers.",
                "trendwatching.com (no public pricing page)",
                "high",
            ),
            _fact(
                "Trend reports for brand teams, not SMB demand-opportunity "
                "scoring.",
                "product nature: trend intelligence",
                "high",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "newsletter": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://www.trendwatching.com"],
    },
    {
        "slug": "trend-hunter",
        "name": "Trend Hunter",
        "site": "https://www.trendhunter.com",
        "facts": [
            _fact(
                "Trend discovery community publishing free trend content.",
                "trendhunter.com (public product)",
                "high",
            ),
            _fact(
                "Trend Hunter PRO paid tier exists.",
                "trendhunter.com (public product)",
                "high",
            ),
            _fact(
                "PRO price not confirmed from public memory — verify via "
                "snapshot before quoting.",
                "public pricing (unconfirmed)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm the live figure before quoting it.",
            ),
            _fact(
                "Ranks trends; no five-factor demand-opportunity scoring.",
                "product nature: trend discovery",
                "medium",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "unknown",
            "demand_opportunity_scoring": "no",
            "proactive_demand_alerts": "unknown",
        },
        "pages": ["https://www.trendhunter.com"],
    },
    {
        "slug": "glimpse",
        "name": "Glimpse",
        "site": "https://meetglimpse.com",
        "facts": [
            _fact(
                "Trends analytics product; markets itself as an upgrade "
                "over Google Trends (public positioning).",
                "meetglimpse.com (public product)",
                "high",
            ),
            _fact(
                "Public pricing page exists.",
                "meetglimpse.com (public product)",
                "high",
            ),
            _fact(
                "Exact tier prices unverified — confirm via snapshot before "
                "quoting.",
                "public pricing page (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Trend trajectories, not SMB demand-opportunity scoring.",
                "product nature: trend analytics",
                "medium",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "trend_visualization": "yes",
            "free": "unknown",
            "paid_tiers": "yes",
            "public_pricing": "yes",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "yes",
        },
        "pages": ["https://meetglimpse.com", "https://meetglimpse.com/pricing"],
    },
    {
        "slug": "answerthepublic",
        "name": "AnswerThePublic",
        "site": "https://answerthepublic.com",
        "facts": [
            _fact(
                "Search-listening tool: visualizes the questions people ask "
                "around a keyword.",
                "answerthepublic.com (public product)",
                "high",
            ),
            _fact(
                "Free limited tier exists; paid Pro tiers exist.",
                "answerthepublic.com (public product)",
                "high",
            ),
            _fact(
                "Exact Pro prices unverified — confirm via snapshot before "
                "quoting.",
                "public pricing page (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Keyword questions, not scored business opportunities.",
                "product nature: search listening",
                "high",
            ),
        ],
        "features": {
            "trend_visualization": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "yes",
            "demand_opportunity_scoring": "no",
            "pain_point_mining": "partial",
            "smb_self_serve": "yes",
        },
        "pages": [
            "https://answerthepublic.com",
            "https://answerthepublic.com/pricing",
        ],
    },
    {
        "slug": "buzzsumo",
        "name": "BuzzSumo",
        "site": "https://buzzsumo.com",
        "facts": [
            _fact(
                "Content discovery and social-engagement analytics.",
                "buzzsumo.com (public product)",
                "high",
            ),
            _fact(
                "Public pricing page with paid tiers; limited free searches.",
                "buzzsumo.com (public product)",
                "high",
            ),
            _fact(
                "Exact tier prices unverified — confirm via snapshot before "
                "quoting.",
                "public pricing page (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Content performance data, not demand-opportunity scoring.",
                "product nature: content analytics",
                "high",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "yes",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "yes",
        },
        "pages": ["https://buzzsumo.com", "https://buzzsumo.com/pricing"],
    },
    {
        "slug": "sparktoro",
        "name": "SparkToro",
        "site": "https://sparktoro.com",
        "facts": [
            _fact(
                "Audience research: shows where any audience hangs out "
                "online.",
                "sparktoro.com (public product)",
                "high",
            ),
            _fact(
                "Free tier exists; paid tiers exist.",
                "sparktoro.com (public product)",
                "high",
            ),
            _fact(
                "Exact prices unverified — confirm via snapshot before "
                "quoting.",
                "public pricing page (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Audience data, not demand-opportunity scoring.",
                "product nature: audience research",
                "high",
            ),
        ],
        "features": {
            "trend_database": "partial",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "yes",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "yes",
        },
        "pages": ["https://sparktoro.com", "https://sparktoro.com/pricing"],
    },
    {
        "slug": "semrush",
        "name": "Semrush",
        "site": "https://www.semrush.com",
        "facts": [
            _fact(
                "SEO and marketing intelligence toolkit.",
                "semrush.com (public product)",
                "high",
            ),
            _fact(
                "Public pricing page; paid tiers with a limited free tier.",
                "semrush.com (public product)",
                "high",
            ),
            _fact(
                "Exact prices unverified — confirm via snapshot before "
                "quoting.",
                "public pricing page (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Marketing toolkit, not SMB demand-opportunity scoring.",
                "product nature: marketing intelligence",
                "high",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "trend_visualization": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "yes",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "yes",
        },
        "pages": ["https://www.semrush.com", "https://www.semrush.com/prices"],
    },
    {
        "slug": "similarweb",
        "name": "Similarweb",
        "site": "https://www.similarweb.com",
        "facts": [
            _fact(
                "Website traffic and market intelligence platform.",
                "similarweb.com (public product)",
                "high",
            ),
            _fact(
                "Free tier exists; paid tiers exist.",
                "similarweb.com (public product)",
                "high",
            ),
            _fact(
                "Exact prices unverified — confirm via snapshot before "
                "quoting.",
                "public product (unconfirmed figures)",
                "low",
                verified=False,
                note="Run `competition track` then `competition intel` to "
                "confirm live prices before quoting.",
            ),
            _fact(
                "Traffic analytics, not demand-opportunity scoring.",
                "product nature: traffic intelligence",
                "high",
            ),
        ],
        "features": {
            "trend_database": "yes",
            "free": "partial",
            "paid_tiers": "yes",
            "public_pricing": "unknown",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "yes",
        },
        "pages": ["https://www.similarweb.com"],
    },
    {
        "slug": "demandbase",
        "name": "Demandbase",
        "site": "https://www.demandbase.com",
        "facts": [
            _fact(
                "B2B account-based marketing platform.",
                "demandbase.com (public product)",
                "high",
            ),
            _fact(
                "Enterprise, quote-based pricing; no public tiers.",
                "demandbase.com (public pricing page absent)",
                "high",
            ),
            _fact(
                "ABM for sales/marketing teams, not SMB demand-opportunity "
                "scoring.",
                "product nature: ABM platform",
                "high",
            ),
        ],
        "features": {
            "buyer_intent_data": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://www.demandbase.com"],
    },
    {
        "slug": "bombora",
        "name": "Bombora",
        "site": "https://bombora.com",
        "facts": [
            _fact(
                "B2B buyer-intent data provider.",
                "bombora.com (public product)",
                "high",
            ),
            _fact(
                "Enterprise, quote-based pricing.",
                "bombora.com (public pricing page absent)",
                "high",
            ),
            _fact(
                "Intent data licensing, not SMB demand-opportunity scoring.",
                "product nature: intent data",
                "high",
            ),
        ],
        "features": {
            "buyer_intent_data": "yes",
            "public_pricing": "no",
            "paid_tiers": "yes",
            "free": "no",
            "demand_opportunity_scoring": "no",
            "smb_self_serve": "no",
        },
        "pages": ["https://bombora.com"],
    },
]

# ---------------------------------------------------------------------------
# DemandPulse's own features — derived ONLY from the demand module's code.
# Each maps to the file/symbol that implements it. Nothing invented.
# ---------------------------------------------------------------------------

DP_FEATURES: Dict[str, Dict[str, str]] = {
    "multi_source_ingest": {
        "name": "Multi-source signal ingestion (HN, jobs, Reddit, "
        "Stack Overflow, GitHub, arXiv, Census)",
        "evidence": "core/levi/demand/ingest.py: ingest_signals",
    },
    "pain_point_mining": {
        "name": "Pain-point mining (7 pain-language patterns)",
        "evidence": "core/levi/demand/ingest.py: PAIN_PATTERNS",
    },
    "industry_classification": {
        "name": "12-industry classifier",
        "evidence": "core/levi/demand/ingest.py: INDUSTRIES/classify_industry",
    },
    "signal_clustering": {
        "name": "Signal clustering (industry|type|keyword)",
        "evidence": "core/levi/demand/processing.py: process_signals",
    },
    "multisource_validation": {
        "name": "Multi-source validation boost",
        "evidence": "core/levi/demand/processing.py: process_signals",
    },
    "five_factor_scoring": {
        "name": "Five-factor opportunity scoring (30/25/20/15/10, threshold 75)",
        "evidence": "core/levi/demand/processing.py: score_cluster + "
        "scoring.py: DEFAULT_WEIGHTS",
    },
    "basis_required_scoring": {
        "name": "Basis-required analyst scoring (no basis = rejected)",
        "evidence": "core/levi/demand/scoring.py: FactorScore",
    },
    "industry_heatmap": {
        "name": "Industry heatmap (green/yellow/gray)",
        "evidence": "core/levi/demand/processing.py: industry_heatmap",
    },
    "proactive_alerts": {
        "name": "Proactive alerts (threshold/briefing/watch/reminder, "
        "quiet hours, dedup)",
        "evidence": "core/levi/demand/alerts.py: AlertEngine",
    },
    "ten_workflows": {
        "name": "10 scheduled workflows (incl. competition monitor)",
        "evidence": "core/levi/demand/workflows.py: WORKFLOWS",
    },
    "local_first": {
        "name": "Local-first, stdlib-only, no accounts",
        "evidence": "core/levi/demand/*: urllib/json/re only; ~/.levi store",
    },
    "zero_marginal_cost": {
        "name": "Zero marginal cost per user (no infra, keyless feeds)",
        "evidence": "architecture: local-first + free keyless public APIs",
    },
    "competitor_change_tracking": {
        "name": "Competitor public-page change tracking",
        "evidence": "core/levi/demand/competition.py: track_all",
    },
    "upgrade_recommender": {
        "name": "Evidence-backed upgrade recommender",
        "evidence": "core/levi/demand/competition.py: propose_upgrades",
    },
}

# ---------------------------------------------------------------------------
# Profile store
# ---------------------------------------------------------------------------


def store_dir(path: Optional[Path] = None) -> Path:
    """Resolve the competitor store directory."""
    if path is not None:
        return Path(path)
    return Path(DEFAULT_STORE)


def load_profiles(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load competitor profiles, seeding from SEED_PROFILES on first run.

    Never overwrites an existing profiles.json — user edits win.
    Never raises; returns [] only if the store is unreadable.
    """
    sdir = store_dir(path)
    pfile = sdir / "profiles.json"
    try:
        if pfile.exists():
            data = json.loads(pfile.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("profiles"), list):
                return data["profiles"]
            return []
        sdir.mkdir(parents=True, exist_ok=True)
        payload = {
            "seeded_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": _DECK_CLAIMS_DISCLAIMER,
            "profiles": SEED_PROFILES,
        }
        tmp = pfile.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(pfile)
        return SEED_PROFILES
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Polite public-page fetching — never raises, never hammers.
# ---------------------------------------------------------------------------


def _extract_text(html_text: str) -> str:
    """Strip scripts/styles/tags/entities; collapse whitespace."""
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html_text)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def fetch_page(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Fetch one public page. Never raises.

    Single attempt, no retry loop (no hammering). Any failure — DNS,
    timeout, HTTP error, bad payload — returns status None and records
    the failure instead of crashing.
    """
    record: Dict[str, Any] = {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "sha256": None,
        "chars": 0,
        "text": "",
        "error": "",
        "label": "OBSERVED",
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(resp.status)
        text = _extract_text(raw.decode("utf-8", errors="replace"))
        record["status"] = status
        record["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record["chars"] = len(text)
        record["text"] = text
    except Exception as exc:  # graceful degradation, never a crash
        record["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return record


def _snapshot_path(sdir: Path, slug: str, url: str) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:60]
    return sdir / "snapshots" / slug / f"{safe}.jsonl"


def snapshot_competitor(
    profile: Dict[str, Any], path: Optional[Path] = None
) -> Dict[str, Any]:
    """Snapshot one competitor's pages. Appends versioned JSONL rows.

    Keeps the newest 25 snapshots per page (prunes older). Never raises.
    """
    sdir = store_dir(path)
    slug = profile.get("slug", "unknown")
    results: List[Dict[str, Any]] = []
    for url in profile.get("pages", []) or []:
        rec = fetch_page(url)
        rec["slug"] = slug
        spath = _snapshot_path(sdir, slug, url)
        try:
            spath.parent.mkdir(parents=True, exist_ok=True)
            with spath.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            _prune(spath, keep=25)
        except Exception:
            pass
        results.append(
            {
                "url": url,
                "status": rec["status"],
                "chars": rec["chars"],
                "error": rec["error"],
            }
        )
        time.sleep(1.0)  # polite: one second between page reads
    return {"slug": slug, "pages": results}


def _prune(spath: Path, keep: int = 25) -> None:
    try:
        lines = spath.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    if len(lines) > keep:
        try:
            spath.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
        except Exception:
            pass


def track_all(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Snapshot every competitor's pages. Polite, graceful, never raises."""
    sdir = store_dir(path)
    out: List[Dict[str, Any]] = []
    for profile in load_profiles(sdir):
        try:
            out.append(snapshot_competitor(profile, sdir))
        except Exception:
            out.append({"slug": profile.get("slug"), "pages": [], "error": "failed"})
    return out


# Hyper-aggressive cadence, still polite: pages are re-fetched at most
# every COMPETITOR_RESCAN_HOURS (12h). "Hyper-aggressive" means broader
# coverage and deeper extraction per run — never more requests per page
# per run, never shorter inter-request sleeps. Getting blocked sinks the
# project; the 1s sleep and single attempt per page are the floor.
COMPETITOR_RESCAN_HOURS = 12.0


def _last_snapshot(sdir: Path, slug: str, url: str) -> Optional[Dict[str, Any]]:
    rows = _read_snapshots(sdir, slug, url)
    for row in reversed(rows):
        if row.get("status") and row.get("sha256"):
            return row
    return None


def _page_due(
    sdir: Path, slug: str, url: str, max_age_hours: float
) -> bool:
    """True when the page has no good snapshot or the newest is stale."""
    last = _last_snapshot(sdir, slug, url)
    if not last:
        return True
    try:
        fetched = datetime.fromisoformat(str(last.get("fetched_at")))
        age_h = (
            datetime.now(timezone.utc) - fetched
        ).total_seconds() / 3600.0
    except Exception:
        return True
    return age_h >= max_age_hours


def track_due(
    path: Optional[Path] = None,
    max_age_hours: float = COMPETITOR_RESCAN_HOURS,
) -> List[Dict[str, Any]]:
    """Snapshot only the competitor pages whose newest good snapshot is
    older than ``max_age_hours`` (default 12h). Fresh pages are skipped —
    the cadence is tighter than a daily full re-crawl, but no page is ever
    fetched twice in one run and the polite 1s sleep still applies.
    Never raises.
    """
    sdir = store_dir(path)
    out: List[Dict[str, Any]] = []
    for profile in load_profiles(sdir):
        slug = profile.get("slug", "unknown")
        results: List[Dict[str, Any]] = []
        skipped = 0
        for url in profile.get("pages", []) or []:
            if not _page_due(sdir, slug, url, max_age_hours):
                skipped += 1
                continue
            try:
                rec = fetch_page(url)
                rec["slug"] = slug
                spath = _snapshot_path(sdir, slug, url)
                spath.parent.mkdir(parents=True, exist_ok=True)
                with spath.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                _prune(spath, keep=25)
            except Exception:
                rec = {"url": url, "status": None, "chars": 0, "error": "failed"}
            results.append(
                {
                    "url": url,
                    "status": rec.get("status"),
                    "chars": rec.get("chars"),
                    "error": rec.get("error"),
                }
            )
            time.sleep(1.0)  # polite floor — never shortened
        out.append({"slug": slug, "pages": results, "skipped_fresh": skipped})
    return out


# ---------------------------------------------------------------------------
# Deep intel scan: prices, tactics, userbase, hiring — diffed run-over-run
# ---------------------------------------------------------------------------


def _emitted_moves_path(sdir: Path) -> Path:
    return sdir / "emitted_moves.jsonl"


def _move_key(move: Dict[str, Any]) -> str:
    canon = json.dumps(move, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _load_emitted(sdir: Path) -> set:
    seen: set = set()
    try:
        for line in _emitted_moves_path(sdir).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                seen.add(line)
    except Exception:
        pass
    return seen


def _record_emitted(sdir: Path, keys: List[str]) -> None:
    if not keys:
        return
    try:
        with _emitted_moves_path(sdir).open("a", encoding="utf-8") as fh:
            for k in keys:
                fh.write(k + "\n")
    except Exception:
        pass


def _write_last_intel(sdir: Path, summary: Dict[str, Any]) -> None:
    try:
        (sdir / "last_intel.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def last_intel_run(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Read-only: when the last intel scan ran and what it found."""
    sdir = store_dir(path)
    try:
        data = json.loads((sdir / "last_intel.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _diff_stored_intel(sdir: Path) -> List[Dict[str, Any]]:
    """Diff the latest two stored snapshots per page into OBSERVED moves.

    Pure reads — no network. Shared by scan_competitor_intel (after a
    track_due) and propose_upgrades (advisory surface stays read-only).
    """
    from levi.demand import competition_intel as _ci

    moves: List[Dict[str, Any]] = []
    for profile in load_profiles(sdir):
        slug = profile.get("slug", "?")
        name = profile.get("name", slug)
        for url in profile.get("pages", []) or []:
            rows = _read_snapshots(sdir, slug, url)
            good = [r for r in rows if r.get("status") and r.get("sha256")]
            if len(good) < 2:
                continue
            old_i = _ci.scan_page_intel(good[-2])
            new_i = _ci.scan_page_intel(good[-1])
            for mv in _ci.diff_intel(old_i, new_i):
                mv["competitor"] = name
                mv["slug"] = slug
                moves.append(mv)
    return moves


def scan_competitor_intel(
    path: Optional[Path] = None,
    max_age_hours: float = COMPETITOR_RESCAN_HOURS,
    with_news: bool = True,
) -> Dict[str, Any]:
    """One deep intel pass: due pages re-fetched, then price / tactic /
    userbase / hiring intel diffed run-over-run into OBSERVED move records.

    Also pulls keyless funding/launch news per competitor (one RSS request
    each). Moves already emitted are returned in ``moves`` but only fresh
    ones in ``new_moves`` (the emitted-moves log prevents re-emission).
    Never raises.
    """
    from levi.demand import competition_intel as _ci

    sdir = store_dir(path)
    tracked = track_due(sdir, max_age_hours=max_age_hours)
    from levi.demand import competition_intel as _ci

    moves = _diff_stored_intel(sdir)
    news: List[Dict[str, Any]] = []
    try:
        for profile in load_profiles(sdir):
            name = profile.get("name", profile.get("slug", "?"))
            slug = profile.get("slug", "?")
            if with_news:
                try:
                    for item in _ci.competitor_news(name):
                        item["competitor"] = name
                        item["slug"] = slug
                        news.append(item)
                except Exception:
                    continue
    except Exception:
        pass

    emitted = _load_emitted(sdir)
    new_moves: List[Dict[str, Any]] = []
    new_keys: List[str] = []
    for mv in moves:
        key = _move_key(mv)
        if key not in emitted:
            emitted.add(key)
            new_keys.append(key)
            new_moves.append(mv)
    _record_emitted(sdir, new_keys)

    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "competitors": len(load_profiles(sdir)),
        "moves": len(moves),
        "new_moves": len(new_moves),
        "news_items": len(news),
        "label": "OBSERVED",
    }
    _write_last_intel(sdir, summary)
    return {
        **summary,
        "moves": moves,
        "new_moves": new_moves,
        "news": news,
        "tracked": tracked,
    }


def _proposals_from_moves(moves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detected competitor moves -> review proposals, fast-laned.

    Price changes and feature launches get fast_lane=True: they surface
    first because they change what the $6/mo product is measured against.
    Still HYPOTHESIS, still never self-applying.
    """
    out: List[Dict[str, Any]] = []
    for mv in moves or []:
        kind = mv.get("kind", "change")
        fast = kind in ("price_change", "feature_launch")
        if kind == "price_change":
            title = (
                f"Respond to {mv.get('competitor')} price change: "
                f"{mv.get('tier', '')} ${mv.get('old_monthly')}/mo -> "
                f"${mv.get('new_monthly')}/mo"
            )
            basis = [
                f"Price moved between {mv.get('from')} and {mv.get('to')} "
                f"(OBSERVED via pricing-page snapshot diff).",
                "Verify on the live page before quoting — scraped text can "
                "misread promotional pricing.",
            ]
            impact = (
                "A rival repricing changes the value story the $6/mo anchor "
                "is judged against; respond deliberately, not reflexively."
            )
        elif kind == "feature_launch":
            title = f"Assess {mv.get('competitor')} launch: {mv.get('text', '')[:80]}"
            basis = [
                f"Launch language appeared between {mv.get('from')} and "
                f"{mv.get('to')} (OBSERVED via page snapshot diff).",
                f"Sample: {mv.get('text', '')[:160]}",
            ]
            impact = (
                "New rival capabilities can erase a moat or open a gap to "
                "answer; assess fit before building anything."
            )
        elif kind == "positioning_shift":
            title = f"Note {mv.get('competitor')} repositioning"
            basis = [
                f"Hero/positioning copy changed between {mv.get('from')} and "
                f"{mv.get('to')} (OBSERVED).",
                f"Was: {mv.get('old', '')[:120]} / Now: {mv.get('new', '')[:120]}",
            ]
            impact = "Repositioning signals where the rival thinks the market is going."
        elif kind == "userbase_change":
            title = (
                f"Note {mv.get('competitor')} user-base proof change: "
                f"{mv.get('metric')} {mv.get('old')} -> {mv.get('new')}"
            )
            basis = [
                f"Public proof-point changed between {mv.get('from')} and "
                f"{mv.get('to')} (OBSERVED; scraped text — verify before quoting)."
            ]
            impact = "Review-velocity / customer-count spikes mark traction worth watching."
        elif kind == "hiring_change":
            title = f"Note {mv.get('competitor')} hiring change: {mv.get('old')} -> {mv.get('new')}"
            basis = [
                f"Open-role mentions changed between {mv.get('from')} and "
                f"{mv.get('to')} (OBSERVED on their jobs/careers page)."
            ]
            impact = "Hiring shows where the rival is investing next."
        else:
            title = f"Review {mv.get('competitor')} move ({kind})"
            basis = [f"Move observed at {mv.get('to')} (OBSERVED)."]
            impact = "Early awareness of rival motion."
        p = _proposal(
            "change",
            title,
            basis,
            impact,
            "medium" if fast else "low",
            "Page churn is often cosmetic; confirm the substance first — "
            "never reprice on noise.",
        )
        p["fast_lane"] = fast
        out.append(p)
    return out


def _read_snapshots(sdir: Path, slug: str, url: str) -> List[Dict[str, Any]]:
    spath = _snapshot_path(sdir, slug, url)
    rows: List[Dict[str, Any]] = []
    try:
        for line in spath.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        pass
    return rows


def diff_snapshots(
    old: Dict[str, Any], new: Dict[str, Any], sample_lines: int = 12
) -> Dict[str, Any]:
    """Diff two snapshots. Pure function; never raises."""
    try:
        old_lines = (old.get("text") or "").splitlines() or [old.get("text") or ""]
        new_lines = (new.get("text") or "").splitlines() or [new.get("text") or ""]
        if not old_lines:
            old_lines = [""]
        if not new_lines:
            new_lines = [""]
        diff = list(difflib.unified_diff(old_lines, new_lines, n=0, lineterm=""))
        added = [
            ln[1:] for ln in diff if ln.startswith("+") and not ln.startswith("+++")
        ]
        removed = [
            ln[1:] for ln in diff if ln.startswith("-") and not ln.startswith("---")
        ]
        changed = old.get("sha256") != new.get("sha256")
        return {
            "changed": changed,
            "added": len(added),
            "removed": len(removed),
            "sample": (added + removed)[:sample_lines],
            "from": old.get("fetched_at"),
            "to": new.get("fetched_at"),
            "label": "OBSERVED",
        }
    except Exception:
        return {
            "changed": False,
            "added": 0,
            "removed": 0,
            "sample": [],
            "from": None,
            "to": None,
            "label": "OBSERVED",
            "error": "diff failed",
        }


def check_changes(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Diff the latest two snapshots per page. Returns change records.

    Only reports pages where both snapshots exist and the hash differs.
    Never raises.
    """
    sdir = store_dir(path)
    changes: List[Dict[str, Any]] = []
    for profile in load_profiles(sdir):
        slug = profile.get("slug", "?")
        for url in profile.get("pages", []) or []:
            rows = _read_snapshots(sdir, slug, url)
            if len(rows) < 2:
                continue
            old, new = rows[-2], rows[-1]
            if not old.get("sha256") or not new.get("sha256"):
                continue  # fetch failures are not "changes"
            d = diff_snapshots(old, new)
            if d["changed"]:
                changes.append(
                    {
                        "competitor": profile.get("name", slug),
                        "slug": slug,
                        "url": url,
                        **d,
                    }
                )
    return changes


# ---------------------------------------------------------------------------
# Gap analysis — feature matrix, DemandPulse column from code only.
# ---------------------------------------------------------------------------


def feature_matrix(
    path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Build the feature matrix: rows of {feature, demandpulse, rivals...}.

    DemandPulse cells come from DP_FEATURES (code-derived). Rival cells come
    from seeded profile facts; "unknown" where not honestly known.
    """
    profiles = load_profiles(path)
    feature_keys: List[str] = list(DP_FEATURES.keys())
    for p in profiles:
        for key in (p.get("features") or {}).keys():
            if key not in feature_keys:
                feature_keys.append(key)

    pretty = {
        "trend_visualization": "Trend visualization",
        "trend_database": "Trend database",
        "newsletter": "Newsletter",
        "buyer_intent_data": "Buyer-intent data",
        "battlecards_enablement": "Battlecards / sales enablement",
        "market_research_db": "Market research database",
        "free": "Free tier",
        "paid_tiers": "Paid tiers",
        "public_pricing": "Public pricing",
        "smb_self_serve": "SMB self-serve",
        "proactive_demand_alerts": "Proactive demand alerts",
    }

    rows: List[Dict[str, Any]] = []
    for key in feature_keys:
        dp_info = DP_FEATURES.get(key)
        row: Dict[str, Any] = {
            "feature": key,
            "label": (
                dp_info["name"] if dp_info else pretty.get(key, key.replace("_", " "))
            ),
            "demandpulse": "yes" if dp_info else "no",
            "demandpulse_evidence": dp_info["evidence"] if dp_info else "",
        }
        for p in profiles:
            row[p["slug"]] = (p.get("features") or {}).get(key, "unknown")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Upgrade recommender — proposals are HYPOTHESIS, never self-applying.
# ---------------------------------------------------------------------------


def _proposal(
    kind: str,
    title: str,
    basis: List[str],
    expected_impact: str,
    confidence: str,
    risk: str,
) -> Dict[str, Any]:
    assert kind in ("add", "change", "remove", "reprice")
    assert confidence in ("high", "medium", "low")
    return {
        "kind": kind,
        "title": title,
        "basis": basis,
        "expected_impact": expected_impact,
        "confidence": confidence,
        "risk": risk,
        "label": "HYPOTHESIS",
        "advisory_only": True,
        "self_applies": False,
        "requires": "founder's explicit word",
        "price_anchor": f"${CURRENT_PRICE_MONTHLY:.0f}/month ({PRICE_ANCHOR_NOTE})"
        if kind == "reprice"
        else "",
    }


# Business-model attributes: honest to show in the matrix, never something
# to "copy" via an add-proposal. DemandPulse IS the $6/mo product.
_NON_FEATURE_KEYS = {"free", "paid_tiers", "public_pricing", "smb_self_serve"}


def _proposals_from_gaps(
    matrix: List[Dict[str, Any]], profiles: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Where a rival honestly does something we don't → consider adding."""
    out: List[Dict[str, Any]] = []
    by_slug = {p["slug"]: p for p in profiles}
    for row in matrix:
        if row["demandpulse"] != "no":
            continue
        if row["feature"] in _NON_FEATURE_KEYS:
            continue  # business-model facts, not copyable features
        holders = [slug for slug in by_slug if row.get(slug) == "yes"]
        if not holders:
            continue
        names = ", ".join(by_slug[s]["name"] for s in holders)
        feature = row["label"]
        if row["feature"] == "newsletter":
            out.append(
                _proposal(
                    "add",
                    "Free demand-digest newsletter as an acquisition channel",
                    [
                        f"Rivals with newsletters (OBSERVED): {names}.",
                        "DemandPulse already curates digests in-code "
                        "(feed/digest surface); repackaging costs ~$0.",
                    ],
                    "Top-of-funnel awareness for the $6/mo product; "
                    "newsletter readers convert to trials.",
                    "low",
                    "Time cost to write it; low direct revenue attribution.",
                )
            )
        elif row["feature"] == "trend_visualization":
            out.append(
                _proposal(
                    "add",
                    "Lightweight trend-sparkline context on opportunities",
                    [
                        f"Google Trends owns the 'see the curve' habit "
                        f"(OBSERVED: {names}).",
                        "DemandPulse scores opportunities but shows no "
                        "time-shape; users cross-check elsewhere today.",
                    ],
                    "Keeps users inside DemandPulse when validating a "
                    "score; narrows the 'just check Trends' escape hatch.",
                    "low",
                    "Scope creep toward charting; must stay stdlib-simple.",
                )
            )
        else:
            out.append(
                _proposal(
                    "add",
                    f"Evaluate parity on: {feature}",
                    [
                        f"Rivals offering it (OBSERVED): {names}.",
                        "DemandPulse has no equivalent in-code.",
                    ],
                    "Closes a named competitive gap.",
                    "low",
                    "May not fit the local-first, useful-silence positioning; "
                    "validate demand first.",
                )
            )
    return out


def _proposals_from_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detected rival page changes → review proposal. Never auto-reacts."""
    out: List[Dict[str, Any]] = []
    for ch in changes:
        out.append(
            _proposal(
                "change",
                f"Review {ch['competitor']} page change ({ch['url']})",
                [
                    f"Page changed between {ch['from']} and {ch['to']} "
                    f"(OBSERVED via snapshot diff: +{ch['added']}/"
                    f"-{ch['removed']} text segments).",
                    "Sample: "
                    + (" | ".join(ch["sample"][:3]) if ch["sample"] else "(empty)"),
                ],
                "Catches rival pricing/feature moves early enough to "
                "respond on the $6/mo anchor deliberately.",
                "medium",
                "Page churn is often cosmetic; do not reprice on noise — "
                "confirm the substance first.",
            )
        )
    return out


def _proposals_from_heatmap(heatmap: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Heating industries → positioning suggestions (INFERENCE)."""
    out: List[Dict[str, Any]] = []
    hot = [
        (ind, cell)
        for ind, cell in (heatmap or {}).items()
        if isinstance(cell, dict) and cell.get("heat") in ("green", "yellow")
    ]
    hot.sort(key=lambda kv: (kv[1]["heat"] != "green", -(kv[1].get("score") or 0)))
    for ind, cell in hot[:3]:
        top = cell.get("top") or "top opportunity"
        out.append(
            _proposal(
                "change",
                f"Aim messaging at heating industry: {ind} "
                f"({cell['heat']}, score {cell.get('score')})",
                [
                    f"Industry heatmap from the last scan (INFERENCE): "
                    f"{ind} is {cell['heat']} with "
                    f"{cell.get('count')} scored opportunities; "
                    f"top: {top}.",
                ],
                "Marketing and onboarding speak to where demand is "
                "demonstrably heating, not where we guess.",
                "low",
                "Heatmap is count-derived heuristic, not market truth; "
                "a hot cluster can be noise.",
            )
        )
    return out


def _pricing_proposals() -> List[Dict[str, Any]]:
    """Reprice proposals, reasoned from the $6/mo founder anchor."""
    anchor = CURRENT_PRICE_MONTHLY
    annual = round(anchor * 10, 2)  # ~2 months free
    return [
        _proposal(
            "reprice",
            f"Add annual option at ${annual:.0f}/yr alongside ${anchor:.0f}/mo",
            [
                f"Anchor: ${anchor:.0f}/mo = ${anchor * 12:.0f}/yr "
                f"(founder's word 2026-09-21).",
                f"${annual:.0f}/yr trades ~17% discount for upfront cash "
                f"and churn reduction.",
                "Rival Exploding Topics Pro is ~$39/mo (unverified); "
                "annual keeps us ~6x cheaper per year while lifting "
                "cash up front.",
            ],
            "Higher cash collection per buyer; fewer monthly cancellations.",
            "low",
            "Monthly buyers may downgrade to annual, lowering ARPU; "
            "only offer if retention data supports it.",
        ),
        _proposal(
            "reprice",
            "Hold the $6/mo anchor; do not chase rival tiers",
            [
                f"Anchor: ${anchor:.0f}/mo (founder's word 2026-09-21).",
                "Rivals sit at ~$39/mo (Exploding Topics Pro, unverified) "
                "to quote-based enterprise; our edge is 'way less'.",
                "Zero marginal cost means $6/mo is ~100% margin minus "
                "processing — no cost pressure to raise.",
            ],
            "Protects the undercut story: 'their month costs more than our year'.",
            "medium",
            "Leaves money on the table if willingness-to-pay is higher; "
            "test via annual uptake first.",
        ),
    ]


def _remove_proposals() -> List[Dict[str, Any]]:
    """Removals need usage evidence. We have none — say so honestly."""
    return [
        _proposal(
            "remove",
            "No removals recommended yet — insufficient usage evidence",
            [
                "Removals (features, tiers, workflows) require observed "
                "usage or cost data; the module is new and ships no "
                "telemetry.",
                "Nothing in-code is currently cost-bearing (local-first, "
                "keyless feeds).",
            ],
            "Avoids cutting something load-bearing on a hunch.",
            "high",
            "Dead weight can accumulate; revisit once usage evidence exists.",
        )
    ]


def target_industries(heatmap: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Suggest target industries from the heatmap. Labeled INFERENCE.

    Consumes processing.industry_heatmap output (or a scan's 'heatmap').
    Returns [] with a note when no scan data exists.
    """
    if not heatmap:
        return {
            "targets": [],
            "label": "INFERENCE",
            "note": "no scan data — run a demand scan first, then re-run",
        }
    ranked: List[Dict[str, Any]] = []
    for industry, cell in heatmap.items():
        if not isinstance(cell, dict):
            continue
        if cell.get("heat") in ("green", "yellow") and (cell.get("count") or 0) > 0:
            ranked.append(
                {
                    "industry": industry,
                    "heat": cell["heat"],
                    "score": cell.get("score"),
                    "opportunities": cell.get("count"),
                    "top_opportunity": cell.get("top"),
                    "label": "INFERENCE",
                }
            )
    ranked.sort(key=lambda r: (r["heat"] != "green", -(r["score"] or 0)))
    return {
        "targets": ranked,
        "label": "INFERENCE",
        "note": "heat = count-derived heuristic from the last scan, not market truth",
    }


def propose_upgrades(
    path: Optional[Path] = None,
    heatmap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the full advisory package. Read-only; never self-applies.

    Pulls the last scan's heatmap automatically when heatmap is None
    (best-effort; absent scan just means no heat proposals).
    """
    sdir = store_dir(path)
    profiles = load_profiles(sdir)
    matrix = feature_matrix(sdir)
    changes = check_changes(sdir)

    if heatmap is None:
        try:
            from levi.demand.processing import load_last_scan

            scan = load_last_scan()
            heatmap = (scan or {}).get("heatmap")
        except Exception:
            heatmap = None

    proposals: List[Dict[str, Any]] = []
    proposals.extend(_proposals_from_gaps(matrix, profiles))
    proposals.extend(_proposals_from_changes(changes))
    try:
        moves = _diff_stored_intel(sdir)
        proposals.extend(_proposals_from_moves(moves))
        moves_observed = len(moves)
    except Exception:
        moves_observed = 0
    proposals.extend(_proposals_from_heatmap(heatmap or {}))
    proposals.extend(_pricing_proposals())
    proposals.extend(_remove_proposals())

    # Moats: things we do that no tracked rival honestly does.
    rival_slugs = [p["slug"] for p in profiles]
    moats: List[Dict[str, Any]] = []
    for row in matrix:
        if row["demandpulse"] != "yes":
            continue
        rival_states = {row.get(s, "unknown") for s in rival_slugs}
        if rival_states <= {"no", "unknown"}:
            moats.append(
                {
                    "feature": row["label"],
                    "evidence": row["demandpulse_evidence"],
                    "note": "No tracked rival honestly offers this — "
                    "lead with it in positioning.",
                    "label": "INFERENCE",
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price_anchor_monthly": CURRENT_PRICE_MONTHLY,
        "proposals": proposals,
        "moats": moats,
        "targets": target_industries(heatmap),
        "changes_observed": len(changes),
        "moves_observed": moves_observed,
        "gate": GATE_TEXT,
    }


# ---------------------------------------------------------------------------
# CLI — read-only advisory surface (+ local snapshot writes on `track`).
# ---------------------------------------------------------------------------


def _render_matrix(matrix: List[Dict[str, Any]], profiles: List[Dict[str, Any]]) -> str:
    slugs = [p["slug"] for p in profiles]
    head = ["feature", "demandpulse"] + slugs
    widths = {h: len(h) for h in head}
    body = []
    for row in matrix:
        cells = [row["label"][:42], row["demandpulse"]] + [
            str(row.get(s, "?")) for s in slugs
        ]
        body.append(cells)
        for h, c in zip(head, cells, strict=True):
            widths[h] = max(widths[h], len(c))
    lines = [" | ".join(h.ljust(widths[h]) for h in head)]
    lines.append("-+-".join("-" * widths[h] for h in head))
    for cells in body:
        lines.append(
            " | ".join(c.ljust(widths[h]) for h, c in zip(head, cells, strict=True))
        )
    lines.append("")
    lines.append("demandpulse column: derived from the demand module's code only.")
    lines.append("'unknown' = not honestly known; never guessed.")
    return "\n".join(lines)


def _render_proposals(pkg: Dict[str, Any]) -> str:
    lines = [
        f"Upgrade proposals (generated {pkg['generated_at']})",
        f"price anchor: ${pkg['price_anchor_monthly']:.0f}/month",
        "",
    ]
    for i, p in enumerate(pkg["proposals"], 1):
        fast = " FAST-LANE" if p.get("fast_lane") else ""
        lines.append(f"{i}. [{p['kind']}{fast}] {p['title']}  ({p['label']})")
        lines.append(f"   confidence: {p['confidence']} | risk: {p['risk']}")
        for b in p["basis"]:
            lines.append(f"   - {b}")
        if p.get("price_anchor"):
            lines.append(f"   anchor: {p['price_anchor']}")
        lines.append("")
    lines.append("Moats (we do this; no tracked rival honestly does):")
    for m in pkg["moats"]:
        lines.append(f"  + {m['feature']} [{m['label']}]")
    lines.append("")
    t = pkg["targets"]
    lines.append(f"Target industries [{t['label']}]: {t['note']}")
    for tgt in t["targets"]:
        lines.append(
            f"  * {tgt['industry']} ({tgt['heat']}, score {tgt['score']}, "
            f"{tgt['opportunities']} opps)"
        )
    lines.append("")
    lines.append(f"GATE: {pkg['gate']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.demand competition",
        description="DemandPulse competitive edge — advisory only. "
        "track: snapshot rival pages. diff: show page changes. "
        "intel: deep scan (prices/tactics/userbase/hiring/news). "
        "gaps: feature matrix. propose: upgrade proposals.",
    )
    ap.add_argument(
        "command",
        choices=("track", "diff", "intel", "gaps", "propose"),
        help="advisory action",
    )
    ap.add_argument(
        "--due-only",
        action="store_true",
        help="track: only re-fetch pages older than the rescan interval "
        f"({COMPETITOR_RESCAN_HOURS:.0f}h); skip fresh pages",
    )
    ap.add_argument(
        "--no-news",
        action="store_true",
        help="intel: skip the per-competitor news RSS reads",
    )
    ap.add_argument(
        "--store",
        default=None,
        help="competitor store dir (default ~/.levi/demandpulse/competitors)",
    )
    args = ap.parse_args(argv)
    sdir = Path(args.store) if args.store else None

    if args.command == "track":
        results = (
            track_due(sdir) if args.due_only else track_all(sdir)
        )
        for r in results:
            skipped = r.get("skipped_fresh", 0)
            extra = f" (skipped {skipped} fresh)" if skipped else ""
            print(f"[{r['slug']}]{extra}")
            for pg in r["pages"]:
                state = (
                    f"status={pg['status']} chars={pg['chars']}"
                    if pg["status"]
                    else f"FAILED: {pg['error']}"
                )
                print(f"  {pg['url']} -> {state}")
        return 0

    if args.command == "intel":
        from levi.demand import competition_intel as _ci

        intel = scan_competitor_intel(sdir, with_news=not args.no_news)
        print(
            f"Intel scan {intel['ran_at']}: "
            f"{intel['competitors']} competitors, "
            f"{intel['moves']} moves ({intel['new_moves']} new), "
            f"{intel['news_items']} news items  (all OBSERVED)"
        )
        for mv in intel["new_moves"]:
            print(f"  NEW [{mv['kind']}] {_ci.move_text(mv, mv.get('competitor', '?'))}")
        if intel["news"]:
            print("  News:")
            for n in intel["news"][:10]:
                print(
                    f"    [{n.get('competitor')}] {n.get('headline', '')[:100]} "
                    f"({n.get('outlet', '')})"
                )
        return 0

    if args.command == "diff":
        changes = check_changes(sdir)
        if not changes:
            print("No page changes detected across tracked snapshots.")
            return 0
        for ch in changes:
            print(f"[{ch['competitor']}] {ch['url']}  ({ch['label']})")
            print(
                f"  {ch['from']} -> {ch['to']} "
                f"(+{ch['added']}/-{ch['removed']} segments)"
            )
            for line in ch["sample"][:6]:
                print(f"    {line[:120]}")
        return 0

    if args.command == "gaps":
        profiles = load_profiles(sdir)
        print(_render_matrix(feature_matrix(sdir), profiles))
        return 0

    if args.command == "propose":
        print(_render_proposals(propose_upgrades(sdir)))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
