"""Sovereign Attention Dials — user-owned feed ranking.

Remix delta: Meta/IG/X/TikTok/YouTube rankers are black boxes whose real
job is ad delivery; the user can never see, let alone edit, the weights.
LEVI inverts this: the weight vector lives in the user's own data dir,
every ranking decision prints its per-weight contributions, and
chronological order is the sticky default with weights as opt-in overlays.
Affinity is an EXPLICIT opt-in list the user edits — never inferred from
surveillance.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

SHELF = {
    "name": "dials",
    "summary": (
        "Sovereign attention dials: transparent, user-editable ranking "
        "weights over a local item stream; chronological-by-default."
    ),
    "items": [
        {
            "name": "weight-vector",
            "provides": "inspectable/editable ranking weights (recency, affinity, diversity, substance, tag-match)",
        },
        {
            "name": "chronological-feed",
            "provides": "sticky chronological default with weights as opt-in overlays",
        },
        {
            "name": "rank-explainer",
            "provides": "per-item per-weight contribution breakdown for every ranking decision",
        },
        {
            "name": "explicit-affinity",
            "provides": "opt-in author affinity list; no implicit tracking",
        },
    ],
}
