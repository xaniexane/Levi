"""LEVI Recap — your year, computed on-device.

REMIX DELTA: Spotify Wrapped is free advertising you make for Spotify:
your listening data is mined on their servers, packaged into shareable
cards, and every share recruits new users. The recap is the product; you
are the ad surface. LEVI inverts it: the same delight — totals,
streaks, top categories, milestones, shareable cards — computed
entirely on your machine from a JSONL event file you own, rendered as
text and standalone HTML (inline CSS, zero external requests). Share
the card if you want; the data never had to travel to make it.

What it adds that the giant refuses: recaps with no telemetry, no
account, and no marketing funnel attached — the cards are yours, not
their growth loop.
"""

from __future__ import annotations

SHELF = {
    "name": "recap",
    "summary": (
        "Local annual recap: stats (totals, streaks, top categories, "
        "milestones) computed on-device from a user-owned JSONL event "
        "source, rendered as text + standalone HTML cards."
    ),
    "items": [
        {
            "id": "recap-stats",
            "kind": "command",
            "summary": "Compute stats from a JSONL event file (optional --year).",
            "invoke": "python -m levi.recap stats EVENTS.jsonl [--year 2026]",
        },
        {
            "id": "recap-html",
            "kind": "command",
            "summary": "Render a standalone shareable HTML card.",
            "invoke": "python -m levi.recap html EVENTS.jsonl --out recap.html",
        },
        {
            "id": "recap-sample",
            "kind": "command",
            "summary": "Generate deterministic synthetic events (labeled synthetic).",
            "invoke": "python -m levi.recap sample --out sample.jsonl",
        },
    ],
}
