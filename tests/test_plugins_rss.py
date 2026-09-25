"""Tests for levi.plugins.rss — the credentialless RSS/Atom reader."""

from __future__ import annotations

import pytest

from levi.plugins import rss as rss_mod
from levi.plugins.registry import get_connector, list_connectors
from levi.plugins.rss import (
    ConnectorAPIError,
    InvalidParams,
    RssConnector,
    parse_feed,
)

RSS_SAMPLE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test Feed</title><link>https://example.test/</link>
<item><title>First post</title><link>https://example.test/1</link>
<description>hello</description><pubDate>Mon, 14 Sep 2026 12:00:00 GMT</pubDate></item>
<item><title>Second post</title><link>https://example.test/2</link>
<description>world</description></item>
</channel></rss>"""

ATOM_SAMPLE = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Test</title><link href="https://example.test/"/>
<entry><title>Entry one</title><link href="https://example.test/e1"/>
<summary>summary one</summary><updated>2026-09-14T12:00:00Z</updated></entry>
</feed>"""


def test_registered_and_credentialless():
    ids = [c.id for c in list_connectors()]
    assert "rss" in ids
    inst = get_connector("rss")
    assert isinstance(inst, RssConnector)
    assert inst.credential() == "public"  # no env var, no gate


def test_read_only_never_requires_confirmation():
    assert RssConnector.requires_confirmation is False
    assert not any(c.write for c in RssConnector.capabilities)
    assert not any(o.write for o in RssConnector.operations)


def test_parse_rss():
    feed = parse_feed(RSS_SAMPLE, url_hint="https://example.test/feed.xml")
    assert feed["kind"] == "rss"
    assert feed["title"] == "Test Feed"
    assert feed["entry_count"] == 2
    first = feed["entries"][0]
    assert first["title"] == "First post"
    assert first["link"] == "https://example.test/1"
    assert "2026" in first["published"]


def test_parse_atom():
    feed = parse_feed(ATOM_SAMPLE)
    assert feed["kind"] == "atom"
    assert feed["entry_count"] == 1
    entry = feed["entries"][0]
    assert entry["title"] == "Entry one"
    assert entry["link"] == "https://example.test/e1"


def test_parse_rejects_garbage():
    with pytest.raises(ConnectorAPIError):
        parse_feed(b"<html>not a feed at all")
    with pytest.raises(InvalidParams):
        parse_feed(b"")


def test_fetch_uses_real_pipeline_monkeypatched(monkeypatch):
    monkeypatch.setattr(rss_mod, "download", lambda url, timeout=20: RSS_SAMPLE)
    c = RssConnector()
    res = c.execute("fetch", {"url": "https://example.test/feed.xml", "limit": 1})
    assert res.ok is True and res.status == "ok"
    assert res.data["entry_count"] == 2
    assert len(res.data["entries"]) == 1  # limit honored
    assert res.data["fetched_at"]


def test_check_returns_newest_entry(monkeypatch):
    monkeypatch.setattr(rss_mod, "download", lambda url, timeout=20: ATOM_SAMPLE)
    c = RssConnector()
    res = c.execute("check", {"url": "https://example.test/atom.xml"})
    assert res.ok is True
    assert len(res.data["entries"]) == 1
    assert res.data["entries"][0]["title"] == "Entry one"


def test_bad_url_rejected_before_network():
    c = RssConnector()
    res = c.execute("fetch", {"url": "gopher://example.test/x"})
    assert res.ok is False and res.status == "invalid_params"
    assert res.request_made is False


def test_limit_bounds():
    c = RssConnector()
    res = c.execute("fetch", {"url": "https://example.test/f", "limit": 500})
    assert res.ok is False and res.status == "invalid_params"


def test_network_failure_is_honest(monkeypatch):
    def boom(url, timeout=20):
        raise rss_mod.ConnectorAPIError("could not reach the feed server")

    monkeypatch.setattr(rss_mod, "download", boom)
    c = RssConnector()
    res = c.execute("fetch", {"url": "https://example.test/f"})
    assert res.ok is False and res.status == "api_error"
    assert res.request_made is False


def test_unknown_operation():
    c = RssConnector()
    res = c.execute("subscribe", {"url": "https://example.test/f"})
    assert res.ok is False and res.status == "unknown_operation"
