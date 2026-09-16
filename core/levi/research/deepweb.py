"""Deep-web research for LEVI (stdlib-only).

The deep web, for LEVI's purposes, is the *public but unindexed* web: pages
and records no surface search engine reaches — Wayback Machine snapshots,
Common Crawl captures, sitemap.xml enumerations, RSS/Atom feeds, academic
repositories, and open public-record portals. The perpetual hunts ("everyday
hunt for food") eat here: forgotten documentation, dead project sites,
historical versions of pages, datasets nobody linked to.

Techniques (all stdlib ``urllib`` — no third-party packages):
- Wayback Machine CDX API + availability API (web.archive.org)
- Common Crawl index API (index.commoncrawl.org) — capture *metadata* only;
  WARC payloads are never downloaded (they are huge; the index is the map)
- sitemap.xml discovery and enumeration (via robots.txt ``Sitemap:`` lines
  and direct probing), following sitemap indexes with caps
- robots.txt-aware polite crawling: per-host rate limiting, Disallow
  honored, LEVI user-agent identification
- RSS/Atom feed discovery (``<link rel=alternate>`` + conventional paths)
  and item extraction
- arXiv API (Atom) for the academic record
- open public-record portals with unauthenticated JSON endpoints
  (data.gov CKAN catalog, SEC EDGAR public filings)

HARD BOUNDARIES (non-negotiable — enforced in code, not just documented):
- POLITE ONLY: every fetch honors robots.txt Disallow rules for our
  user-agent, rate-limits per host (default 2s between requests), and
  identifies as ``LEVI-deepweb``. A disallowed URL is never fetched.
- PUBLIC ONLY: no paywall bypass, no credentials, no login flows, no
  CAPTCHA/token solving, no defeating access controls of any kind.
- NO DARKNET: ``.onion`` addresses are refused outright (``BoundaryError``).
- NO PRIVATE-DATA HARVESTING: only published public records; nothing
  targeting individuals' non-public information.
- Fetch failures are reported honestly (``FetchError`` / recorded
  refusals) — content is never fabricated to fill a gap.

This is OSINT knowledge-gathering, defensive in spirit: LEVI learns what
the public web already published, nothing more.

Usage:
    python3 -m levi.research.deepweb survey "forgotten hypertext systems" \\
        --domain example.org
    python3 -m levi.research.deepweb boundaries
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

USER_AGENT = (
    "LEVI-deepweb/1.0 (public-source research; honors robots.txt; "
    "polite crawler)"
)

BOUNDARIES_TEXT = """\
LEVI deep-web research — hard boundaries (enforced in code):
1. Polite crawling only: robots.txt Disallow honored, per-host rate
   limiting (default 2s), LEVI user-agent identification.
2. Public sources only: no paywall bypass, no credentials, no login
   flows, no CAPTCHA/token solving, no defeating access controls.
