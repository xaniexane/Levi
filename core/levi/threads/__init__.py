"""Bridging-Ranked Discussion Trees — threading without the engagement casino.

Remix delta: Reddit's engagement-optimized sorting is its revenue — it
structurally cannot ship an honest ranker, because low-effort fluff that
drives time-on-site is what the sorter is FOR. LEVI inverts this: thread
ranking combines transparent quality signals with the bridging score
from ``levi.bridging``'s clean-room math (cross-camp consensus, not raw
popularity), every weight is user-editable, and identities are portable
signed artifacts instead of platform accounts.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

SHELF = {
    "name": "threads",
    "summary": (
        "Bridging-ranked discussion trees: Reddit-density threading whose "
        "ranking blends quality signals with cross-camp bridging consensus "
        "(reusing levi.bridging's math, decoupled), plus portable "
        "HMAC-signed identity profiles."
    ),
    "items": [
        {
            "name": "thread-store",
            "provides": "discussions, nested comments, votes as local trees",
        },
        {
            "name": "bridging-rank",
            "provides": "ranking = quality signals + bridging consensus, user-editable weights, explainable",
        },
        {
            "name": "portable-identity",
            "provides": "user profiles as exportable HMAC-signed artifacts (self-attestation, honestly scoped)",
        },
    ],
}
