"""LEVI Classifieds — trust-graph classifieds, no ad layer.

REMIX DELTA: Meta Marketplace's trust story is "trust our graph" — a
graph you can't inspect, scored by an algorithm you can't audit, on a
platform that monetizes every listing with ads and paid boosting. LEVI
inverts it: listings live in a local JSON file, the trust graph is a
contacts file *you* curate, trust scores come from a transparent
published formula (mutual vouches, fully explained per listing), and
export bundles listings with HMAC-signed trust attestations anyone can
import. No ads, no boosting, no algorithmic ranking — search is substring
match over your own listings, newest first.

What it adds that the giant refuses: auditable trust (the formula is
the documentation), portable listings (leave anytime, take everything),
and a board with no casino attached.
"""

from __future__ import annotations

SHELF = {
    "name": "classifieds",
    "summary": (
        "Trust-graph classifieds: local listings, trust scores from a "
        "user-controlled contacts graph via a transparent formula, "
        "portable signed export bundles, no ad layer."
    ),
    "items": [
        {
            "id": "listing-add",
            "kind": "command",
            "summary": "Post a listing (title, price, category, contact).",
            "invoke": "python -m levi.classifieds add TITLE [--price P] [--category C]",
        },
        {
            "id": "listing-browse",
            "kind": "command",
            "summary": "Browse listings, newest first, with trust scores.",
            "invoke": "python -m levi.classifieds browse [--category C] [--query Q]",
        },
        {
            "id": "trust-score",
            "kind": "command",
            "summary": "Explain a lister's trust score (mutuals + formula).",
            "invoke": "python -m levi.classifieds trust LISTER_ID",
        },
        {
            "id": "vouch",
            "kind": "command",
            "summary": "Record that a contact vouches for someone.",
            "invoke": "python -m levi.classifieds vouch CONTACT --for ID --weight 0.8",
        },
        {
            "id": "bundle-export",
            "kind": "command",
            "summary": "Export portable bundle: listings + signed attestations.",
            "invoke": "python -m levi.classifieds export --out bundle.json",
        },
        {
            "id": "bundle-import",
            "kind": "command",
            "summary": "Import a bundle; trust recomputed against your graph.",
            "invoke": "python -m levi.classifieds import bundle.json",
        },
    ],
}