3. No darknet: .onion addresses are refused outright.
4. No private-data harvesting: published public records only.
5. Honest failures: unreachable sources are reported, never fabricated.
"""


class BoundaryError(ValueError):
    """Refused: the request would cross a hard deep-web boundary."""


class FetchError(OSError):
    """A public source could not be fetched (network/timeout/HTTP error)."""


@dataclass
class CrawlPolicy:
    """Politeness knobs. Defaults are conservative on purpose."""

    user_agent: str = USER_AGENT
    delay_seconds: float = 2.0
    timeout: int = 15
    max_bytes: int = 2_000_000
    max_pages_per_host: int = 200
    respect_robots: bool = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Result types — every finding carries provenance.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DeepSource:
    """One deep-web finding with full provenance."""

    kind: str            # wayback|commoncrawl|sitemap|feed|arxiv|portal|page
    url: str
    title: str = ""
    summary: str = ""
    retrieved_at: str = ""
    method: str = ""     # how this source was found
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind, "url": self.url, "title": self.title,
            "summary": self.summary, "retrieved_at": self.retrieved_at,
            "method": self.method, "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeepSource":
        if not isinstance(data, dict):
            raise ValueError("DeepSource must be a mapping")
        url = str(data.get("url", "")).strip()
        if not url:
            raise ValueError("DeepSource requires a url")
        return cls(
            kind=str(data.get("kind", "page")),
            url=url,
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            retrieved_at=str(data.get("retrieved_at", "")),
            method=str(data.get("method", "")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class DeepSurvey:
    """The result of surveying a topic across deep-web sources."""

    topic: str
    created_at: str = ""
    sources: List[DeepSource] = field(default_factory=list)
    refusals: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()

    def add(self, source: DeepSource) -> None:
        self.sources.append(source)

    def refuse(self, url: str, reason: str) -> None:
        self.refusals.append({"url": url, "reason": reason,
                              "at": _now_iso()})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "created_at": self.created_at,
            "sources": [s.to_dict() for s in self.sources],
            "refusals": self.refusals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeepSurvey":
        if not isinstance(data, dict):
            raise ValueError("DeepSurvey must be a mapping")
        return cls(
            topic=str(data.get("topic", "")),
            created_at=str(data.get("created_at", "")),
            sources=[DeepSource.from_dict(s)
                     for s in data.get("sources", [])],
            refusals=[dict(r) for r in data.get("refusals", [])],
        )


# --------------------------------------------------------------------------
# HTTP choke point (tests monkeypatch ``_http_get`` — no live network).
# --------------------------------------------------------------------------

def _check_boundary(url: str) -> urllib.parse.ParseResult:
    """Parse *url* and refuse anything outside the hard boundaries."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise BoundaryError(
            "refused: only http(s) URLs are fetchable, got scheme %r"
            % parts.scheme)
    host = (parts.hostname or "").lower()
    if not host:
        raise BoundaryError("refused: URL has no host: %r" % url)
    if host == "localhost" or host.startswith("127.") or host == "::1":
        raise BoundaryError("refused: loopback addresses are not targets")
    if host.endswith(".onion"):
        raise BoundaryError(
            "refused: .onion (darknet) is outside the hard boundaries")
    if parts.username or parts.password:
        raise BoundaryError(
            "refused: URLs carrying credentials are never used")
    return parts


class _BoundaryRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-applies the hard boundaries on every hop.

    Without this, ``urlopen`` would follow a redirect from a vetted URL to
    a loopback/internal address, silently bypassing ``_check_boundary``
    (SSRF). Any out-of-bounds hop raises ``BoundaryError`` and aborts the
    whole chain.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_boundary(newurl)  # raises BoundaryError: aborts the chain
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_BoundaryRedirectHandler)


