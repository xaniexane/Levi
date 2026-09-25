"""feedlab — the feed-ranking transparency lab.

The giants refuse to show how their rankers score you: X's For You feed,
TikTok's recommendation engine, Instagram's ranking — all opaque, all
optimized for engagement extraction. feedlab inverts the trade.

It applies a FULLY DISCLOSED engagement-bait scoring model to YOUR OWN
saved posts — every signal, every weight, every point contribution is
visible in the output. Chronological order is always shown alongside the
bait ranking so you can see exactly what the ranker moved and why.

Honesty rules (enforced, not aspirational):
- This is an EDUCATIONAL SIMULATION. It never claims to reproduce any
  real platform's ranker; the model is a documented teaching device.
- Bait flags are labeled HEURISTICS — pattern matches, not judgments.
- Input posts are the user's own data (JSON file or the built-in demo
  feed). feedlab never fetches from any platform, never phones home,
  never stores anything outside the process.
"""

from levi.feedlab.feedlab import (
    MODEL_VERSION,
    WEIGHTS,
    Post,
    compare,
    flag_bait,
    load_posts,
    rank_bait,
    rank_chronological,
    score,
    transparency,
)

__all__ = [
    "MODEL_VERSION",
    "WEIGHTS",
    "Post",
    "compare",
    "flag_bait",
    "load_posts",
    "rank_bait",
    "rank_chronological",
    "score",
    "transparency",
]
