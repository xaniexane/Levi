"""LEVI discover — ritualized local discovery over your OWN corpus.

REMIX DELTA: Spotify's Discover Weekly is a ritual people love — but it
runs on a licensed catalog, optimizes for engagement, and steers you into
a filter bubble that serves the platform. The fallen-platforms thesis
says the abandoned agency-enhancing idea IS the feature: a discovery
ritual with NO catalog license, NO engagement steering, and EXPLICIT
anti-filter-bubble rules. The remix: a Discover-Weekly-style digest
generated over the user's own library/corpus (the Archive, or any JSONL
source), with serendipity as a designed mechanism — seeded randomness
you can see, diversity caps you can read, and a no-repeat memory.

What it ADDS that the giants refuse:
- Non-optimized serendipity: picks are random-by-design (seed shown in
  the digest), never engagement-ranked. Randomness is the point.
- Anti-filter-bubble diversity rules: per-kind caps, per-tag caps, and
  preference for unseen items — the opposite of collaborative filtering.
- The ritual is yours: weekly markdown digests under
  ``~/.levi/discover/digests/``, shareable as plain files, no account.

Stdlib-only. Local-first. No network.
"""

from __future__ import annotations

__all__ = ["SHELF"]

SHELF = {
    "name": "local discovery",
    "summary": (
        "Discover-Weekly-style ritual over the user's own corpus: seeded "
        "serendipity, anti-filter-bubble diversity rules, no-repeat memory, "
        "shareable weekly markdown digests. No catalog, no engagement steering."
    ),
    "items": [
        "items: JSONL item schema (id/title/kind/tags/added_at/source) + loader",
        "digest: seeded random picks, diversity caps, no-repeat history, markdown output",
        "CLI: discover --week, history, init-sample corpus",
    ],
}
