"""Hermetic tests for levi.honestsearch (mocked fetcher, tmp HOME)."""

import inspect
import json
import math

import pytest

from levi.honestsearch import SHELF, search
from levi.honestsearch.crawl import SiteCrawl, extract_links, title_of
from levi.honestsearch.index import InvertedIndex, tokenize
from levi.honestsearch.model import Document, doc_id_for
from levi.honestsearch.rank import (
    DEFAULT_WEIGHTS,
    explain,
    normalize_weights,
    pagerank,
    parse_weights,
    text_scores,
)


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def _doc(url, title, text, outlinks=()):
    return Document(
        doc_id=doc_id_for(url),
        url=url,
        title=title,
        text=text,
        outlinks=list(outlinks),
        source="file",
    )


def _sample_index():
    index = InvertedIndex()
    index.add(
        _doc(
            "https://x.test/a",
            "Alpha guide",
            "alpha beta alpha gamma",
            ["https://x.test/b"],
        )
    )
    index.add(
        _doc("https://x.test/b", "Beta notes", "beta beta delta", ["https://x.test/c"])
    )
    index.add(
        _doc(
            "https://x.test/c", "Third page", "gamma gamma gamma", ["https://x.test/a"]
        )
    )
    index.add(
        _doc("https://x.test/d", "Lonely delta", "delta unrelated words here", [])
    )
    return index


# ---------------------------------------------------------------------------
# PageRank math
# ---------------------------------------------------------------------------


def test_shelf_shape():
    assert SHELF["name"] == "honestsearch"
    assert SHELF["summary"] and SHELF["items"]


def test_pagerank_sums_to_one():
    ranks = pagerank({"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"]})
    assert math.isclose(sum(ranks.values()), 1.0, rel_tol=1e-9)


def test_pagerank_known_graph_order():
    # a->b, b->c, c->a, d->a. d has no inlinks (rank = random-jump share
    # only); the extra inbound link lifts a, and the lift decays around
    # the cycle: a > b > c > d. (Verified against an exact linear solve.)
    ranks = pagerank({"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"]})
    order = sorted(ranks, key=ranks.get, reverse=True)
    assert order == ["a", "b", "c", "d"]


def test_pagerank_all_dangling_is_uniform():
    ranks = pagerank({"a": [], "b": [], "c": []})
    assert all(math.isclose(v, 1 / 3, rel_tol=1e-6) for v in ranks.values())


def test_pagerank_empty_and_bad_damping():
    assert pagerank({}) == {}
    with pytest.raises(ValueError):
        pagerank({"a": ["b"], "b": []}, damping=1.5)


def test_pagerank_ignores_external_neighbors():
    ranks = pagerank({"a": ["b", "https://outside.test/x"], "b": ["a"]})
    assert math.isclose(sum(ranks.values()), 1.0, rel_tol=1e-9)
    assert set(ranks) == {"a", "b"}


# ---------------------------------------------------------------------------
# Index + text scoring
# ---------------------------------------------------------------------------


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("The Quick BROWN fox, a!") == ["quick", "brown", "fox"]


def test_index_add_search_roundtrip():
    index = _sample_index()
    assert len(index) == 4
    assert index.doc_freq("gamma") == 2  # in a and c
    assert index.doc_freq("nosuchterm") == 0


def test_index_remove_cleans_postings():
    index = _sample_index()
    doc_id = doc_id_for("https://x.test/d")
    assert index.remove(doc_id)
    assert len(index) == 3
    assert index.doc_freq("unrelated") == 0
    assert not index.remove("missing")


def test_index_readd_same_url_replaces():
    index = _sample_index()
    index.add(_doc("https://x.test/d", "Lonely delta v2", "completely new words"))
    assert len(index) == 4
    assert index.doc_freq("unrelated") == 0
    assert index.doc_freq("completely") == 1


def test_text_scores_prefers_term_frequency():
    index = _sample_index()
    scores = text_scores(index, ["gamma"])
    # c mentions gamma 3x, a mentions it 1x
    assert (
        scores[doc_id_for("https://x.test/c")] > scores[doc_id_for("https://x.test/a")]
    )
    assert doc_id_for("https://x.test/b") not in scores


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


def test_normalize_weights():
    assert normalize_weights({"text": 3, "link": 1}) == {"text": 0.75, "link": 0.25}


