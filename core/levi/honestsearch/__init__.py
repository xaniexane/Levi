"""Honest Search — clean-room link-graph ranking over a local index.

REMIX DELTA: Google auctions ads against the *person*, not the query —
personalization and ad load are load-bearing for its business, so it
cannot ship neutrality. LEVI inverts it: a polite crawler (rate-limited,
robots-aware, reusing ``levi.research.deepweb.PoliteCrawler``) fills a
*local* inverted index, and ranking is clean-room math over that corpus —
tf-idf text match plus a PageRank-style link graph — with a genuine
unpersonalized mode. There is no user profile anywhere in the ranking
path: ``rank.search()`` structurally accepts no profile, and the tests
prove it. Every result ships an explanation naming which signals
contributed and by how much.

Layout:
    model.py   Document record
    crawl.py   polite BFS crawl -> Documents (injectable fetcher)
    index.py   local inverted index, JSON-persisted under ~/.levi
    rank.py    PageRank + tf-idf + weighted combination + explanations
    store.py   call-time home paths, weight persistence
"""

from __future__ import annotations

from levi.honestsearch.crawl import SiteCrawl, extract_links, title_of
from levi.honestsearch.index import InvertedIndex, tokenize
from levi.honestsearch.model import Document
from levi.honestsearch.rank import (
    DEFAULT_WEIGHTS,
    ScoredResult,
    normalize_weights,
    pagerank,
    parse_weights,
    search,
    text_scores,
)
from levi.honestsearch.store import (
    index_path,
    load_index,
    load_weights,
    save_index,
    save_weights,
    store_dir,
    weights_path,
)

__all__ = [
    "Document",
    "SiteCrawl",
    "extract_links",
    "title_of",
    "InvertedIndex",
    "tokenize",
    "DEFAULT_WEIGHTS",
    "ScoredResult",
    "normalize_weights",
    "pagerank",
    "parse_weights",
    "search",
    "text_scores",
    "index_path",
    "load_index",
    "load_weights",
    "save_index",
    "save_weights",
    "store_dir",
    "weights_path",
    "SHELF",
]

# Warehouse atlas entry (wired later by the interop/warehouses crew).
SHELF = {
    "name": "honestsearch",
    "summary": (
        "Clean-room link-graph search over a local index: polite "
        "robots-aware crawler, local inverted index, documented "
        "PageRank-style ranking, genuine unpersonalized mode (no profile "
        "enters ranking — tested), per-result signal explanations."
    ),
    "items": [
        "crawl: SiteCrawl — polite BFS crawl (reuses deepweb PoliteCrawler) "
        "-> Documents with outlinks",
        "index: InvertedIndex — local token index, JSON-persisted",
        "rank: pagerank + tf-idf + weighted combination; search() takes no "
        "profile by construction",
        "cli: python -m levi.honestsearch add|crawl|query|weights|stats|export",
    ],
}
