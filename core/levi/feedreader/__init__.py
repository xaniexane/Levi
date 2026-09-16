"""LEVI Feedreader — the sovereign feed reader.

REMIX DELTA: Google killed Reader in 2013 because open RSS can't be
monetized — no ad surface, no algorithmic engagement to sell. The
giants' refusal is structural: a feed reader that respects you (no
tracking, no algorithmic reordering, portable subscriptions) is a cost
center to them. LEVI inverts it: the reader runs entirely on your
machine, polls politely with conditional GET (ETag/Last-Modified, no
re-fetch waste), shows feeds in plain chronological order (no engagement
algorithm, ever), monitors per-feed health honestly (fail streaks,
latency — no hiding dead feeds to juice "active" metrics), and your
subscription list is an OPML file you can take anywhere.

What it adds that the giant refuses: reader-side health transparency,
zero tracking, and subscriptions as a portable file — monopoly-minus-one
for your attention.
"""

from __future__ import annotations

SHELF = {
    "name": "feedreader",
    "summary": (
        "Sovereign RSS/Atom reader: polite conditional-GET polling, local "
        "store, per-feed health monitoring, OPML import/export, "
        "chronological + unread views."
    ),
    "items": [
        {
            "id": "feed-add",
            "kind": "command",
            "summary": "Subscribe to an RSS/Atom feed.",
            "invoke": "python -m levi.feedreader add URL [--title T]",
        },
        {
            "id": "feed-poll",
            "kind": "command",
            "summary": "Poll subscriptions (conditional GET; backoff on failure).",
            "invoke": "python -m levi.feedreader poll [--force]",
        },
        {
            "id": "feed-items",
            "kind": "command",
            "summary": "Chronological items; --unread for unread only.",
            "invoke": "python -m levi.feedreader items [--unread]",
        },
        {
            "id": "feed-read",
            "kind": "command",
            "summary": "Mark an item read by link.",
            "invoke": "python -m levi.feedreader read LINK",
        },
        {
            "id": "feed-health",
            "kind": "command",
            "summary": "Per-feed health: fail streaks, latency, last success.",
            "invoke": "python -m levi.feedreader health",
        },
        {
            "id": "feed-opml",
            "kind": "command",
            "summary": "Export/import subscriptions as OPML.",
            "invoke": "python -m levi.feedreader opml-export | opml-import FILE",
        },
        {
            "id": "news-refresh",
            "kind": "command",
            "summary": "Refresh the dated news corpus (BBC, AP, HN, arXiv; "
            "Reuters 401s honestly). Polite, stdlib-only.",
            "invoke": "python -m levi.feedreader news-refresh [--date YYYY-MM-DD]",
        },
        {
            "id": "news-latest",
            "kind": "command",
            "summary": "Newest ingested headlines (dated recall).",
            "invoke": "python -m levi.feedreader news-latest [--limit N]",
        },
        {
            "id": "news-search",
            "kind": "command",
            "summary": "Ranked keyword search over the news corpus: title "
            "weight ×3, exact-phrase bonus, recency weighting.",
            "invoke": "python -m levi.feedreader news-search QUERY [--limit N]",
        },
    ],
}