def test_normalize_weights_rejects_bad():
    for bad in (
        {"text": -1, "link": 1},
        {"text": 0, "link": 0},
        {"text": float("nan"), "link": 1},
        {"text": 1},
    ):
        with pytest.raises(ValueError):
            normalize_weights(bad)


def test_parse_weights():
    assert parse_weights("text=0.8,link=0.2") == {"text": 0.8, "link": 0.2}
    with pytest.raises(ValueError):
        parse_weights("text=0.8,vibes=0.2")
    with pytest.raises(ValueError):
        parse_weights("garbage")


# ---------------------------------------------------------------------------
# search(): combination, explanations, unpersonalized guarantee
# ---------------------------------------------------------------------------


def test_search_ranks_and_explains():
    index = _sample_index()
    results = search(index, "gamma guide", top_k=10)
    assert results
    top = results[0]
    assert top.doc.url == "https://x.test/a"  # matches both terms
    # contributions must sum to the total, exactly as explain() reports
    assert math.isclose(
        top.total, top.contributions["text"] + top.contributions["link"], rel_tol=1e-12
    )
    text = explain(top, DEFAULT_WEIGHTS)
    assert "text" in text and "link" in text and "gamma" in text


def test_search_weights_change_order():
    # Dedicated corpus: p1 says "target" 6x (high text score) but nobody
    # links to it; p2 says it 1x but p1 and p3 both link to it (high link
    # score). The declared weights must be able to flip the winner.
    index = InvertedIndex()
    p1 = "https://w.test/1"
    p2 = "https://w.test/2"
    p3 = "https://w.test/3"
    index.add(_doc(p1, "One", "target " * 6, [p2]))
    index.add(_doc(p2, "Two", "target", []))
    index.add(_doc(p3, "Three", "filler filler", [p2]))
    text_only = search(index, "target", weights={"text": 1.0, "link": 0.0})
    link_only = search(index, "target", weights={"text": 0.0, "link": 1.0})
    assert [r.doc.url for r in text_only] == [p1, p2]
    assert [r.doc.url for r in link_only] == [p2, p1]
    assert link_only[0].contributions["text"] == 0.0
    assert text_only[0].contributions["link"] == 0.0


def test_search_empty_query_or_index():
    assert search(_sample_index(), "   ") == []
    assert search(InvertedIndex(), "gamma") == []


def test_search_is_deterministic():
    index = _sample_index()
    first = [(r.doc.doc_id, r.total) for r in search(index, "gamma delta")]
    second = [(r.doc.doc_id, r.total) for r in search(index, "gamma delta")]
    assert first == second


def test_search_takes_no_profile_by_construction():
    params = inspect.signature(search).parameters
    assert not any(
        key
        in ("profile", "user", "user_id", "history", "personalize", "personalization")
        for key in params
    ), "ranking must not accept a profile parameter"


def test_unpersonalized_results_ignore_stored_profile(monkeypatch, tmp_path):
    """Pollute the store with fake profile data; the order must not move."""
    _herm(monkeypatch, tmp_path)
    import levi.honestsearch.__main__ as cli

    (tmp_path / "notes.md").write_text("gamma rays and alpha particles")
    assert cli.main(["add", str(tmp_path / "notes.md")]) == 0
    before = [
        (r.doc.doc_id, round(r.total, 9))
        for r in search(
            __import__("levi.honestsearch.store", fromlist=["load_index"]).load_index(),
            "gamma",
        )
    ]
    # A giant would re-rank on this. We must not.
    store = tmp_path / ".levi" / "honestsearch"
    (store / "user_profile.json").write_text(
        json.dumps(
            {
                "user_id": "chauncey",
                "interests": ["sports", "celebrity gossip"],
                "click_history": ["https://ads.test/x"] * 500,
            }
        )
    )
    (store / "ad_auction.json").write_text(json.dumps({"bids": {"x": 999}}))
    import importlib

    store_mod = importlib.import_module("levi.honestsearch.store")
    after = [
        (r.doc.doc_id, round(r.total, 9))
        for r in search(store_mod.load_index(), "gamma")
    ]
    assert before == after


# ---------------------------------------------------------------------------
# Crawl (fake fetcher — no network)
# ---------------------------------------------------------------------------


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages  # url -> html
        self.refusals = []

    def get(self, url):
        if url in self.pages:
            return self.pages[url].encode(), "text/html; charset=utf-8"
        self.refusals.append({"url": url, "reason": "404 in fake fetcher"})
        return None


