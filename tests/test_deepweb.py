"""Hermetic tests for levi.research.deepweb.

No live network: every test monkeypatches ``deepweb._http_get`` (the single
HTTP choke point) with fixture routers. No real HOME writes: persistence
tests pass an explicit tmp home. Follows the tests/test_entrypoints_finance.py
lesson — paths are resolved at call time, so tmp homes genuinely isolate.
"""

from __future__ import annotations

import json

import pytest

from levi.research import deepweb as dw


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

CDX_JSON = json.dumps([
    ["timestamp", "original", "statuscode", "digest"],
    ["20200101000000", "http://example.com/", "200", "aaa"],
    ["20210601000000", "http://example.com/about", "200", "bbb"],
])

AVAIL_JSON = json.dumps({
    "archived_snapshots": {
        "closest": {"available": True,
                    "url": "https://web.archive.org/web/20200101/http://example.com/",
                    "timestamp": "20200101000000"}
    }
})

CC_LINES = "\n".join([
    '{"url":"http://example.com/","timestamp":"20200101000000",'
    '"filename":"crawl.warc.gz","offset":"123"}',
    "this line is not json",
    '{"url":"http://example.com/about","timestamp":"20210601000000",'
    '"filename":"crawl2.warc.gz","offset":"456"}',
])

COLLININFO_JSON = json.dumps([{"id": "CC-MAIN-2025-30"}, {"id": "CC-MAIN-2025-21"}])

ROBOTS_TXT = """\
User-agent: *
Disallow: /private
Sitemap: https://example.com/sitemap.xml

User-agent: levi-deepweb
Disallow: /internal
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/s1.xml</loc></sitemap>
</sitemapindex>"""

URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>"""

PAGE_HTML = """<html><head><title>Example</title>
<link rel="alternate" type="application/rss+xml" href="/feed.xml">
</head><body><p>Hello world, this is a test page.</p></body></html>"""

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Ex</title>
<item><title>Post One</title><link>https://example.com/p1</link>
<description>First post</description></item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Paper Title</title><id>http://arxiv.org/abs/1234.5678</id>
<link href="http://arxiv.org/abs/1234.5678"/>
<summary>Abstract text here.</summary>
<published>2025-01-01T00:00:00Z</published></entry>
</feed>"""

DATAGOV_JSON = json.dumps({
    "result": {"results": [
        {"name": "ds-one", "title": "Dataset One", "notes": "Some notes",
         "organization": {"title": "Test Org"}}]}
})

TICKERS_JSON = json.dumps({
    "0": {"cik_str": 123, "ticker": "ABC", "title": "ABC Corp"},
    "1": {"cik_str": 456, "ticker": "XYZ", "title": "XYZ Inc"},
})

SUBMISSIONS_JSON = json.dumps({
    "filings": {"recent": {"form": ["10-K", "10-Q", "8-K"]}}
})


def _router(routes):
    """Build a fake ``_http_get(url, policy)`` matching URL substrings."""
    def fake(url, policy):
        for needle, (body, ctype) in routes:
            if needle in url:
                data = body.encode("utf-8") if isinstance(body, str) else body
                return data, ctype
        return None  # unreachable -> crawler records refusal, returns None
    return fake


def _fast_crawler(monkeypatch):
    """Patch network + crawler factory: no sleeps, no live HTTP."""
    orig = dw.PoliteCrawler
    monkeypatch.setattr(
        dw, "PoliteCrawler",
        lambda policy=None, **kw: orig(
            policy=dw.CrawlPolicy(delay_seconds=0)))
    return orig(policy=dw.CrawlPolicy(delay_seconds=0))


BASE_ROUTES = [
    ("robots.txt", (ROBOTS_TXT, "text/plain")),
    ("web.archive.org/cdx", (CDX_JSON, "application/json")),
    ("archive.org/wayback/available", (AVAIL_JSON, "application/json")),
    ("collinfo.json", (COLLININFO_JSON, "application/json")),
    ("index.commoncrawl.org/CC", (CC_LINES, "application/json")),
    ("sitemap.xml", (URLSET_XML, "application/xml")),
    ("export.arxiv.org", (ATOM_XML, "application/atom+xml")),
    ("catalog.data.gov", (DATAGOV_JSON, "application/json")),
    ("company_tickers.json", (TICKERS_JSON, "application/json")),
    ("data.sec.gov", (SUBMISSIONS_JSON, "application/json")),
    ("/feed.xml", (RSS_XML, "application/rss+xml")),
    ("example.com/a", (PAGE_HTML, "text/html")),
    ("example.com/b", (PAGE_HTML, "text/html")),
    ("example.com", (PAGE_HTML, "text/html")),
]


# --------------------------------------------------------------------------
# Boundaries
# --------------------------------------------------------------------------

