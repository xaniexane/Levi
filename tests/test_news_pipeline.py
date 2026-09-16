"""Hermetic tests for the news pipeline: Atom parsing, title-hash dedup,
URL normalization, ranked search, failure honesty, and the out-of-weights
guard. No live network — the HTTP layer is monkeypatched throughout."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

NEWS_DIR = (
    Path(__file__).resolve().parent.parent / "core" / "levi" / "knowledge" / "news"
)
sys.path.insert(0, str(NEWS_DIR))
import refresh as news_refresh  # noqa: E402
from levi.knowledge.news import guard, search  # noqa: E402

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Alpha breakthrough</title><link>https://example.com/a</link>
<description>Scientists did a thing.</description></item>
<item><title>Beta markets rally</title><link>https://example.com/b?at_medium=RSS</link>
<description>Numbers went up.</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Test Atom</title>
<entry><title>Atom headline story</title>
<link rel="alternate" href="https://example.com/atom1"/>
<summary>Atom world keeps turning.</summary></entry>
<entry><title>No link, dropped</title>
<summary>Entries without a link are skipped.</summary></entry>
</feed>"""


# -- parsing ----------------------------------------------------------------
def test_parse_atom_fixture():
    items = news_refresh._parse_rss(ATOM.encode())
    assert len(items) == 1
    assert items[0]["title"] == "Atom headline story"
    assert items[0]["url"] == "https://example.com/atom1"
    assert "turning" in items[0]["summary"]
    assert news_refresh._parse_rss(b"\x00\x01 not a feed") == []


def test_atom_entry_uses_alternate_link():
    feed = ATOM.replace('rel="alternate"', 'rel="self"', 1)
    items = news_refresh._parse_rss(feed.encode())
    assert items == []  # non-alternate link only → no usable URL → dropped


# -- dedup ------------------------------------------------------------------
def test_norm_url_strips_tracking_params():
    a = news_refresh._norm_url(
        "https://www.bbc.co.uk/news/x?at_medium=RSS&at_campaign=rss"
    )
    b = news_refresh._norm_url("https://WWW.BBC.CO.UK/news/x/")
    assert a == b


def test_title_key_is_case_and_punct_insensitive():
    k1 = news_refresh._title_key("Hello, World: A Breakthrough!")
    k2 = news_refresh._title_key("hello world a breakthrough")
    assert k1 == k2
    assert news_refresh._title_key("something else entirely") != k1


def _isolated(monkeypatch, tmp_path, sources, fetch):
    days = tmp_path / "days"
    days.mkdir()
    monkeypatch.setattr(news_refresh, "DAYS", days)
    monkeypatch.setattr(news_refresh, "SOURCES_JSON", tmp_path / "sources.json")
    monkeypatch.setattr(news_refresh, "SOURCES", sources)
    monkeypatch.setattr(news_refresh, "_fetch", fetch)
    return days


def test_dedup_by_normalized_url_and_title_hash(tmp_path, monkeypatch):
    """Same story under two URLs (one with tracking params, one bare) and
    the same title under a different URL are each stored exactly once."""
    days = _isolated(
        monkeypatch,
        tmp_path,
        [{"id": "s", "kind": "rss", "url": "https://example.com/feed"}],
        lambda url: RSS.encode(),
    )
    feed2 = RSS.replace(
        "https://example.com/a", "https://example.com/a?utm_source=x"
    ).replace("https://example.com/b?at_medium=RSS", "https://example.com/other-b-url")
    # first pass: 2 records
    out = news_refresh.refresh(day="2026-09-15", limit=10)
    assert out["new_records"] == 2
    # second pass, same stories under rewritten URLs: nothing new
    monkeypatch.setattr(news_refresh, "_fetch", lambda url: feed2.encode())
    out = news_refresh.refresh(day="2026-09-16", limit=10)
    assert out["new_records"] == 0
    assert not (days / "2026-09-16.jsonl").exists()


# -- failure honesty ----------------------------------------------------------
def test_dead_source_recorded_never_fabricated(tmp_path, monkeypatch):
    def fetch(url):
        return None if "dead" in url else RSS.encode()

    _isolated(
        monkeypatch,
        tmp_path,
        [
            {"id": "dead-src", "kind": "rss", "url": "https://dead.example/feed"},
            {"id": "live-src", "kind": "rss", "url": "https://live.example/feed"},
        ],
        fetch,
    )
    out = news_refresh.refresh(day="2026-09-15", limit=10)
    assert out["new_records"] == 2
    statuses = json.loads((tmp_path / "sources.json").read_text())
    assert statuses["dead-src"].startswith("dead")
    assert statuses["live-src"].startswith("ok")
    # nothing was invented for the dead source
    days_file = tmp_path / "days" / "2026-09-15.jsonl"
    recs = [json.loads(ln) for ln in days_file.read_text().splitlines()]
    assert all(r["source"] == "live-src" for r in recs)


