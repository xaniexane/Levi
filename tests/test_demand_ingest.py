"""Tests for levi.demand.ingest — stdlib-only Layer 1 ingestion.

No real network in these tests: urllib.request.urlopen is monkeypatched.
Fixtures only — no invented demand data.
"""

import json
import urllib.error
import urllib.request

import pytest

from levi.demand import ingest


class _FakeResp:
    """Minimal urlopen response: context manager + read() + status."""

    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _json_resp(obj, status=200):
    return _FakeResp(json.dumps(obj).encode("utf-8"), status)


def _down(*args, **kwargs):
    raise urllib.error.URLError("network down (fixture)")


# ---- constants --------------------------------------------------------------


def test_original_constants_intact():
    assert len(ingest.INDUSTRIES) == 12
    assert "Technology / SaaS" in ingest.INDUSTRIES
    assert ingest.SIGNAL_TYPES == [
        "pain_point",
        "trend",
        "regulatory_shift",
        "tech_emergence",
    ]
    assert ingest.CONFIDENCE_LEVELS == ["high", "medium", "low"]
    assert len(ingest.PAIN_PATTERNS) == 7


def test_data_sources_keyless_only():
    ids = {s["id"] for s in ingest.DATA_SOURCES}
    assert ids == {
        "social",
        "jobs",
        "reddit",
        "stackoverflow",
        "github",
        "arxiv",
        "census",
        "news",
    }
    # BLS deliberately excluded: registration key required, no keyless path.
    assert "bls" not in ids


# ---- classifiers ------------------------------------------------------------


def test_classify_industry():
    assert (
        ingest.classify_industry("fintech startup for banking") == "Finance / FinTech"
    )
    assert ingest.classify_industry("I need a better health app") == "Health / Wellness"
    assert ingest.classify_industry("solar panel installers") == "Energy / CleanTech"
    assert (
        ingest.classify_industry("something with no keywords xyz")
        == "Technology / SaaS"
    )


def test_classify_signal_pain_patterns():
    assert (
        ingest.classify_signal("i wish there was a better invoicing tool", "social")
        == "pain_point"
    )
    assert ingest.classify_signal("frustrated with my CRM", "jobs") == "pain_point"
    assert (
        ingest.classify_signal("looking for alternative to X", "github") == "pain_point"
    )


def test_classify_signal_source_fallback():
    assert ingest.classify_signal("some post", "reddit") == "pain_point"
    assert ingest.classify_signal("some post", "stackoverflow") == "pain_point"
    assert ingest.classify_signal("some post", "jobs") == "trend"
    assert ingest.classify_signal("some post", "social") == "trend"
    assert ingest.classify_signal("some post", "github") == "tech_emergence"
    assert ingest.classify_signal("some post", "arxiv") == "tech_emergence"
    assert ingest.classify_signal("some post", "census") == "regulatory_shift"


# ---- graceful failure ---------------------------------------------------------


def test_http_get_never_raises(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _down)
    assert ingest._http_get("https://example.com") == (None, "")


@pytest.mark.parametrize(
    "fetcher",
    [
        ingest.fetch_hackernews,
        ingest.fetch_job_signals,
        ingest.fetch_reddit_signals,
        ingest.fetch_stackoverflow_signals,
        ingest.fetch_github_signals,
        ingest.fetch_arxiv_signals,
        ingest.fetch_census_signals,
    ],
)
def test_fetchers_fail_gracefully(monkeypatch, fetcher):
    monkeypatch.setattr(urllib.request, "urlopen", _down)
    assert fetcher("test query") == []


def test_fetchers_reject_bad_status(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResp(b"nope", 429)
    )
    assert ingest.fetch_hackernews("x") == []
    assert ingest.fetch_github_signals("x") == []


def test_fetchers_reject_bad_json(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResp(b"<html>not json", 200)
    )
    assert ingest.fetch_hackernews("x") == []
    assert ingest.fetch_stackoverflow_signals("x") == []


