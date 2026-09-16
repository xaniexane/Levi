"""Polite BFS crawl -> Documents.

Reuses ``levi.research.deepweb.PoliteCrawler`` for every fetch, so all
hard boundaries carry over unchanged: robots.txt honored, per-host rate
limiting, public-sources-only, no darknet, refusals recorded (never
fabricated). The ``fetcher`` is injectable so tests never touch the
network.
"""

from __future__ import annotations

import urllib.parse
from html.parser import HTMLParser
from typing import Dict, List, Tuple

from levi.research.deepweb import PoliteCrawler, extract_text

from levi.honestsearch.model import Document, doc_id_for

MAX_TEXT_CHARS = 20000


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value.strip())


def extract_links(html_bytes: bytes, base_url: str) -> List[str]:
    """Absolute http(s) outlinks from a page, fragment-stripped, deduped."""
    try:
        text = html_bytes.decode("utf-8", "replace")
    except Exception:
        return []
    parser = _LinkExtractor()
    try:
        parser.feed(text)
    except Exception:
        return []
    out: List[str] = []
    seen = set()
    for href in parser.links:
        if href.lower().startswith(("javascript:", "mailto:", "data:")):
            continue
        abs_url = urllib.parse.urljoin(base_url, href)
        abs_url, _frag = urllib.parse.urldefrag(abs_url)
        parts = urllib.parse.urlparse(abs_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        if abs_url not in seen:
            seen.add(abs_url)
            out.append(abs_url)
    return out


def title_of(html_bytes: bytes) -> str:
    try:
        text = html_bytes.decode("utf-8", "replace")
    except Exception:
        return ""
    import re

    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if not m:
        return ""
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    import html as _html

    return _html.unescape(title)[:200]


class SiteCrawl:
    """Breadth-first crawl of seed URLs into Documents.

    ``fetcher`` must expose ``.get(url) -> (bytes, content_type) | None``
    and ``.refusals`` (``PoliteCrawler`` does). ``scope="host"`` stays on
    the seed hosts; ``scope="any"`` follows links anywhere the fetcher
    allows (still polite, still robots-honoring).
    """

    def __init__(
        self, fetcher=None, max_pages: int = 50, max_depth: int = 2, scope: str = "host"
    ) -> None:
        if scope not in ("host", "any"):
            raise ValueError("scope must be 'host' or 'any'")
        if max_pages < 1 or max_depth < 0:
            raise ValueError("max_pages >= 1 and max_depth >= 0 required")
        self.fetcher = fetcher or PoliteCrawler()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.scope = scope

    def crawl(self, seeds: List[str]) -> Tuple[List[Document], Dict]:
        seed_hosts = set()
        queue: List[Tuple[str, int]] = []
        for seed in seeds:
            parts = urllib.parse.urlparse(seed)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                continue
            seed_hosts.add(parts.hostname.lower())
            queue.append((seed, 0))
        visited = set()
        documents: List[Document] = []
        skipped_scope = 0
        while queue and len(documents) < self.max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            got = self.fetcher.get(url)
            if got is None:
                continue  # refusal recorded on the fetcher; stay honest
            body, content_type = got
            if "html" not in (content_type or "").lower():
                continue
            outlinks = extract_links(body, url)
            documents.append(
                Document(
                    doc_id=doc_id_for(url),
                    url=url,
                    title=title_of(body) or url,
                    text=extract_text(body, limit=MAX_TEXT_CHARS),
                    outlinks=outlinks,
                    source="crawl",
                )
            )
            if depth < self.max_depth:
                for link in outlinks:
                    host = (urllib.parse.urlparse(link).hostname or "").lower()
                    if self.scope == "host" and host not in seed_hosts:
                        skipped_scope += 1
                        continue
                    if link not in visited:
                        queue.append((link, depth + 1))
        report = {
            "seeds": seeds,
            "pages": len(documents),
            "visited": len(visited),
            "skipped_out_of_scope": skipped_scope,
            "refusals": list(getattr(self.fetcher, "refusals", [])),
            "scope": self.scope,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
        }
        return documents, report
