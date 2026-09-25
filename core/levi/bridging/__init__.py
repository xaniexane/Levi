"""Disagreement-Bridging Legitimacy Layer — consensus without a central moderator.

Remix delta: X's Community Notes runs the bridging algorithm centrally on
X-owned data. LEVI runs a clean-room implementation locally on
user-owned rating data: legitimacy comes from math the user can audit,
not from a platform's moderation team.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

SHELF = {
    "name": "bridging",
    "summary": (
        "Bridging-based consensus scoring (clean-room latent-factor model): "
        "notes earn legitimacy when raters who normally disagree both rate "
        "them helpful. Runs on local rating data; no central moderator."
    ),
    "items": [
        {
            "name": "bridging-math",
            "provides": "pure latent-factor fit (raters x notes -> helpfulness intercepts + viewpoint factors), importable without storage",
        },
        {
            "name": "rating-store",
            "provides": "local rater/note registry with hermetic JSON persistence",
        },
        {
            "name": "note-status",
            "provides": "BRIDGING-HELPFUL / NOT-HELPFUL / NEEDS-MORE-RATINGS classification with cross-camp evidence",
        },
    ],
}