# -- search ranking -----------------------------------------------------------
def _write_days(days: Path, mapping: dict[str, list[dict]]):
    for day, recs in mapping.items():
        days.mkdir(parents=True, exist_ok=True)
        with (days / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")


def _rec(day, title, summary="", source="t", url=None):
    return {
        "date": day,
        "source": source,
        "title": title,
        "summary": summary,
        "url": url or f"https://example.com/{abs(hash(title)) % 999999}",
    }


@pytest.fixture()
def ranked_days(tmp_path):
    days = tmp_path / "days"
    _write_days(
        days,
        {
            "2026-09-16": [
                _rec(
                    "2026-09-16",
                    "Quantum error correction milestone",
                    "A lab reports a logical qubit that survives longer.",
                ),
                _rec(
                    "2026-09-16",
                    "Markets rally on tech earnings",
                    "Quantum computing stocks jumped on the news.",
                ),
                _rec(
                    "2026-09-16",
                    "Error correction in quantum devices",
                    "Progress on a hard problem, years from product.",
                ),
            ],
            "2026-01-01": [
                _rec(
                    "2026-01-01",
                    "Quantum error correction milestone",
                    "The same headline eight months ago.",
                ),
            ],
        },
    )
    return days


def test_search_ranks_title_over_summary(ranked_days):
    hits = search.search_news("quantum", days_dir=ranked_days, today=date(2026, 9, 16))
    assert hits
    titles = [h["title"] for h in hits]
    # fresh title matches outrank the fresh summary-only match ...
    assert titles.index("Markets rally on tech earnings") > titles.index(
        "Error correction in quantum devices"
    )
    # ... and everything outranks the same headline from eight months ago
    assert hits[-1]["date"] == "2026-01-01"
    assert hits[0]["score"] > hits[-1]["score"]


def test_search_exact_phrase_bonus(ranked_days):
    hits = search.search_news(
        "quantum error correction", days_dir=ranked_days, today=date(2026, 9, 16)
    )
    assert hits[0]["title"] == "Quantum error correction milestone"


def test_search_recency_weights_fresh_higher(ranked_days):
    hits = search.search_news(
        "quantum error correction milestone",
        days_dir=ranked_days,
        today=date(2026, 9, 16),
    )
    same = [h for h in hits if h["title"] == "Quantum error correction milestone"]
    assert len(same) == 2
    fresh = [h for h in same if h["date"] == "2026-09-16"][0]
    stale = [h for h in same if h["date"] == "2026-01-01"][0]
    assert fresh["score"] > stale["score"]
    assert stale["age_days"] > 200


def test_search_short_tokens_count_and_empty_query_is_empty(ranked_days):
    hits = search.search_news(
        "AI quantum", days_dir=ranked_days, today=date(2026, 9, 16)
    )
    assert any("quantum" in h["title"].lower() for h in hits)  # "AI" not required
    assert search.search_news("", days_dir=ranked_days) == []
    assert search.search_news("the and or", days_dir=ranked_days) == []
    assert search.search_news("quantum", days_dir=Path("/nonexistent")) == []


def test_corpus_range_is_honest(tmp_path):
    assert search.corpus_range(tmp_path / "nope") == "empty"
    days = tmp_path / "days"
    _write_days(
        days,
        {
            "2026-09-15": [_rec("2026-09-15", "T")],
            "2026-09-16": [_rec("2026-09-16", "U")],
        },
    )
    assert search.corpus_range(days) == "2026-09-15..2026-09-16 (2 records)"


# -- out-of-weights guard ------------------------------------------------------
def test_guard_detects_news_records(tmp_path):
    p = tmp_path / "corpus.jsonl"
    p.write_text(
        json.dumps({"text": "stable knowledge"})
        + "\n"
        + json.dumps(
            {
                "date": "2026-09-16",
                "source": "t",
                "title": "T",
                "summary": "S",
                "url": "https://example.com/x",
            }
        )
        + "\n"
    )
    assert not guard.looks_like_news_record({"text": "stable knowledge"})
    assert guard.looks_like_news_record(
        {
            "date": "d",
            "source": "s",
            "title": "t",
            "summary": "s",
            "url": "https://example.com/x",
        }
    )
    with pytest.raises(guard.GuardError, match="never baked into weights"):
        guard.assert_no_news_records(p)


def test_guard_passes_clean_corpus(tmp_path):
    p = tmp_path / "corpus.jsonl"
    p.write_text(
        json.dumps({"text": "stable knowledge one"})
        + "\n\n"
        + json.dumps({"text": "stable knowledge two"})
        + "\n"
    )
    assert guard.assert_no_news_records(p) == 2


def test_guard_holds_on_real_training_corpus():
    academy = (
        Path(__file__).resolve().parent.parent
        / "core"
        / "levi"
        / "brain"
        / "train"
        / "corpus_academy.jsonl"
    )
    if not academy.exists():
        pytest.skip("no training corpus present")
    scanned = guard.assert_no_news_records(academy)  # raises if news leaked in
    assert scanned > 0