def _http_get(url: str, policy: CrawlPolicy) -> Tuple[bytes, str]:
    """Single HTTP GET choke point. Returns (body, content_type).

    Raises BoundaryError for out-of-bounds URLs, FetchError for
    network/HTTP failures. Never returns fabricated content.
    """
    _check_boundary(url)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": policy.user_agent,
                 "Accept": "*/*"},
    )
    try:
        # NOTE: _OPENER (not urlopen) so every redirect hop is re-checked
        # against the hard boundaries by _BoundaryRedirectHandler.
        with _OPENER.open(req, timeout=policy.timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise FetchError("HTTP %s for %s" % (status, url))
            body = resp.read(policy.max_bytes + 1)
            if len(body) > policy.max_bytes:
                body = body[:policy.max_bytes]
            ctype = resp.headers.get("Content-Type", "")
            return body, ctype
    except (BoundaryError, FetchError):
        raise
    except Exception as exc:
        raise FetchError("could not fetch %s: %s" % (url, exc)) from exc


# --------------------------------------------------------------------------
# robots.txt + polite crawler
# --------------------------------------------------------------------------

def parse_robots(text: str, user_agent: str) -> List[str]:
    """Return Disallow path prefixes applying to *user_agent*.

    Considers blocks for our exact agent token (``levi-deepweb``) and the
    wildcard ``*`` block. An empty Disallow means "allow all". Malformed
    lines are ignored (fail-open on parse, fail-closed on fetch: callers
    still rate-limit and identify).
    """
    token = user_agent.split("/")[0].lower()  # "levi-deepweb"
    disallows: List[str] = []
    in_scope = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            agent = value.lower()
            in_scope = agent in ("*", token)
        elif key == "disallow" and in_scope and value:
            disallows.append(value)
    return disallows


def _robots_url(url: str) -> str:
    parts = urllib.parse.urlparse(url)
    return "%s://%s/robots.txt" % (parts.scheme, parts.netloc)


class PoliteCrawler:
    """Rate-limited, robots.txt-honoring fetcher.

    ``clock``/``sleeper`` are injectable so tests never sleep or hit the
    network. Refusals (robots disallow, boundary, fetch failure) are
    recorded in ``self.refusals`` instead of raising — the survey stays
    honest about what it could not reach.
    """

    def __init__(self, policy: Optional[CrawlPolicy] = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.policy = policy or CrawlPolicy()
        self._clock = clock
        self._sleeper = sleeper
        self._last_fetch: Dict[str, float] = {}
        self._robots_cache: Dict[str, List[str]] = {}
        self._page_counts: Dict[str, int] = {}
        self.refusals: List[Dict[str, str]] = []

    def _refuse(self, url: str, reason: str) -> None:
        self.refusals.append({"url": url, "reason": reason,
                              "at": _now_iso()})

    def _robots_for(self, host: str, scheme: str) -> List[str]:
        if host in self._robots_cache:
            return self._robots_cache[host]
        disallows: List[str] = []
        if self.policy.respect_robots:
            try:
                body, _ = _http_get("%s://%s/robots.txt" % (scheme, host),
                                   self.policy)
                disallows = parse_robots(
                    body.decode("utf-8", "replace"), self.policy.user_agent)
            except (FetchError, BoundaryError):
                # Unreachable robots.txt: proceed (standard behavior) but
                # stay rate-limited and identified. Recorded, not hidden.
                self._refuse("%s://%s/robots.txt" % (scheme, host),
                             "robots.txt unreachable; proceeding rate-limited")
        self._robots_cache[host] = disallows
        return disallows

    def allowed(self, url: str) -> bool:
        """True if *url* passes the hard boundaries and robots.txt."""
        try:
            parts = _check_boundary(url)
        except BoundaryError as exc:
            self._refuse(url, str(exc))
            return False
        if not self.policy.respect_robots:
            return True
        host = parts.hostname or ""
        for prefix in self._robots_for(host, parts.scheme):
            if parts.path.startswith(prefix):
                self._refuse(url, "disallowed by robots.txt (%s)" % prefix)
                return False
        return True

    def get(self, url: str) -> Optional[Tuple[bytes, str]]:
        """Fetch *url* politely. None when refused or unreachable."""
        try:
            parts = _check_boundary(url)
        except BoundaryError as exc:
            self._refuse(url, str(exc))
            return None
        host = parts.hostname or ""
        if self._page_counts.get(host, 0) >= self.policy.max_pages_per_host:
            self._refuse(url, "per-host page cap reached")
            return None
        if not self.allowed(url):
            return None
        # Rate limit per host.
        now = self._clock()
        last = self._last_fetch.get(host)
        if last is not None:
            wait = self.policy.delay_seconds - (now - last)
            if wait > 0:
                self._sleeper(wait)
                now = self._clock()
        try:
            result = _http_get(url, self.policy)
        except (FetchError, BoundaryError) as exc:
            self._refuse(url, str(exc))
            return None
        self._last_fetch[host] = now
        self._page_counts[host] = self._page_counts.get(host, 0) + 1
        return result


# --------------------------------------------------------------------------
# Text extraction (extractive snippets — never presented as summaries of
# meaning, only as "this is what the page starts with").
# --------------------------------------------------------------------------

_TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>", re.S | re.I)
_STRIP_RE = re.compile(r"<[^>]+>")


def extract_text(html_bytes: bytes, limit: int = 1200) -> str:
    """Extract a readable text prefix from HTML. Best-effort, stdlib-only."""
    try:
        text = html_bytes.decode("utf-8", "replace")
    except Exception:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = _STRIP_RE.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _title_of(html_bytes: bytes) -> str:
    try:
        text = html_bytes.decode("utf-8", "replace")
    except Exception:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if not m:
        return ""
    return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:200]


# --------------------------------------------------------------------------
# Wayback Machine (web.archive.org) — snapshots of the public web.
# --------------------------------------------------------------------------

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
AVAIL_ENDPOINT = "https://archive.org/wayback/available"


def wayback_cdx(url: str, crawler: Optional[PoliteCrawler] = None,
                limit: int = 20) -> List[DeepSource]:
    """Query the Wayback CDX API for successful captures of *url*.

    ``url`` may include a wildcard (``example.com/docs/*``). Returns one
    DeepSource per capture with the replay URL as ``url``.
    """
    crawler = crawler or PoliteCrawler()
    query = {
        "url": url, "output": "json", "filter": "statuscode:200",
        "collapse": "urlkey", "limit": str(limit),
        "fl": "timestamp,original,statuscode,digest",
    }
    target = CDX_ENDPOINT + "?" + urllib.parse.urlencode(query)
    got = crawler.get(target)
    if got is None:
        return []
    body, _ = got
    try:
        rows = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return []
    if not rows or rows[0][0] != "timestamp":
        return []
    out: List[DeepSource] = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        ts, original = row[0], row[1]
        replay = "https://web.archive.org/web/%s/%s" % (ts, original)
        out.append(DeepSource(
            kind="wayback", url=replay,
            title="Snapshot %s — %s" % (ts, original),
            retrieved_at=_now_iso(),
            method="Wayback CDX query for %s" % url,
            notes="archived capture %s (HTTP 200)" % ts,
        ))
    return out


def wayback_availability(url: str,
                         crawler: Optional[PoliteCrawler] = None
                         ) -> Optional[DeepSource]:
    """Closest Wayback snapshot to now for *url* (availability API)."""
    crawler = crawler or PoliteCrawler()
    target = AVAIL_ENDPOINT + "?" + urllib.parse.urlencode({"url": url})
    got = crawler.get(target)
    if got is None:
        return None
    try:
        data = json.loads(got[0].decode("utf-8", "replace"))
    except ValueError:
        return None
    snap = (data.get("archived_snapshots") or {}).get("closest") or {}
    if not snap.get("available"):
        return None
    return DeepSource(
        kind="wayback", url=snap.get("url", ""),
        title="Closest snapshot — %s" % url,
        retrieved_at=_now_iso(),
        method="Wayback availability API",
        notes="snapshot timestamp %s" % snap.get("timestamp", "?"),
    )



# --------------------------------------------------------------------------
# Common Crawl (index.commoncrawl.org) — capture metadata, never WARC data.
# --------------------------------------------------------------------------

CC_COLLINFO = "https://index.commoncrawl.org/collinfo.json"


def commoncrawl_latest_index(crawler: Optional[PoliteCrawler] = None) -> str:
    """Newest Common Crawl index id (e.g. ``CC-MAIN-2025-30``)."""
    crawler = crawler or PoliteCrawler()
    got = crawler.get(CC_COLLINFO)
    if got is None:
        raise FetchError("could not reach Common Crawl collinfo")
    try:
        infos = json.loads(got[0].decode("utf-8", "replace"))
        return str(infos[0]["id"])
    except (ValueError, KeyError, IndexError) as exc:
        raise FetchError("could not parse Common Crawl collinfo: %s"
                         % exc) from exc


def commoncrawl_captures(url_pattern: str,
                         crawler: Optional[PoliteCrawler] = None,
                         index: Optional[str] = None,
                         limit: int = 20) -> List[DeepSource]:
    """Query the Common Crawl index for captures matching *url_pattern*.

    Returns capture *metadata* (URL, timestamp, WARC location). WARC
    payloads are deliberately never downloaded — the index is the map.
    """
    crawler = crawler or PoliteCrawler()
    index = index or commoncrawl_latest_index(crawler)
    target = ("https://index.commoncrawl.org/%s-index?%s" % (
        index, urllib.parse.urlencode(
            {"url": url_pattern, "output": "json",
             "limit": str(limit)})))
    got = crawler.get(target)
    if got is None:
        return []
    out: List[DeepSource] = []
    for line in got[0].decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        out.append(DeepSource(
            kind="commoncrawl", url=str(rec.get("url", "")),
            title="Capture %s — %s" % (rec.get("timestamp", "?"),
                                       rec.get("url", "")),
            retrieved_at=_now_iso(),
            method="Common Crawl %s index query" % index,
            notes="warc %s @ offset %s (metadata only — payload not fetched)"
                  % (rec.get("filename", "?"), rec.get("offset", "?")),
        ))
    return out


# --------------------------------------------------------------------------
# Sitemaps — discovery via robots.txt + probing, enumeration with caps.
# --------------------------------------------------------------------------

_SITEMAP_PROBES = ("sitemap.xml", "sitemap_index.xml", "sitemap-index.xml")


def discover_sitemaps(domain: str,
                      crawler: Optional[PoliteCrawler] = None
                      ) -> List[str]:
    """Find sitemap URLs for *domain*: robots.txt ``Sitemap:`` lines first,
    then conventional probes. *domain* may be a bare host or a URL."""
    crawler = crawler or PoliteCrawler()
    host = urllib.parse.urlparse(
        domain if "://" in domain else "https://" + domain).hostname or domain
    found: List[str] = []
    got = crawler.get("https://%s/robots.txt" % host)
    if got is not None:
        for raw in got[0].decode("utf-8", "replace").splitlines():
            line = raw.split("#", 1)[0].strip()
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                if sm and sm not in found:
                    found.append(sm)
    for probe in _SITEMAP_PROBES:
        cand = "https://%s/%s" % (host, probe)
        if cand in found:
            continue
        got = crawler.get(cand)
        if got is not None and b"<sitemap" in got[0][:400].lower():
            found.append(cand)
    return found


def _local(tag: str) -> str:
    return tag.split("}")[-1].lower()


def enumerate_sitemap(sitemap_url: str,
                      crawler: Optional[PoliteCrawler] = None,
                      max_urls: int = 2000,
                      max_depth: int = 3) -> List[str]:
    """List page URLs from a sitemap (or sitemap index). Capped."""
    crawler = crawler or PoliteCrawler()
    urls: List[str] = []

    def _loc_text(el: ET.Element) -> str:
        for child in el:
            if _local(child.tag) == "loc":
                return (child.text or "").strip()
        return "".join(el.itertext()).strip()

    def _walk(sm_url: str, depth: int) -> None:
        if depth > max_depth or len(urls) >= max_urls:
            return
        got = crawler.get(sm_url)
        if got is None:
            return
        try:
            root = ET.fromstring(got[0])
        except ET.ParseError:
            return
        if _local(root.tag) == "sitemapindex":
            for sm in root.iter():
                if _local(sm.tag) != "sitemap":
                    continue
                loc = _loc_text(sm)
                if loc:
                    _walk(loc, depth + 1)
        else:  # urlset
            for url_el in root.iter():
                if _local(url_el.tag) != "url":
                    continue
                loc = _loc_text(url_el)
                if loc and loc not in urls and len(urls) < max_urls:
                    urls.append(loc)

    _walk(sitemap_url, 0)
    return urls


# --------------------------------------------------------------------------
# Feeds — discovery + item extraction (RSS 2.0 and Atom).
# --------------------------------------------------------------------------

_FEED_PROBES = ("feed", "feed.xml", "rss", "rss.xml", "atom.xml")
_FEED_LINK_RE = re.compile(r'<link[^>]+rel=["\']alternate["\'][^>]*>', re.I)
_FEED_TYPE_RE = re.compile(r'type=["\']application/(rss|atom)\+xml["\']', re.I)
_FEED_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def discover_feeds(page_url: str,
                   crawler: Optional[PoliteCrawler] = None) -> List[str]:
    """Find RSS/Atom feed URLs for a page: ``<link rel=alternate>`` first,
    then conventional paths."""
    crawler = crawler or PoliteCrawler()
    found: List[str] = []
    got = crawler.get(page_url)
    if got is not None:
        try:
            text = got[0].decode("utf-8", "replace")
        except Exception:
            text = ""
        for tag in _FEED_LINK_RE.findall(text):
            if _FEED_TYPE_RE.search(tag):
                m = _FEED_HREF_RE.search(tag)
                if m:
                    absu = urllib.parse.urljoin(page_url, m.group(1))
                    if absu not in found:
                        found.append(absu)
    base = page_url.rstrip("/")
    for probe in _FEED_PROBES:
        cand = base + "/" + probe
        if cand in found:
            continue
        got = crawler.get(cand)
        if got is not None:
            head = got[0][:400].lower()
            if b"<rss" in head or b"<feed" in head:
                found.append(cand)
    return found


def _child_text(el: ET.Element, name: str) -> str:
    for child in el.iter():
        if _local(child.tag) == name and child.text:
            return html.unescape(
                re.sub(r"\s+", " ", child.text).strip())[:600]
    return ""


def feed_entries(feed_bytes: bytes) -> List[Dict[str, str]]:
    """Extract (title, link, summary) entries from RSS 2.0 or Atom bytes."""
    try:
        root = ET.fromstring(feed_bytes)
    except ET.ParseError:
        return []
    out: List[Dict[str, str]] = []
    if _local(root.tag) == "rss":
        for it in root.iter():
            if _local(it.tag) != "item":
                continue
            title = _child_text(it, "title")
            link = _child_text(it, "link")
            desc = _child_text(it, "description")
            if title or link:
                out.append({"title": title[:200], "link": link,
                            "summary": desc})
    else:  # Atom <feed>/<entry>
        for it in root.iter():
            if _local(it.tag) != "entry":
                continue
            title = _child_text(it, "title")
            link = ""
            for child in it.iter():
                if _local(child.tag) == "link" and child.get("href"):
                    link = child.get("href", "").strip()
                    break
            summ = _child_text(it, "summary") or _child_text(it, "content")
            if title or link:
                out.append({"title": title[:200], "link": link,
                            "summary": summ})
    return out


def parse_feed(feed_url: str, crawler: Optional[PoliteCrawler] = None,
               limit: int = 15) -> List[DeepSource]:
    """Fetch a feed URL and return its items as DeepSources."""
    crawler = crawler or PoliteCrawler()
    got = crawler.get(feed_url)
    if got is None:
        return []
    out: List[DeepSource] = []
    for entry in feed_entries(got[0])[:limit]:
        out.append(DeepSource(
            kind="feed", url=entry["link"], title=entry["title"],
            summary=entry["summary"], retrieved_at=_now_iso(),
            method="feed item from %s" % feed_url,
        ))
    return out


# --------------------------------------------------------------------------
# arXiv API (Atom) — the academic record. arXiv asks for ~3s between calls.
# --------------------------------------------------------------------------

ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"


def arxiv_search(query: str, crawler: Optional[PoliteCrawler] = None,
                 max_results: int = 10) -> List[DeepSource]:
    """Search arXiv (all fields). Polite: dedicated 3s-delay crawler."""
    crawler = crawler or PoliteCrawler(policy=CrawlPolicy(delay_seconds=3.0))
    target = ARXIV_ENDPOINT + "?" + urllib.parse.urlencode({
        "search_query": "all:" + query, "start": "0",
        "max_results": str(max_results), "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    got = crawler.get(target)
    if got is None:
        return []
    out: List[DeepSource] = []
    for entry in feed_entries(got[0])[:max_results]:
        out.append(DeepSource(
            kind="arxiv", url=entry["link"], title=entry["title"],
            summary=entry["summary"], retrieved_at=_now_iso(),
            method="arXiv API search: %s" % query,
            notes="open-access academic record",
        ))
    return out


# --------------------------------------------------------------------------
# Open public-record portals (unauthenticated JSON endpoints only).
# --------------------------------------------------------------------------

def datagov_search(query: str, crawler: Optional[PoliteCrawler] = None,
                   rows: int = 10) -> List[DeepSource]:
    """Search the data.gov CKAN open-data catalog (public JSON API)."""
    crawler = crawler or PoliteCrawler()
    target = ("https://catalog.data.gov/api/3/action/package_search?"
              + urllib.parse.urlencode({"q": query, "rows": str(rows)}))
    got = crawler.get(target)
    if got is None:
        return []
    try:
        data = json.loads(got[0].decode("utf-8", "replace"))
    except ValueError:
        return []
    out: List[DeepSource] = []
    for ds in (data.get("result") or {}).get("results", []):
        name = str(ds.get("name", ""))
        out.append(DeepSource(
            kind="portal",
            url="https://catalog.data.gov/dataset/" + name,
            title=str(ds.get("title", ""))[:200],
            summary=str(ds.get("notes", ""))[:600],
            retrieved_at=_now_iso(),
            method="data.gov CKAN package_search",
            notes="open government dataset; organization: %s"
                  % (ds.get("organization") or {}).get("title", "?"),
        ))
    return out


def sec_edgar_search(query: str,
                     crawler: Optional[PoliteCrawler] = None
                     ) -> List[DeepSource]:
    """Match *query* against SEC EDGAR public company tickers, then pull
    each match's public submissions index. Best-effort: EDGAR formats
    change; failures are reported, never fabricated."""
    crawler = crawler or PoliteCrawler()
    got = crawler.get("https://www.sec.gov/files/company_tickers.json")
    if got is None:
        return []
    try:
        tickers = json.loads(got[0].decode("utf-8", "replace"))
    except ValueError:
        return []
    q = query.lower()
    matches = [t for t in tickers.values()
               if q in str(t.get("title", "")).lower()
               or q == str(t.get("ticker", "")).lower()][:5]
    out: List[DeepSource] = []
    for m in matches:
        cik = str(m.get("cik_str", "")).zfill(10)
        url = "https://data.sec.gov/submissions/CIK%s.json" % cik
        sub = crawler.get(url)
        forms: List[str] = []
        if sub is not None:
            try:
                recent = json.loads(
                    sub[0].decode("utf-8", "replace")
                ).get("filings", {}).get("recent", {})
                forms = [str(f) for f in recent.get("form", [])[:3]]
            except ValueError:
                pass
        out.append(DeepSource(
            kind="portal", url=url,
            title="SEC EDGAR: %s (%s)" % (m.get("title", ""),
                                          m.get("ticker", "")),
            summary=("recent filings: %s" % ", ".join(forms)) if forms
                     else "",
            retrieved_at=_now_iso(),
            method="SEC EDGAR public company_tickers + submissions JSON",
            notes="public filings record; no authentication used",
        ))
    return out


OPEN_PORTALS: Dict[str, Dict[str, Any]] = {
    "datagov": {
        "label": "data.gov — US open-data catalog (CKAN JSON API)",
        "search": datagov_search,
    },
    "sec-edgar": {
        "label": "SEC EDGAR — public company filings (JSON)",
        "search": sec_edgar_search,
    },
}


# --------------------------------------------------------------------------
# Survey orchestration
# --------------------------------------------------------------------------

def survey_topic(topic: str, seed_domains: List[str] | None = None,
                 policy: Optional[CrawlPolicy] = None,
                 max_per_source: int = 10) -> DeepSurvey:
    """Survey *topic* across deep-web sources. Returns a DeepSurvey with
    provenance on every finding and recorded refusals.

    *seed_domains* are starting points the caller already knows (e.g. a
    dead project's old domain): Wayback snapshots, sitemaps, and feeds
    are enumerated for each. Nothing is invented: every source was
    actually retrieved, every failure recorded.
    """
    crawler = PoliteCrawler(policy=policy or CrawlPolicy())
    survey = DeepSurvey(topic=topic)
    survey.sources.extend(arxiv_search(topic, crawler, max_per_source))
    survey.sources.extend(datagov_search(topic, crawler, max_per_source))
    for domain in seed_domains or []:
        root = domain if "://" in domain else "https://" + domain
        snap = wayback_availability(root, crawler)
        if snap is not None:
            survey.add(snap)
        for sm in discover_sitemaps(domain, crawler):
            for page in enumerate_sitemap(sm, crawler, max_urls=50)[:10]:
                got = crawler.get(page)
                if got is None:
                    continue
                body, ctype = got
                if "html" not in ctype:
                    continue
                survey.add(DeepSource(
                    kind="sitemap", url=page,
                    title=_title_of(body) or page,
                    summary=extract_text(body),
                    retrieved_at=_now_iso(),
                    method="sitemap enumeration via %s" % sm,
                ))
        for feed_url in discover_feeds(root, crawler)[:3]:
            survey.sources.extend(parse_feed(feed_url, crawler, 5))
    survey.refusals.extend(crawler.refusals)
    return survey


# --------------------------------------------------------------------------
# Persistence (home resolved at call time — never import-time).
# --------------------------------------------------------------------------

def research_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "research" / "deepweb"


def save_survey(survey: DeepSurvey,
                home: "str | os.PathLike[str] | None" = None) -> Path:
    """Persist a survey as JSON under ~/.levi/research/deepweb/."""
    dest = research_home(home)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(dest, 0o700)
    except OSError:
        pass
    slug = re.sub(r"[^a-z0-9]+", "-", survey.topic.lower()).strip("-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = dest / ("%s-%s.json" % (slug[:40] or "survey", stamp))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(survey.to_dict(), indent=2, ensure_ascii=False),
                   encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------
# CLI: python -m levi.research.deepweb <command>
# --------------------------------------------------------------------------

def _print_sources(sources: List[DeepSource], as_json: bool) -> None:
    if as_json:
        print(json.dumps([s.to_dict() for s in sources], indent=2,
                         ensure_ascii=False))
        return
    if not sources:
        print("(no sources found — refusals/failures are reported, "
              "never fabricated)")
        return
    for s in sources:
        print("[%s] %s" % (s.kind, s.title or s.url))
        print("  url: %s" % s.url)
        if s.summary:
            print("  %s" % s.summary[:220])
        print("  via: %s | retrieved: %s" % (s.method, s.retrieved_at))
        if s.notes:
            print("  note: %s" % s.notes)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="levi.research.deepweb",
        description="Deep-web research over public but unindexed sources "
                    "(polite, robots.txt-honoring, public-only).",
    )
    ap.add_argument("--json", action="store_true",
                    help="Machine-readable JSON output")
    ap.add_argument("--home", default=None,
                    help="Override home dir (tests / hermetic runs)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("survey", help="Survey a topic across deep sources")
    p.add_argument("topic", help="Topic to research")
    p.add_argument("--domain", action="append", default=[],
                   help="Seed domain (repeatable)")
    p.add_argument("--max", type=int, default=10,
                   help="Max results per source")
    p.add_argument("--save", action="store_true",
                   help="Persist the survey under ~/.levi/research/deepweb/")

    p = sub.add_parser("wayback", help="Wayback CDX captures for a URL")
    p.add_argument("--url", required=True)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("commoncrawl", help="Common Crawl captures (metadata)")
    p.add_argument("--pattern", required=True,
                   help="URL pattern, e.g. 'example.com/docs/*'")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("sitemap", help="Discover + enumerate sitemaps")
    p.add_argument("--domain", required=True)

    p = sub.add_parser("feeds", help="Discover feeds for a page")
    p.add_argument("--url", required=True)
    p.add_argument("--items", action="store_true",
                   help="Also fetch feed items")

    p = sub.add_parser("arxiv", help="Search arXiv")
    p.add_argument("--query", required=True)
    p.add_argument("--max", type=int, default=10)

    p = sub.add_parser("portals", help="Search open public-record portals")
    p.add_argument("--portal", choices=sorted(OPEN_PORTALS), default=None,
                   help="Portal id (default: all)")
    p.add_argument("--query", required=True)

    sub.add_parser("boundaries", help="Print the hard boundaries")

    args = ap.parse_args(argv)
    crawler = PoliteCrawler()

    if args.cmd == "boundaries":
        print(BOUNDARIES_TEXT)
        return 0
    if args.cmd == "survey":
        survey = survey_topic(args.topic, seed_domains=args.domain,
                              max_per_source=args.max)
        if args.json:
            print(json.dumps(survey.to_dict(), indent=2,
                             ensure_ascii=False))
        else:
            print("DEEP SURVEY: %s (%d sources, %d refusals)" % (
                survey.topic, len(survey.sources),
                len(survey.refusals)))
            _print_sources(survey.sources, False)
            for r in survey.refusals[:10]:
                print("  refused: %s — %s" % (r["url"], r["reason"]))
        if args.save:
            path = save_survey(survey, home=args.home)
            print("saved: %s" % path)
        return 0
    if args.cmd == "wayback":
        _print_sources(wayback_cdx(args.url, crawler, args.limit),
                       args.json)
        return 0
    if args.cmd == "commoncrawl":
        try:
            srcs = commoncrawl_captures(args.pattern, crawler,
                                        limit=args.limit)
        except FetchError as exc:
            print("failed: %s" % exc)
            return 1
        _print_sources(srcs, args.json)
        return 0
    if args.cmd == "sitemap":
        sms = discover_sitemaps(args.domain, crawler)
        urls: List[str] = []
        for sm in sms[:5]:
            urls.extend(enumerate_sitemap(sm, crawler, max_urls=200))
        if args.json:
            print(json.dumps({"sitemaps": sms, "urls": urls[:200]},
                             indent=2))
        else:
            print("sitemaps: %d, urls enumerated: %d" % (len(sms),
                                                         len(urls)))
            for sm in sms:
                print("  sitemap: %s" % sm)
            for u in urls[:20]:
                print("  url: %s" % u)
        return 0
    if args.cmd == "feeds":
        feeds = discover_feeds(args.url, crawler)
        if args.items:
            srcs: List[DeepSource] = []
            for f in feeds[:3]:
                srcs.extend(parse_feed(f, crawler))
            _print_sources(srcs, args.json)
        elif args.json:
            print(json.dumps({"feeds": feeds}, indent=2))
        else:
            for f in feeds:
                print("feed: %s" % f)
            if not feeds:
                print("(no feeds discovered)")
        return 0
    if args.cmd == "arxiv":
        _print_sources(arxiv_search(args.query, crawler, args.max),
                       args.json)
        return 0
    if args.cmd == "portals":
        ids = [args.portal] if args.portal else sorted(OPEN_PORTALS)
        srcs = []
        for pid in ids:
            try:
                srcs.extend(OPEN_PORTALS[pid]["search"](
                    args.query, crawler))
            except FetchError as exc:
                print("portal %s failed: %s" % (pid, exc))
        _print_sources(srcs, args.json)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