def test_boundary_onion_refused():
    with pytest.raises(dw.BoundaryError):
        dw._check_boundary("http://example123.onion/page")


def test_boundary_non_http_refused():
    with pytest.raises(dw.BoundaryError):
        dw._check_boundary("ftp://example.com/file")


def test_boundary_credentials_refused():
    with pytest.raises(dw.BoundaryError):
        dw._check_boundary("https://user:pass@example.com/")


def test_boundary_loopback_refused():
    with pytest.raises(dw.BoundaryError):
        dw._check_boundary("http://127.0.0.1/admin")


def test_parse_robots_wildcard_and_specific():
    dis = dw.parse_robots(ROBOTS_TXT, dw.USER_AGENT)
    assert "/private" in dis   # via User-agent: *
    assert "/internal" in dis  # via User-agent: levi-deepweb


def test_parse_robots_ignores_other_agents():
    txt = "User-agent: googlebot\nDisallow: /x\nUser-agent: *\nDisallow: /y\n"
    dis = dw.parse_robots(txt, dw.USER_AGENT)
    assert dis == ["/y"]


# --------------------------------------------------------------------------
# PoliteCrawler
# --------------------------------------------------------------------------

def test_crawler_honors_robots_disallow(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = dw.PoliteCrawler(policy=dw.CrawlPolicy(delay_seconds=0))
    assert crawler.get("https://example.com/private/secret") is None
    assert any("robots.txt" in r["reason"]
               for r in crawler.refusals)


def test_crawler_rate_limits_per_host(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    now = [1000.0]
    slept = []
    crawler = dw.PoliteCrawler(
        policy=dw.CrawlPolicy(delay_seconds=2.0),
        clock=lambda: now[0],
        sleeper=lambda s: slept.append(s))
    crawler.get("https://example.com/a")
    crawler.get("https://example.com/b")
    assert slept and abs(slept[0] - 2.0) < 1e-9


def test_crawler_page_cap(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = dw.PoliteCrawler(
        policy=dw.CrawlPolicy(delay_seconds=0, max_pages_per_host=1))
    assert crawler.get("https://example.com/a") is not None
    assert crawler.get("https://example.com/b") is None
    assert any("cap" in r["reason"] for r in crawler.refusals)


def test_crawler_records_unreachable(monkeypatch):
    monkeypatch.setattr(dw, "_http_get",
                        lambda url, policy: (_ for _ in ()).throw(
                            dw.FetchError("boom")))
    crawler = dw.PoliteCrawler(policy=dw.CrawlPolicy(delay_seconds=0))
    assert crawler.get("https://example.com/a") is None
    assert crawler.refusals


# --------------------------------------------------------------------------
# Techniques
# --------------------------------------------------------------------------

def test_wayback_cdx_parses(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    srcs = dw.wayback_cdx("example.com/*", crawler, limit=5)
    assert len(srcs) == 2
    assert srcs[0].kind == "wayback"
    assert srcs[0].url.startswith("https://web.archive.org/web/20200101")
    assert srcs[0].retrieved_at and srcs[0].method


def test_wayback_availability_parses(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    src = dw.wayback_availability("https://example.com/", crawler)
    assert src is not None and src.kind == "wayback"


def test_wayback_availability_none_when_absent(monkeypatch):
    routes = [("archive.org/wayback/available",
               ('{"archived_snapshots":{}}', "application/json")),
              ("robots.txt", (ROBOTS_TXT, "text/plain"))]
    monkeypatch.setattr(dw, "_http_get", _router(routes))
    crawler = _fast_crawler(monkeypatch)
    assert dw.wayback_availability("https://example.com/", crawler) is None


def test_commoncrawl_parses_and_skips_bad_lines(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    srcs = dw.commoncrawl_captures("example.com/*", crawler,
                                   index="CC-MAIN-2025-30")
    assert len(srcs) == 2  # bad line skipped, not fatal
    assert srcs[0].kind == "commoncrawl"
    assert "metadata only" in srcs[0].notes


def test_commoncrawl_latest_index(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    assert dw.commoncrawl_latest_index(crawler) == "CC-MAIN-2025-30"


def test_discover_sitemaps_from_robots(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    sms = dw.discover_sitemaps("example.com", crawler)
    assert "https://example.com/sitemap.xml" in sms


def test_enumerate_sitemap_index_nested(monkeypatch):
    routes = [("robots.txt", (ROBOTS_TXT, "text/plain")),
              ("sitemap.xml", (URLSET_XML, "application/xml")),
              ("s1.xml", (URLSET_XML, "application/xml")),
              ("index.xml", (SITEMAP_INDEX_XML, "application/xml"))]
    monkeypatch.setattr(dw, "_http_get", _router(routes))
    crawler = dw.PoliteCrawler(policy=dw.CrawlPolicy(delay_seconds=0))
    urls = dw.enumerate_sitemap("https://example.com/index.xml", crawler)
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_discover_feeds_from_link_tag(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    feeds = dw.discover_feeds("https://example.com/", crawler)
    assert "https://example.com/feed.xml" in feeds


def test_feed_entries_rss_and_atom():
    rss = dw.feed_entries(RSS_XML.encode())
    assert rss[0]["title"] == "Post One"
    assert rss[0]["link"] == "https://example.com/p1"
    atom = dw.feed_entries(ATOM_XML.encode())
    assert atom[0]["title"] == "Paper Title"
    assert atom[0]["link"] == "http://arxiv.org/abs/1234.5678"


def test_arxiv_search_with_crawler(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    srcs = dw.arxiv_search("hypertext", crawler=crawler, max_results=5)
    assert len(srcs) == 1
    assert srcs[0].kind == "arxiv"
    assert "open-access" in srcs[0].notes


def test_datagov_search(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    srcs = dw.datagov_search("climate", crawler)
    assert len(srcs) == 1
    assert srcs[0].url == "https://catalog.data.gov/dataset/ds-one"


def test_sec_edgar_search(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    crawler = _fast_crawler(monkeypatch)
    srcs = dw.sec_edgar_search("ABC", crawler)
    assert len(srcs) == 1
    assert "10-K" in srcs[0].summary
    assert srcs[0].kind == "portal"


def test_extract_text_strips_markup():
    txt = dw.extract_text(PAGE_HTML.encode())
    assert "Hello world" in txt
    assert "<p>" not in txt and "<title>" not in txt


# --------------------------------------------------------------------------
# Survey + persistence + CLI
# --------------------------------------------------------------------------

def test_survey_assembles_provenance(monkeypatch):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    _fast_crawler(monkeypatch)
    survey = dw.survey_topic("hypertext", seed_domains=["example.com"],
                             max_per_source=5)
    kinds = {s.kind for s in survey.sources}
    assert {"arxiv", "portal", "wayback", "sitemap", "feed"} <= kinds
    for s in survey.sources:
        assert s.url and s.retrieved_at and s.method
    # round-trip
    again = dw.DeepSurvey.from_dict(survey.to_dict())
    assert len(again.sources) == len(survey.sources)


def test_save_survey_hermetic(tmp_path):
    survey = dw.DeepSurvey(topic="test topic")
    survey.add(dw.DeepSource(kind="page", url="https://example.com/",
                             retrieved_at="2026-01-01T00:00:00+00:00",
                             method="test"))
    path = dw.save_survey(survey, home=tmp_path)
    assert path.parent.parent == tmp_path / ".levi" / "research"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["topic"] == "test topic"


def test_cli_boundaries(capsys):
    assert dw.main(["boundaries"]) == 0
    assert "hard boundaries" in capsys.readouterr().out.lower()


def test_cli_survey_json_mocked(monkeypatch, capsys):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    _fast_crawler(monkeypatch)
    assert dw.main(["--json", "survey", "hypertext",
                    "--domain", "example.com", "--max", "3"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["topic"] == "hypertext"
    assert data["sources"]


def test_cli_wayback_mocked(monkeypatch, capsys):
    monkeypatch.setattr(dw, "_http_get", _router(BASE_ROUTES))
    _fast_crawler(monkeypatch)
    assert dw.main(["wayback", "--url", "example.com/*",
                    "--limit", "5"]) == 0
    assert "web.archive.org" in capsys.readouterr().out


def test_deepsource_requires_url():
    with pytest.raises(ValueError):
        dw.DeepSource.from_dict({"kind": "page", "url": "  "})


# --------------------------------------------------------------------------
# SSRF redirect hardening: every redirect hop is re-checked against the
# hard boundaries (_BoundaryRedirectHandler).
# --------------------------------------------------------------------------

def test_redirect_to_loopback_refused():
    handler = dw._BoundaryRedirectHandler()
    with pytest.raises(dw.BoundaryError):
        handler.redirect_request(
            None, None, 302, "Found", {}, "http://127.0.0.1/secret")


def test_redirect_to_onion_refused():
    handler = dw._BoundaryRedirectHandler()
    with pytest.raises(dw.BoundaryError):
        handler.redirect_request(
            None, None, 302, "Found", {}, "http://example.onion/")


def test_redirect_to_credential_url_refused():
    handler = dw._BoundaryRedirectHandler()
    with pytest.raises(dw.BoundaryError):
        handler.redirect_request(
            None, None, 302, "Found", {}, "https://user:pass@example.com/")


def test_redirect_to_public_url_allowed():
    import urllib.request
    handler = dw._BoundaryRedirectHandler()
    req = urllib.request.Request("http://example.com/")
    out = handler.redirect_request(
        req, None, 302, "Found", {}, "https://example.org/next")
    assert out.get_full_url() == "https://example.org/next"