PAGES = {
    "https://site.test/": (
        "<html><head><title>Home</title></head><body>"
        '<a href="/a">A</a><a href="/b">B</a>'
        '<a href="https://other.test/x">X</a></body></html>'
    ),
    "https://site.test/a": (
        "<html><head><title>Page A</title></head><body>alpha content "
        '<a href="/b">B</a></body></html>'
    ),
    "https://site.test/b": (
        "<html><head><title>Page B</title></head><body>beta content</body></html>"
    ),
}


def test_extract_links_resolves_and_dedups():
    links = extract_links(PAGES["https://site.test/"].encode(), "https://site.test/")
    assert links == [
        "https://site.test/a",
        "https://site.test/b",
        "https://other.test/x",
    ]


def test_title_of():
    assert title_of(b"<title>  Hello  World </title>") == "Hello World"
    assert title_of(b"no title here") == ""


def test_crawl_finds_pages_and_links():
    crawl = SiteCrawl(fetcher=FakeFetcher(PAGES), max_pages=10, max_depth=2)
    docs, report = crawl.crawl(["https://site.test/"])
    by_url = {d.url: d for d in docs}
    assert set(by_url) == {
        "https://site.test/",
        "https://site.test/a",
        "https://site.test/b",
    }
    assert by_url["https://site.test/"].title == "Home"
    assert "https://site.test/a" in by_url["https://site.test/"].outlinks
    assert report["pages"] == 3
    # out-of-scope host skipped under default host scope
    assert report["skipped_out_of_scope"] == 1


def test_crawl_records_refusals_honestly():
    pages = dict(PAGES)
    pages["https://site.test/"] = pages["https://site.test/"].replace(
        "</body>", '<a href="/missing">M</a></body>'
    )
    crawl = SiteCrawl(fetcher=FakeFetcher(pages), max_pages=10, max_depth=2)
    docs, report = crawl.crawl(["https://site.test/"])
    assert len(docs) == 3  # missing page not fabricated
    assert any(r["url"] == "https://site.test/missing" for r in report["refusals"])


def test_crawl_respects_max_depth_and_pages():
    crawl = SiteCrawl(fetcher=FakeFetcher(PAGES), max_pages=10, max_depth=0)
    docs, _ = crawl.crawl(["https://site.test/"])
    assert [d.url for d in docs] == ["https://site.test/"]
    crawl = SiteCrawl(fetcher=FakeFetcher(PAGES), max_pages=2, max_depth=5)
    docs, _ = crawl.crawl(["https://site.test/"])
    assert len(docs) == 2


def test_crawl_rejects_bad_config():
    with pytest.raises(ValueError):
        SiteCrawl(fetcher=FakeFetcher({}), scope="galaxy")
    with pytest.raises(ValueError):
        SiteCrawl(fetcher=FakeFetcher({}), max_pages=0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero():
    from levi.honestsearch.__main__ import main

    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_cli_add_query_explain_weights(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    from levi.honestsearch.__main__ import main

    (tmp_path / "alpha.md").write_text("# Alpha\nrepeat repeat repeat gamma")
    (tmp_path / "beta.md").write_text("# Beta\ngamma once")
    assert main(["add", str(tmp_path / "alpha.md"), str(tmp_path / "beta.md")]) == 0
    assert main(["query", "repeat", "--explain"]) == 0
    out = capsys.readouterr().out
    assert "unpersonalized" in out
    assert "contribution" in out
    assert "alpha" in out  # title falls back to the file stem
    # weights round-trip
    assert main(["weights", "set", "text=0.8,link=0.2"]) == 0
    assert main(["weights", "show"]) == 0
    assert "text=0.80" in capsys.readouterr().out
    assert main(["stats"]) == 0
    assert "documents: 2" in capsys.readouterr().out
    # bad weights rejected, not silently accepted
    assert main(["weights", "set", "text=-1,link=1"]) == 2


def test_cli_query_empty_index(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    from levi.honestsearch.__main__ import main

    assert main(["query", "anything"]) == 1
    assert "empty" in capsys.readouterr().out


def test_cli_export(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    from levi.honestsearch.__main__ import main

    (tmp_path / "n.md").write_text("hello world")
    assert main(["add", str(tmp_path / "n.md")]) == 0
    out = tmp_path / "export.json"
    assert main(["export", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["documents"] and "weights" in payload
