"""Sovereign feed reader — local RSS/Atom aggregation.

Google killed Reader because RSS can't be monetized: no ad surface, no
engagement graph. A local reader has no ad surface to protect, so it can
be exactly what a reader should be: a polite poller, a durable local
store, honest per-feed health stats, and full OPML portability in and
out. Your subscriptions are a file you own, not a product surface.

Parsing reuses :func:`levi.research.deepweb.feed_entries` (no duplicated
XML logic). Fetching is this module's own polite choke point
(:func:`_http_fetch`) with conditional GET (ETag/Last-Modified) so
servers aren't re-polled wastefully — reusing bandwidth etiquette the
RSS spec asked for twenty years ago.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom

from levi.research.deepweb import feed_entries

ENC = "utf-8"
USER_AGENT = "levi-feedreader/1.0 (+local; polite)"
_MIN_INTERVAL = 300  # seconds between polls of a healthy feed
_BACKOFF_CAP = 24 * 3600


def feedreader_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "feedreader"


class FeedError(Exception):
    pass


def _http_fetch(
    url: str, etag: Optional[str], last_modified: Optional[str]
) -> Tuple[int, bytes, Dict[str, str], float]:
    """Single HTTP choke point. Returns (status, body, headers, latency_s).

    Raises urllib.error.URLError on network failure. Tests monkeypatch this.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if etag:
        req.add_header("If-None-Match", etag)
    if last_modified:
        req.add_header("If-Modified-Since", last_modified)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            body = resp.read() if status == 200 else b""
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, b"", {}, time.monotonic() - t0
        raise
    return status, body, headers, time.monotonic() - t0


