"""LEVI Share Shelf — the reading shelf the giants refused.

REMIX DELTA: Google Reader died in 2013 because an open RSS reader is a
cost center for an ad company: no ad surface, no algorithmic engagement
to sell. The giants' refusal is structural — no honest local-first
shared-items shelf exists anywhere. LEVI inverts it: the shelf runs
entirely on your machine. You shelve anything with a note (Reader's
share-with-note), star your private canon, and bury the duds. Digg's
bury is built in as a first-class signal: buried items sink, never
vanish, and bury is reversible — 'no' is as easy as 'yes,' and the
penalty is yours, never hidden. Starred first, then recency, buried
sunk; no engagement algorithm, ever.

The whole shelf is portable: `shelf bundle` writes a self-describing
zip (markdown + JSON manifest) you can hand to anyone. This is the
honest inversion of the sly trade — your curation leaves the platform,
not your data leaving you.

What it adds that the giants refuse: annotation-first curation, an
honest bury signal, and curation as a portable file. Complements
levi.feedreader (subscriptions) — it never re-reads feeds, it keeps
the shelf.
"""

from __future__ import annotations

from .shelf import (
    ShelfItem,
    ShelfStore,
    ShelfError,
    default_dir,
    url_ok,
)

SHELF = {
    "name": "shelf",
    "summary": (
        "Local-first reading shelf: shelve with a note, star the canon, "
        "bury the duds, bundle the shelf as a portable file."
    ),
    "items": [
        {"id": "shelf-add", "cli": "python -m levi.shelf add URL --title T --note N"},
        {"id": "shelf-list", "cli": "python -m levi.shelf list [--buried]"},
        {"id": "shelf-star", "cli": "python -m levi.shelf star ITEM_ID"},
        {"id": "shelf-bury", "cli": "python -m levi.shelf bury ITEM_ID"},
        {"id": "shelf-unbury", "cli": "python -m levi.shelf unbury ITEM_ID"},
        {"id": "shelf-remove", "cli": "python -m levi.shelf remove ITEM_ID"},
        {"id": "shelf-bundle", "cli": "python -m levi.shelf bundle PATH.shelfbundle"},
        {"id": "shelf-import", "cli": "python -m levi.shelf import PATH.shelfbundle"},
    ],
}

__all__ = [
    "ShelfItem",
    "ShelfStore",
    "ShelfError",
    "default_dir",
    "url_ok",
    "SHELF",
]
