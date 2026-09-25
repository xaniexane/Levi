"""DemandPulse Layer 1 — Data Ingestion Engine (original design, stdlib-only).

Ports the ingestion layer of the original ``omega_demandpulse.py``
(Hacker News, job aggregators, Reddit, Stack Overflow, GitHub, arXiv,
economic sources) with one hard constraint: the LEVI kernel is
stdlib-only, so every fetcher is rewritten on ``urllib`` + ``json`` +
``re``. No httpx, no new dependencies.

Differences from the original, deliberate and documented:
  - Reddit: the original used the PullPush API, which is unreliable/dead.
    Rewritten against the public ``www.reddit.com/.../search.json``
    endpoints with a proper User-Agent and graceful failure.
  - Jobs: the original called an internal ``omega_jobs.search_jobs``
    module. Rewritten against the keyless public APIs of Remotive and
    Arbeitnow.
  - BLS: the original listed the BLS API ("Free (registration)"). BLS v2
    series endpoints require a registration key — there is no keyless
    path — so BLS is deliberately excluded. The Census Bureau's keyless
    ACS endpoint covers the economic slot.
  - Failure contract: a dead network, a 429, a bad payload — everything
    degrades to an empty list. No fetcher ever lets an exception escape.

Labels: every ingested signal carries ``label: "OBSERVED"`` because it is
real fetched text, never invented. Downstream clustering is INFERENCE and
scored opportunities are HYPOTHESIS (see processing.py).

Advisory only: fetching public feeds reads the world; it changes nothing
and touches no money.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---- original constants, kept verbatim -------------------------------------

INDUSTRIES = [
    "Technology / SaaS",
    "Health / Wellness",
    "E-Commerce / Retail",
    "Services / Trades",
    "Education / EdTech",
    "Finance / FinTech",
    "Energy / CleanTech",
    "Media / Entertainment",
    "Real Estate / PropTech",
    "Food / Agriculture",
    "Legal / RegTech",
    "Government / Civic",
]

SIGNAL_TYPES = ["pain_point", "trend", "regulatory_shift", "tech_emergence"]
CONFIDENCE_LEVELS = ["high", "medium", "low"]
STATUSES = ["new", "watching", "pursuing", "passed"]

PAIN_PATTERNS = [
    r"i wish",
    r"frustrated with",
    r"there should be",
    r"why isn't there",
    r"looking for alternative",
    r"anyone know a tool",
    r"need a better",
]

DATA_SOURCES = [
    {
        "id": "social",
        "name": "Hacker News (Algolia)",
        "type": "sentiment",
        "cost": "Free",
    },
    {
        "id": "jobs",
        "name": "Job Aggregators (Remotive, Arbeitnow)",
        "type": "hiring_demand",
        "cost": "Free",
    },
    {
        "id": "reddit",
        "name": "Reddit (public .json)",
        "type": "pain_points",
        "cost": "Free",
    },
    {
        "id": "stackoverflow",
        "name": "Stack Overflow API",
        "type": "pain_points",
        "cost": "Free",
    },
    {
        "id": "github",
        "name": "GitHub Search API",
        "type": "tech_emergence",
        "cost": "Free",
    },
    {
        "id": "arxiv",
        "name": "arXiv Research Feed",
        "type": "tech_emergence",
        "cost": "Free",
    },
    {
        "id": "census",
        "name": "Census Bureau API (keyless ACS)",
        "type": "economic",
        "cost": "Free",
    },
    {
        "id": "news",
        "name": "Google News (RSS)",
        "type": "news",
        "cost": "Free",
    },
]
# BLS deliberately excluded: its API requires a registration key and offers
# no keyless path. This is a documented omission, not a silent one.

_INDUSTRY_KEYWORDS = {
    "ai": "Technology / SaaS",
    "software": "Technology / SaaS",
    "saas": "Technology / SaaS",
    "health": "Health / Wellness",
    "medical": "Health / Wellness",
    "fintech": "Finance / FinTech",
    "bank": "Finance / FinTech",
    "crypto": "Finance / FinTech",
    "education": "Education / EdTech",
    "learn": "Education / EdTech",
    "retail": "E-Commerce / Retail",
    "ecommerce": "E-Commerce / Retail",
    "shop": "E-Commerce / Retail",
    "real estate": "Real Estate / PropTech",
    "housing": "Real Estate / PropTech",
    "food": "Food / Agriculture",
    "agri": "Food / Agriculture",
    "legal": "Legal / RegTech",
    "compliance": "Legal / RegTech",
    "energy": "Energy / CleanTech",
    "solar": "Energy / CleanTech",
    "media": "Media / Entertainment",
    "content": "Media / Entertainment",
    "government": "Government / Civic",
    "civic": "Government / Civic",
}

_USER_AGENT = "levi-demandpulse/1.0 (+local-first demand research; stdlib urllib)"


# ---- stdlib HTTP ------------------------------------------------------------


def _http_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> Tuple[Optional[int], str]:
    """GET ``url``; return ``(status, text)``. Never raises.

    Any failure — DNS, refused connection, timeout, HTTP error, bad
    encoding — returns ``(None, "")``. Callers treat that as "source down"
    and degrade to an empty signal list.
    """
    try:
        qs = urllib.parse.urlencode(params or {})
        full = url + ("?" + qs if qs else "")
        req = urllib.request.Request(
            full, headers={"User-Agent": _USER_AGENT, **(headers or {})}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return int(resp.status), raw.decode("utf-8", errors="replace")
            except Exception:
                return int(resp.status), ""
    except Exception:
        return None, ""


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


# ---- classifiers (original logic, kept verbatim) -----------------------------


def classify_industry(text: str) -> str:
    """Keyword → one of the 12 INDUSTRIES. Defaults to Technology / SaaS."""
    text_l = (text or "").lower()
    for kw, industry in _INDUSTRY_KEYWORDS.items():
        if kw in text_l:
            return industry
    return "Technology / SaaS"


def classify_signal(text: str, source: str) -> str:
    """Pain patterns first, then source-based fallback. Original logic."""
    text_l = (text or "").lower()
    if any(re.search(p, text_l) for p in PAIN_PATTERNS):
        return "pain_point"
    if source in ("reddit", "stackoverflow"):
        return "pain_point"
    if source in ("jobs", "social"):
        return "trend"
    if source == "news":
        return "trend"
    if source in ("github", "arxiv"):
        return "tech_emergence"
    if source in ("bls", "census"):
        return "regulatory_shift"
    return "trend"


def _keywords(text: str, query: str) -> List[str]:
    return re.findall(r"[a-z0-9+#]{3,}", f"{text} {query}".lower())[:5]


# ---- fetchers (one per source; each returns [] on any failure) --------------


def fetch_hackernews(query: str) -> List[Dict[str, Any]]:
    status, text = _http_get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query, "tags": "story", "hitsPerPage": 20},
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    for hit in data.get("hits", []) or []:
        if not isinstance(hit, dict):
            continue
        title = hit.get("title", "") or ""
        if not title:
            continue
        signals.append(
            {
                "source": "social",
                "source_name": "Hacker News",
                "text": title,
                "url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "metadata": {
                    "points": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                },
            }
        )
    return signals


def _fetch_remotive(query: str) -> List[Dict[str, Any]]:
    status, text = _http_get(
        "https://remotive.com/api/remote-jobs",
        params={"search": query},
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    for job in (data.get("jobs", []) or [])[:15]:
        if not isinstance(job, dict):
            continue
        title = job.get("title", "") or ""
        company = job.get("company_name", "") or ""
        if not title:
            continue
        signals.append(
            {
                "source": "jobs",
                "source_name": "Job Aggregators",
                "text": f"Hiring surge: {title} at {company}",
                "url": job.get("url", "") or "",
                "metadata": {
                    "location": job.get("candidate_required_location"),
                    "job_type": job.get("job_type"),
                },
            }
        )
    return signals


def _fetch_arbeitnow(query: str) -> List[Dict[str, Any]]:
    status, text = _http_get(
        "https://www.arbeitnow.com/api/job-board-api",
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t]
    for job in (data.get("data", []) or [])[:40]:
        if not isinstance(job, dict):
            continue
        title = job.get("title", "") or ""
        company = job.get("company_name", "") or ""
        if not title:
            continue
        if tokens and not any(t in title.lower() for t in tokens):
            continue
        signals.append(
            {
                "source": "jobs",
                "source_name": "Job Aggregators",
                "text": f"Hiring surge: {title} at {company}",
                "url": job.get("url", "") or "",
                "metadata": {
                    "remote": job.get("remote"),
                    "location": job.get("location"),
                },
            }
        )
        if len(signals) >= 15:
            break
    return signals


def fetch_job_signals(query: str) -> List[Dict[str, Any]]:
    """Keyless public job boards (Remotive + Arbeitnow). [] on any failure."""
    return _fetch_remotive(query) + _fetch_arbeitnow(query)


def fetch_reddit_signals(query: str) -> List[Dict[str, Any]]:
    """Real Reddit pain-point signals via the public search.json endpoint.

    The original used PullPush, which is unreliable/dead; this uses
    www.reddit.com with a proper User-Agent. Reddit rate-limits
    aggressively from datacenters — any failure degrades to [].
    """
    status, text = _http_get(
        "https://www.reddit.com/r/all/search.json",
        params={
            "q": query,
            "sort": "new",
            "limit": 20,
            "t": "month",
            "restrict_sr": "false",
        },
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    children = ((data.get("data") or {}).get("children", [])) or []
    for child in children:
        post = (child or {}).get("data", {}) if isinstance(child, dict) else {}
        title = post.get("title", "") or ""
        if not title:
            continue
        signals.append(
            {
                "source": "reddit",
                "source_name": "Reddit (public .json)",
                "text": title,
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "metadata": {
                    "score": post.get("score", 0),
                    "subreddit": post.get("subreddit", ""),
                    "comments": post.get("num_comments", 0),
                },
            }
        )
    return signals


def fetch_stackoverflow_signals(query: str) -> List[Dict[str, Any]]:
    status, text = _http_get(
        "https://api.stackexchange.com/2.3/search/advanced",
        params={
            "order": "desc",
            "sort": "activity",
            "q": query,
            "site": "stackoverflow",
            "pagesize": 15,
        },
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title", "") or ""
        if not title:
            continue
        signals.append(
            {
                "source": "stackoverflow",
                "source_name": "Stack Overflow",
                "text": title,
                "url": item.get("link", "") or "",
                "metadata": {
                    "score": item.get("score", 0),
                    "answers": item.get("answer_count", 0),
                    "tags": (item.get("tags", []) or [])[:5],
                },
            }
        )
    return signals


def fetch_github_signals(query: str) -> List[Dict[str, Any]]:
    status, text = _http_get(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": 12},
        headers={"Accept": "application/vnd.github+json"},
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    data = _parse_json(text)
    if not isinstance(data, dict):
        return signals
    for repo in data.get("items", []) or []:
        if not isinstance(repo, dict):
            continue
        name = repo.get("full_name", "") or ""
        if not name:
            continue
        desc = repo.get("description") or ""
        signals.append(
            {
                "source": "github",
                "source_name": "GitHub",
                "text": f"{name}: {desc[:120]}" if desc else name,
                "url": repo.get("html_url", "") or "",
                "metadata": {
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language"),
                    "updated": (repo.get("updated_at", "") or "")[:10],
                },
            }
        )
    return signals


def fetch_arxiv_signals(query: str) -> List[Dict[str, Any]]:
    q = query.replace(" ", "+")
    status, text = _http_get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f"all:{q}",
            "max_results": 10,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        timeout=20.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200:
        return signals
    try:
        titles = re.findall(r"<title>([^<]+)</title>", text)
        ids = re.findall(r"<id>([^<]+)</id>", text)
    except re.error:
        return signals
    for title, arx_id in zip(titles[1:], ids[1:], strict=False):  # skip feed title
        title = title.strip()
        if not title:
            continue
        signals.append(
            {
                "source": "arxiv",
                "source_name": "arXiv",
                "text": title,
                "url": arx_id.strip(),
                "metadata": {"feed": "research"},
            }
        )
    return signals


def fetch_census_signals(query: str = "") -> List[Dict[str, Any]]:
    """Keyless economic signal: US median household income (ACS 5-year).

    The Census Bureau API needs no key. This is the economic slot the
    original filled with BLS/Census; BLS is excluded because it requires
    a registration key (documented above).
    """
    status, text = _http_get(
        "https://api.census.gov/data/2022/acs/acs5",
        params={"get": "NAME,B19013_001E", "for": "us:1"},
        timeout=15.0,
    )
    if status != 200:
        return []
    data = _parse_json(text)
    if not (isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list)):
        return []
    try:
        income = int(data[1][1])
    except (ValueError, TypeError, IndexError):
        return []
    return [
        {
            "source": "census",
            "source_name": "Census Bureau (ACS)",
            "text": f"US median household income ${income:,} (ACS 5-year, OBSERVED)",
            "url": "https://api.census.gov/data/2022/acs/acs5",
            "metadata": {"series": "B19013_001E", "income": income},
        }
    ]


def fetch_google_news(query: str) -> List[Dict[str, Any]]:
    """Keyless launch/funding/product news via Google News RSS.

    Powers competitor news (funding rounds, launches) and general trend
    news. One polite RSS request; a dead network, a 429, or a bad
    payload degrades to []. Never raises.
    """
    status, text = _http_get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        timeout=15.0,
    )
    signals: List[Dict[str, Any]] = []
    if status != 200 or not text:
        return signals
    try:
        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
    except re.error:
        return signals
    for item in items[:15]:
        try:
            title_m = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
            date_m = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
            src_m = re.search(r"<source[^>]*>(.*?)</source>", item, re.DOTALL)
        except re.error:
            continue
        title = (title_m.group(1).strip() if title_m else "")
        title = re.sub(r"\s+", " ", title)
        # Google News titles append " - Outlet"; keep it, it names the source.
        if not title:
            continue
        outlet = (src_m.group(1).strip() if src_m else "")
        signals.append(
            {
                "source": "news",
                "source_name": "Google News (RSS)",
                "text": title[:200],
                "url": (link_m.group(1).strip() if link_m else ""),
                "metadata": {
                    "published": (date_m.group(1).strip() if date_m else ""),
                    "outlet": outlet,
                },
            }
        )
    return signals


# Deliberate omissions (documented, not silent):
#  - Indie Hackers: no keyless stable feed or JSON endpoint — scraping its
#    JS-heavy pages would be brittle and impolite. Launch news is covered
#    by Google News RSS instead.
#  - Product Hunt direct: api.producthunt.com requires a token; the public
#    pages are JS-rendered with no stable keyless endpoint. Launch news is
#    covered by Google News RSS instead.


_FETCHERS: List[Tuple[str, Callable[[str], List[Dict[str, Any]]]]] = [
    ("Hacker News", fetch_hackernews),
    ("Job Aggregators", fetch_job_signals),
    ("Reddit", fetch_reddit_signals),
    ("Stack Overflow", fetch_stackoverflow_signals),
    ("GitHub", fetch_github_signals),
    ("arXiv", fetch_arxiv_signals),
    ("Census", fetch_census_signals),
    ("Google News", fetch_google_news),
]


def ingest_signals(
    query: str,
    focus_industries: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Layer 1 — Data Ingestion Engine (real free APIs only, stdlib HTTP).

    Returns signal dicts with ``label: "OBSERVED"`` — real fetched text.
    Never raises: a source that is down contributes nothing.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    query = query.strip()
    if focus_industries is None:
        focus_industries = list(INDUSTRIES)

    raw: List[Dict[str, Any]] = []
    for _name, fn in _FETCHERS:
        try:
            raw.extend(fn(query))
        except Exception:
            continue  # belt and suspenders: a fetcher must never escape

    signals: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "") or ""
        if not text:
            continue
        industry = classify_industry(f"{text} {query}")
        if industry not in focus_industries:
            continue
        source = item.get("source", "") or ""
        sig_type = classify_signal(text, source)
        confidence = (
            "high"
            if source in ("jobs", "social", "reddit", "stackoverflow")
            else "medium"
        )
        signals.append(
            {
                "id": uuid.uuid4().hex[:12],
                "timestamp": now,
                "source": source,
                "source_name": item.get("source_name", "") or "",
                "signal_type": sig_type,
                "industry": industry,
                "confidence": confidence,
                "label": "OBSERVED",  # real fetched text, never invented
                "summary": text[:200],
                "keywords": _keywords(text, query),
                "url": item.get("url", "") or "",
                "metadata": item.get("metadata", {}) or {},
            }
        )
    return signals
