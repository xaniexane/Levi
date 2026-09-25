"""local_feed_reader — sovereign RSS, parsed and watched locally.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 4]).
Load-bearing idea: RSS aggregation that lives on your machine — feed
health monitoring (is it alive? stale? broken?) and OPML portability so
your subscription list is yours to carry anywhere.

LEVI's take: ``FeedReader`` manages ``Feed`` subscriptions. Parsing is
local (``xml.etree`` over RSS 2.0 / Atom supplied by the caller — cache
files, pasted documents, test fixtures), so there is no network anywhere
in this module. Each feed keeps health stats: last successful parse,
consecutive errors, item count, staleness. OPML import/export makes the
whole subscription list portable in one document.

Honest limits: this module parses and watches; it does not fetch. A
``refresh`` takes feed XML you already hold (e.g. saved to disk by
whatever fetcher you trust) and updates items + health.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/local-feed-reader"

STALE_AFTER = 24 * 3600.0  # a feed silent for a day counts as stale


@dataclass
class FeedItem:
    id: str
    title: str
    link: str
    published: str
    summary: str


@dataclass
class Feed:
    id: str
    name: str
    url: str
    kind: str = "rss"  # rss | atom
    items: List[FeedItem] = field(default_factory=list)
    last_ok: float = 0.0
    last_attempt: float = 0.0
    error_count: int = 0
    last_error: str = ""
    muted: bool = False

    def health(self, now: Optional[float] = None) -> Dict[str, object]:
        now = time.time() if now is None else now
        age = now - self.last_ok if self.last_ok else float("inf")
        if self.error_count > 0 and self.last_attempt > self.last_ok:
            status = "error"
        elif self.last_ok == 0.0:
            status = "never-fetched"
        elif age > STALE_AFTER:
            status = "stale"
        else:
            status = "healthy"
        return {
            "status": status,
            "items": len(self.items),
            "error_count": self.error_count,
            "last_error": self.last_error,
            "seconds_since_ok": None if age == float("inf") else age,
        }


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def _find(parent: ET.Element, name: str) -> Optional[ET.Element]:
    """Find a child ignoring XML namespaces."""
    for child in parent:
        tag = child.tag.split("}")[-1]
        if tag == name:
            return child
    return None


def parse_feed_xml(xml_text: str) -> tuple[str, List[FeedItem]]:
    """Parse RSS 2.0 or Atom from a string. Returns (kind, items).

    Raises ValueError on unparseable documents.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"not parseable XML: {exc}") from exc
    tag = root.tag.split("}")[-1].lower()
    items: List[FeedItem] = []
    if tag == "rss":
        kind = "rss"
        for it in root.iter():
            if it.tag.split("}")[-1] == "item":
                guid = _text(_find(it, "guid")) or _text(_find(it, "link"))
                items.append(
                    FeedItem(
                        id=guid or _text(_find(it, "title")),
                        title=_text(_find(it, "title")),
                        link=_text(_find(it, "link")),
                        published=_text(_find(it, "pubDate")),
                        summary=_text(_find(it, "description")),
                    )
                )
    elif tag == "feed":
        kind = "atom"
        for child in root:
            if child.tag.split("}")[-1] == "entry":
                link_el = _find(child, "link")
                link = link_el.get("href", "") if link_el is not None else ""
                items.append(
                    FeedItem(
                        id=_text(_find(child, "id")) or link,
                        title=_text(_find(child, "title")),
                        link=link,
                        published=_text(_find(child, "updated"))
                        or _text(_find(child, "published")),
                        summary=_text(_find(child, "summary")),
                    )
                )
    else:
        raise ValueError(f"unrecognized feed root <{tag}>")
    return kind, items


class FeedReader:
    """Local RSS/Atom aggregation with health monitoring and OPML portability."""

    def __init__(self) -> None:
        self.feeds: Dict[str, Feed] = {}

    # -- subscriptions --------------------------------------------------------

    def subscribe(self, name: str, url: str) -> Feed:
        f = Feed(id=f"feed-{uuid.uuid4().hex[:8]}", name=name, url=url)
        self.feeds[f.id] = f
        return f

    def unsubscribe(self, feed_id: str) -> bool:
        return self.feeds.pop(feed_id, None) is not None

    def mute(self, feed_id: str, muted: bool = True) -> Feed:
        f = self.feeds[feed_id]
        f.muted = muted
        return f

    # -- refresh from already-held XML (no network) ---------------------------

    def refresh(self, feed_id: str, xml_text: str) -> Feed:
        """Parse held XML into the feed, updating health. Never fetches."""
        f = self.feeds[feed_id]
        f.last_attempt = time.time()
        try:
            kind, items = parse_feed_xml(xml_text)
        except ValueError as exc:
            f.error_count += 1
            f.last_error = str(exc)
            return f
        f.kind = kind
        f.items = items
        f.last_ok = time.time()
        f.error_count = 0
        f.last_error = ""
        return f

    # -- reading --------------------------------------------------------------

    def latest(self, feed_id: str, limit: int = 20) -> List[FeedItem]:
        return self.feeds[feed_id].items[:limit]

    def all_items(self, include_muted: bool = False) -> List[FeedItem]:
        out = []
        for f in self.feeds.values():
            if f.muted and not include_muted:
                continue
            out.extend(f.items)
        return out

    def health_report(self) -> Dict[str, Dict[str, object]]:
        return {f.name: f.health() for f in self.feeds.values()}

    # -- OPML portability -----------------------------------------------------

    def export_opml(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<opml version="2.0">',
            "  <head><title>LEVI feed subscriptions</title></head>",
            "  <body>",
        ]
        for f in self.feeds.values():
            lines.append(
                f'    <outline type="rss" text="{_esc(f.name)}" '
                f'title="{_esc(f.name)}" xmlUrl="{_esc(f.url)}"/>'
            )
        lines += ["  </body>", "</opml>"]
        return "\n".join(lines) + "\n"

    def import_opml(self, opml_text: str) -> List[Feed]:
        """Subscribe to every outline in an OPML document. Returns new feeds."""
        try:
            root = ET.fromstring(opml_text)
        except ET.ParseError as exc:
            raise ValueError(f"not parseable OPML: {exc}") from exc
        made = []
        for el in root.iter("outline"):
            url = el.get("xmlUrl", "")
            name = el.get("text", "") or el.get("title", "") or url
            if url and not any(f.url == url for f in self.feeds.values()):
                made.append(self.subscribe(name, url))
        return made


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