class FeedStore:
    """Local feed subscriptions + items, rooted at feedreader_home(home)."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.root = feedreader_home(home)
        self.root.mkdir(parents=True, exist_ok=True)
        self._feeds_path = self.root / "feeds.json"
        self._items_path = self.root / "items.jsonl"

    # -- subscription management --------------------------------------------
    def _load_feeds(self) -> List[Dict[str, Any]]:
        if not self._feeds_path.exists():
            return []
        return json.loads(self._feeds_path.read_text(encoding=ENC))

    def _save_feeds(self, feeds: List[Dict[str, Any]]) -> None:
        self._feeds_path.write_text(json.dumps(feeds, indent=2), encoding=ENC)

    def add(self, url: str, title: Optional[str] = None) -> Dict[str, Any]:
        feeds = self._load_feeds()
        if any(f["url"] == url for f in feeds):
            raise FeedError("already subscribed: %s" % url)
        feed = {
            "url": url,
            "title": title or url,
            "etag": None,
            "last_modified": None,
            "last_poll": 0.0,
            "last_success": 0.0,
            "fail_streak": 0,
            "polls": 0,
            "errors": 0,
            "latency_ms_avg": 0.0,
            "items_seen": 0,
        }
        feeds.append(feed)
        self._save_feeds(feeds)
        return feed

    def remove(self, url: str) -> None:
        feeds = [f for f in self._load_feeds() if f["url"] != url]
        self._save_feeds(feeds)

    def list_feeds(self) -> List[Dict[str, Any]]:
        return self._load_feeds()

    # -- polling -------------------------------------------------------------
    def _backoff_until(self, feed: Dict[str, Any]) -> float:
        if feed["fail_streak"] <= 0:
            return feed["last_poll"] + _MIN_INTERVAL
        return feed["last_poll"] + min(
            _BACKOFF_CAP, _MIN_INTERVAL * (2 ** feed["fail_streak"])
        )

    def poll(
        self, url: Optional[str] = None, force: bool = False
    ) -> List[Dict[str, Any]]:
        """Poll feeds (conditional GET). Returns per-feed poll reports."""
        feeds = self._load_feeds()
        if url:
            feeds = [f for f in feeds if f["url"] == url]
            if not feeds:
                raise FeedError("not subscribed: %s" % url)
        now = time.time()
        reports = []
        for feed in feeds:
            if not force and now < self._backoff_until(feed):
                reports.append(
                    {"url": feed["url"], "skipped": True, "reason": "backoff"}
                )
                continue
            reports.append(self._poll_one(feed, now))
        self._save_feeds(self._load_feeds_merged(feeds))
        return reports

    def _load_feeds_merged(self, updated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_url = {f["url"]: f for f in updated}
        out = []
        for f in self._load_feeds():
            out.append(by_url.get(f["url"], f))
        return out

    def _poll_one(self, feed: Dict[str, Any], now: float) -> Dict[str, Any]:
        feed["last_poll"] = now
        feed["polls"] += 1
        try:
            status, body, headers, latency = _http_fetch(
                feed["url"], feed["etag"], feed["last_modified"]
            )
        except Exception as exc:  # URLError, timeouts — counted, never fatal
            feed["fail_streak"] += 1
            feed["errors"] += 1
            return {
                "url": feed["url"],
                "ok": False,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "fail_streak": feed["fail_streak"],
            }
        feed["latency_ms_avg"] = round(
            (feed["latency_ms_avg"] * (feed["polls"] - 1) + latency * 1000)
            / feed["polls"],
            1,
        )
        if status == 304:
            feed["fail_streak"] = 0
            return {
                "url": feed["url"],
                "ok": True,
                "not_modified": True,
                "new_items": 0,
            }
        if status != 200:
            feed["fail_streak"] += 1
            feed["errors"] += 1
            return {
                "url": feed["url"],
                "ok": False,
                "error": "HTTP %d" % status,
                "fail_streak": feed["fail_streak"],
            }
        feed["etag"] = headers.get("etag", feed["etag"])
        feed["last_modified"] = headers.get("last-modified", feed["last_modified"])
        feed["fail_streak"] = 0
        feed["last_success"] = now
        entries = feed_entries(body)
        new = self._upsert_items(feed["url"], entries, now)
        feed["items_seen"] += len(entries)
        if entries and entries[0]["title"]:
            feed["title"] = (
                entries[0]["title"] if feed["title"] == feed["url"] else feed["title"]
            )
        return {"url": feed["url"], "ok": True, "new_items": new, "total": len(entries)}

    def _upsert_items(
        self, feed_url: str, entries: List[Dict[str, str]], now: float
    ) -> int:
        seen = {it["link"] for it in self._iter_items() if it["feed_url"] == feed_url}
        new = 0
        with self._items_path.open("a", encoding=ENC) as fh:
            for e in entries:
                link = e.get("link") or e.get("title", "")
                if not link or link in seen:
                    continue
                seen.add(link)
                fh.write(
                    json.dumps(
                        {
                            "feed_url": feed_url,
                            "title": e.get("title", ""),
                            "link": link,
                            "summary": e.get("summary", ""),
                            "fetched_at": now,
                            "read": False,
                        }
                    )
                    + "\n"
                )
                new += 1
        return new

    def _iter_items(self):
        if not self._items_path.exists():
            return
        with self._items_path.open(encoding=ENC) as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    # -- views ---------------------------------------------------------------
    def items(
        self, feed_url: Optional[str] = None, unread_only: bool = False, limit: int = 50
    ) -> List[Dict[str, Any]]:
        rows = [
            it
            for it in self._iter_items()
            if (feed_url is None or it["feed_url"] == feed_url)
            and (not unread_only or not it["read"])
        ]
        rows.sort(key=lambda r: r["fetched_at"], reverse=True)
        return rows[:limit]

    def mark_read(self, link: str) -> int:
        changed = 0
        rows = list(self._iter_items())
        for r in rows:
            if r["link"] == link and not r["read"]:
                r["read"] = True
                changed += 1
        if changed:
            with self._items_path.open("w", encoding=ENC) as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
        return changed

    def unread_count(self, feed_url: Optional[str] = None) -> int:
        return sum(
            1
            for it in self._iter_items()
            if not it["read"] and (feed_url is None or it["feed_url"] == feed_url)
        )

    def health(self) -> List[Dict[str, Any]]:
        """Per-feed health: fail streaks, latency, last success — honest stats."""
        out = []
        for f in self._load_feeds():
            if f["fail_streak"] >= 5:
                status = "down"
            elif f["fail_streak"] > 0 or f["polls"] == 0:
                status = "degraded" if f["polls"] else "never-polled"
            else:
                status = "ok"
            out.append(
                {
                    "url": f["url"],
                    "title": f["title"],
                    "status": status,
                    "polls": f["polls"],
                    "errors": f["errors"],
                    "fail_streak": f["fail_streak"],
                    "latency_ms_avg": f["latency_ms_avg"],
                    "last_success": f["last_success"],
                    "items_seen": f["items_seen"],
                }
            )
        return out

    # -- OPML portability ----------------------------------------------------
    def opml_export(self) -> str:
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = "LEVI feedreader subscriptions"
        body = ET.SubElement(opml, "body")
        for f in self._load_feeds():
            ET.SubElement(
                body,
                "outline",
                {
                    "type": "rss",
                    "text": f["title"],
                    "title": f["title"],
                    "xmlUrl": f["url"],
                },
            )
        return minidom.parseString(ET.tostring(opml)).toprettyxml(indent="  ")

    def opml_import(self, opml_text: str) -> int:
        try:
            root = ET.fromstring(opml_text)
        except ET.ParseError as exc:
            raise FeedError("bad OPML: %s" % exc)
        added = 0
        for el in root.iter("outline"):
            url = el.get("xmlUrl")
            if not url:
                continue
            try:
                self.add(url, el.get("title") or el.get("text"))
                added += 1
            except FeedError:
                pass  # already subscribed — idempotent
        return added
