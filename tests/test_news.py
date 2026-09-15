"""Tests for current-events ingestion (dated recall, not live awareness)."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


NEWS_DIR = (
    Path(__file__).resolve().parent.parent / "core" / "levi" / "knowledge" / "news"
)
sys.path.insert(0, str(NEWS_DIR))
import refresh as news_refresh  # noqa: E402

FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Alpha breakthrough</title><link>https://example.com/a</link>
<description>Scientists did a thing.</description></item>
<item><title>Beta markets rally</title><link>https://example.com/b</link>
<description>Numbers went up.</description></item>
</channel></rss>"""


def test_parse_rss_fixture():
    items = news_refresh._parse_rss(FEED.encode())
    assert len(items) == 2
    assert items[0]["title"] == "Alpha breakthrough"
    assert items[0]["url"] == "https://example.com/a"
    assert "Scientists" in items[0]["summary"]
    assert news_refresh._parse_rss(b"not xml at all <<<") == []


def test_dedupe_within_and_across_days(tmp_path, monkeypatch):
    days = tmp_path / "days"
    days.mkdir()
    (days / "2026-09-14.jsonl").write_text(
        json.dumps(
            {
                "date": "2026-09-14",
                "source": "t",
                "title": "Old",
                "summary": "",
                "url": "https://example.com/a",
            }
        )
        + "\n"
    )
    monkeypatch.setattr(news_refresh, "DAYS", days)
    monkeypatch.setattr(news_refresh, "SOURCES_JSON", tmp_path / "sources.json")
    monkeypatch.setattr(
        news_refresh,
        "SOURCES",
        [{"id": "t", "kind": "rss", "url": "https://example.com/feed"}],
    )
    monkeypatch.setattr(news_refresh, "_fetch", lambda url: FEED.encode())
    out = news_refresh.refresh(day="2026-09-15", limit=10)
    assert out["new_records"] == 1  # /a deduped against yesterday, /b new
    recs = (days / "2026-09-15.jsonl").read_text().strip().splitlines()
    assert len(recs) == 1
    assert json.loads(recs[0])["url"] == "https://example.com/b"
    assert json.loads(recs[0])["date"] == "2026-09-15"


def test_refresh_handles_dead_source_gracefully(tmp_path, monkeypatch):
    class Dead(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(500)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Dead)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        days = tmp_path / "days"
        days.mkdir()
        monkeypatch.setattr(news_refresh, "DAYS", days)
        monkeypatch.setattr(news_refresh, "SOURCES_JSON", tmp_path / "sources.json")
        monkeypatch.setattr(
            news_refresh,
            "SOURCES",
            [
                {
                    "id": "dead-src",
                    "kind": "rss",
                    "url": f"http://127.0.0.1:{srv.server_port}/feed",
                },
                {"id": "live-src", "kind": "rss", "url": "https://example.com/feed"},
            ],
        )
        monkeypatch.setattr(
            news_refresh,
            "_fetch",
            lambda url: None if "127.0.0.1" in url else FEED.encode(),
        )
        out = news_refresh.refresh(day="2026-09-15", limit=10)
        assert out["new_records"] == 2  # live source still ingested
        statuses = json.loads((tmp_path / "sources.json").read_text())
        assert statuses["dead-src"].startswith("dead")
        assert statuses["live-src"].startswith("ok")
    finally:
        srv.shutdown()


def test_news_tools_return_date_stamped_results():
    from levi.agent.tools import build_default_registry, ExecContext

    reg = build_default_registry()
    ctx = ExecContext()
    latest = reg.execute("news_latest", {"limit": "3"}, ctx)
    assert latest.ok
    # Either empty-corpus guidance or date-stamped items — never dateless items
    if "no ingested news" not in latest.output:
        assert "[20" in latest.output  # [YYYY-MM-DD] stamp present
    search = reg.execute("news_search", {"query": "markets"}, ctx)
    assert search.ok
    bad = reg.execute("news_search", {"query": ""}, ctx)
    assert not bad.ok
