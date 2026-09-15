"""Content discovery — archived URLs, JS harvesting, exposure detection.

  - Wayback Machine CDX API: archived URLs for the target's hosts
    (passive — touches archive.org, not the target).
  - JS harvesting: <script src> from probed pages, fetched with ordinary
    GETs, then regex extraction of API-ish endpoints.
  - Exposure *detection*: regexes for secret-shaped strings (AWS keys,
    generic api_key/token assignments) in fetched JS. These are REPORTED
    as findings for the hunter to verify — detection only, never
    exploited, never used.

Scope gate applies to the target domain; archive.org itself is a public
data source and needs no enrollment.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Dict, List, Optional, Set

from levi.bounty.scope import ScopeStore, check_scope, normalize_domain

UA = "LEVI-bounty-recon/1.0 (authorized bug-bounty recon; in-scope targets only)"
TIMEOUT = 10
REQUEST_DELAY = 0.5

WAYBACK_CDX = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=*.{domain}/*&output=json&filter=statuscode:200"
    "&collapse=urlkey&limit=2000"
)

_SCRIPT_SRC_RE = re.compile(
    r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', re.IGNORECASE
)
_ENDPOINT_RE = re.compile(
    r"""["'`](/(?:api|v\d|graphql|rest|internal|admin)[A-Za-z0-9_\-./{}]*)["'`]"""
)

# Secret-shaped patterns — DETECTION ONLY. Matches are reported as
# "possible exposure — verify manually", never used or tested.
_SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_api_key_assign": re.compile(
        r"""(?i)(?:api[_-]?key|apikey)\s*[:=]\s*["'][A-Za-z0-9_\-]{16,}["']"""
    ),
    "generic_secret_assign": re.compile(
        r"""(?i)(?:secret|token)\s*[:=]\s*["'][A-Za-z0-9_\-]{20,}["']"""
    ),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
}


def _fetch_text(url: str, timeout: int = TIMEOUT) -> Optional[str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(5_000_000).decode("utf-8", "replace")
    except Exception:
        return None


def wayback_urls(domain: str, delay: float = REQUEST_DELAY) -> List[str]:
    """Archived URLs for *.domain from the Wayback CDX API (passive)."""
    body = _fetch_text(WAYBACK_CDX.format(domain=domain))
    time.sleep(delay)
    if not body:
        return []
    try:
        rows = json.loads(body)
    except Exception:
        return []
    urls: List[str] = []
    for row in rows[1:]:  # first row is the header
        if len(row) > 2 and row[2]:
            urls.append(row[2])
    # dedup, keep it bounded
    seen: Set[str] = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= 500:
            break
    return out


def _script_urls(page_url: str, html: str) -> List[str]:
    found: List[str] = []
    for m in _SCRIPT_SRC_RE.finditer(html):
        src = m.group(1)
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            base = re.match(r"(https?://[^/]+)", page_url)
            src = (base.group(1) if base else "") + src
        elif not src.startswith("http"):
            src = page_url.rsplit("/", 1)[0] + "/" + src
        found.append(src)
    return found[:20]


def harvest_js(
    host: str,
    page_bodies: Dict[str, str],
    delay: float = REQUEST_DELAY,
) -> List[Dict[str, object]]:
    """Fetch <script src> JS from probed pages; extract endpoints + exposures.

    ``page_bodies`` maps page URL -> HTML (as captured during probing).
    Returns a list of {js_url, endpoints, possible_exposures}.
    """
    results: List[Dict[str, object]] = []
    for page_url, html in page_bodies.items():
        for js_url in _script_urls(page_url, html):
            js = _fetch_text(js_url)
            time.sleep(delay)
            if not js:
                continue
            endpoints = sorted(set(_ENDPOINT_RE.findall(js)))[:50]
            exposures = sorted(
                {name for name, rx in _SECRET_PATTERNS.items() if rx.search(js)}
            )
            if endpoints or exposures:
                results.append(
                    {
                        "js_url": js_url,
                        "endpoints": endpoints,
                        "possible_exposures": exposures,
                    }
                )
    return results


def collect_content(
    domain: str,
    store: Optional[ScopeStore] = None,
    page_bodies: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """Content discovery for an in-scope domain. Scope gate at entry."""
    check_scope(domain, store)  # raises ScopeError if out of scope
    target = normalize_domain(domain)
    archived = wayback_urls(target)
    bodies = dict(page_bodies or {})
    if not bodies:
        # fetch the target's own homepage so JS harvesting has something
        # to work with (ordinary GETs, in-scope by the gate above)
        for scheme in ("https", "http"):
            html = _fetch_text(f"{scheme}://{target}/")
            if html:
                bodies[f"{scheme}://{target}/"] = html
                break
            time.sleep(REQUEST_DELAY)
    js = harvest_js(target, bodies)
    return {
        "domain": target,
        "archived_urls": archived,
        "archived_count": len(archived),
        "js_files": js,
    }