# ---- mocked parsing -----------------------------------------------------------


def test_fetch_hackernews_parses(monkeypatch):
    payload = {
        "hits": [
            {
                "title": "Show HN: offline-first notes",
                "objectID": "123",
                "points": 42,
                "num_comments": 7,
            },
            {"title": "", "objectID": "124"},  # skipped: no title
        ]
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _json_resp(payload))
    signals = ingest.fetch_hackernews("notes")
    assert len(signals) == 1
    sig = signals[0]
    assert sig["source"] == "social"
    assert sig["text"] == "Show HN: offline-first notes"
    assert "item?id=123" in sig["url"]
    assert sig["metadata"]["points"] == 42


def test_fetch_reddit_parses(monkeypatch):
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "i wish invoicing was simpler",
                        "permalink": "/r/smallbusiness/abc",
                        "score": 10,
                        "subreddit": "smallbusiness",
                        "num_comments": 3,
                    }
                },
                {"data": {"title": "", "permalink": "/r/x/y"}},  # skipped
            ]
        }
    }
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _json_resp(payload))
    signals = ingest.fetch_reddit_signals("invoicing")
    assert len(signals) == 1
    assert signals[0]["source"] == "reddit"
    assert signals[0]["url"].startswith("https://reddit.com/r/")


def test_fetch_arxiv_parses(monkeypatch):
    body = (
        b"<feed><title>arXiv Query</title><id>http://arxiv.org/</id></feed>"
        b"<entry><title>  Offline Agents  </title><id>http://arxiv.org/abs/1</id></entry>"
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResp(body, 200))
    signals = ingest.fetch_arxiv_signals("agents")
    assert len(signals) == 1
    assert signals[0]["text"] == "Offline Agents"
    assert signals[0]["source"] == "arxiv"


def test_fetch_census_parses(monkeypatch):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: _json_resp(
            [["NAME", "B19013_001E", "us"], ["United States", "75000", "1"]]
        ),
    )
    signals = ingest.fetch_census_signals()
    assert len(signals) == 1
    assert signals[0]["source"] == "census"
    assert "75,000" in signals[0]["text"]


# ---- ingest_signals -----------------------------------------------------------


def _canned_raw():
    return [
        {
            "source": "social",
            "source_name": "Hacker News",
            "text": "i wish dispatch software was simpler",
            "url": "u1",
            "metadata": {},
        },
        {
            "source": "reddit",
            "source_name": "Reddit",
            "text": "i wish dispatch software was simpler for truckers",
            "url": "u2",
            "metadata": {},
        },
        {
            "source": "github",
            "source_name": "GitHub",
            "text": "dispatchkit: offline dispatch toolkit",
            "url": "u3",
            "metadata": {},
        },
    ]


def test_ingest_signals_labels_and_confidence(monkeypatch):
    monkeypatch.setattr(ingest, "_FETCHERS", [("Canned", lambda q: _canned_raw())])
    signals = ingest.ingest_signals("dispatch")
    assert len(signals) == 3
    for sig in signals:
        assert sig["label"] == "OBSERVED"  # real fetched text
        assert sig["id"] and sig["timestamp"] and sig["keywords"]
    by_source = {s["source"]: s for s in signals}
    assert by_source["social"]["confidence"] == "high"
    assert by_source["reddit"]["confidence"] == "high"
    assert by_source["github"]["confidence"] == "medium"
    assert by_source["social"]["signal_type"] == "pain_point"
    assert by_source["github"]["signal_type"] == "tech_emergence"


def test_ingest_signals_industry_filter(monkeypatch):
    monkeypatch.setattr(ingest, "_FETCHERS", [("Canned", lambda q: _canned_raw())])
    signals = ingest.ingest_signals("dispatch", focus_industries=["Health / Wellness"])
    assert signals == []  # nothing matches the focus list


def test_ingest_signals_rejects_empty_query():
    with pytest.raises(ValueError):
        ingest.ingest_signals("   ")
