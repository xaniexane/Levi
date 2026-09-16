"""feedlab core: a fully disclosed engagement-bait scoring model.

The model is deliberately simple and deliberately visible. Every point a
post earns is itemized by signal, so the "algorithm" has nowhere to hide.
Real platform rankers are thousands of features deep and proprietary; this
one is six signals deep and printed on the screen. That is the point.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

MODEL_VERSION = "feedlab-bait-model/1"

# Every weight the ranker uses, published in the open. Changing a weight
# changes the ranking — which is exactly what the opaque giants never let
# you see.
WEIGHTS: Dict[str, float] = {
    "relative_engagement": 1.0,  # engagement per follower, x100
    "outrage_language": 2.0,  # per matched outrage word
    "engagement_farming": 3.0,  # per matched farming phrase
    "follower_asymmetry": 1.5,  # log10(followers+1) — big accounts boosted
    "media_bonus": 2.0,  # flat bonus for attached media
    "recency": -0.05,  # per hour of age (newer scores higher)
}

OUTRAGE_WORDS = (
    "outrage",
    "outraged",
    "shocking",
    "shocked",
    "disgusting",
    "furious",
    "scandal",
    "scandalous",
    "unbelievable",
    "ridiculous",
    "absurd",
    "terrifying",
    "horrifying",
    "sickening",
    "corrupt",
    "liar",
    "stupid",
    "idiot",
    "destroyed",
    "slammed",
    "explodes",
    "meltdown",
)

FARMING_PHRASES = (
    "comment below",
    "like and share",
    "retweet if",
    "repost if",
    "tag a friend",
    "tag someone",
    "follow for",
    "share this",
    "type yes if",
    "drop a",
    "let me know in the comments",
)

_QUESTION_BAIT_RE = re.compile(r"\?\s*$")
_CAPS_RUN_RE = re.compile(r"\b[A-Z]{4,}\b")


@dataclass
class Post:
    """One post, supplied by the user. All fields are the user's own data."""

    author: str
    text: str
    posted_at: str = ""  # ISO-8601 timestamp; "" = unknown
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    follower_count: int = 0
    has_media: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Post":
        if not isinstance(data, dict):
            raise ValueError("post must be a JSON object")
        author = data.get("author", "")
        text = data.get("text", "")
        if not isinstance(author, str) or not author.strip():
            raise ValueError("post requires a non-empty 'author'")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("post requires non-empty 'text'")

        def _int(name: str) -> int:
            val = data.get(name, 0)
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError("post field %r must be a number" % name)
            val = int(val)
            if val < 0:
                raise ValueError("post field %r must be >= 0" % name)
            return val

        posted_at = data.get("posted_at", "")
        if posted_at and not isinstance(posted_at, str):
            raise ValueError("post field 'posted_at' must be an ISO string")
        return cls(
            author=author.strip(),
            text=text.strip(),
            posted_at=posted_at or "",
            likes=_int("likes"),
            reposts=_int("reposts"),
            replies=_int("replies"),
            follower_count=_int("follower_count"),
            has_media=bool(data.get("has_media", False)),
        )

    def age_hours(self, now: datetime) -> float | None:
        if not self.posted_at:
            return None
        try:
            ts = datetime.fromisoformat(self.posted_at)
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (now - ts).total_seconds() / 3600.0)


def _word_hits(text: str, words: Tuple[str, ...]) -> List[str]:
    lowered = text.lower()
    return sorted({w for w in words if w in lowered})


def _phrase_hits(text: str, phrases: Tuple[str, ...]) -> List[str]:
    lowered = text.lower()
    return sorted({p for p in phrases if p in lowered})


def score(
    post: Post, now: datetime | None = None
) -> Tuple[float, List[Dict[str, Any]]]:
    """Score a post with the disclosed bait model.

    Returns (total, contributions) where each contribution names the
    signal, shows the raw value observed, and the points it earned.
    Nothing is hidden: the contributions ARE the explanation.
    """
    now = now or datetime.now(timezone.utc)
    contributions: List[Dict[str, Any]] = []

    followers = max(post.follower_count, 1)
    rel = (post.likes + 3 * post.reposts + 2 * post.replies) / followers * 100.0
    contributions.append(
        {
            "signal": "relative_engagement",
            "observed": round(rel, 3),
            "detail": "(likes + 3*reposts + 2*replies) / followers * 100",
            "weight": WEIGHTS["relative_engagement"],
            "points": round(rel * WEIGHTS["relative_engagement"], 3),
        }
    )

    outrage = _word_hits(post.text, OUTRAGE_WORDS)
    contributions.append(
        {
            "signal": "outrage_language",
            "observed": outrage,
            "detail": "%d outrage word(s) matched" % len(outrage),
            "weight": WEIGHTS["outrage_language"],
            "points": round(len(outrage) * WEIGHTS["outrage_language"], 3),
        }
    )

    farming = _phrase_hits(post.text, FARMING_PHRASES)
    contributions.append(
        {
            "signal": "engagement_farming",
            "observed": farming,
            "detail": "%d farming phrase(s) matched" % len(farming),
            "weight": WEIGHTS["engagement_farming"],
            "points": round(len(farming) * WEIGHTS["engagement_farming"], 3),
        }
    )

    asym = math.log10(post.follower_count + 1)
    contributions.append(
        {
            "signal": "follower_asymmetry",
            "observed": round(asym, 3),
            "detail": "log10(followers + 1) — the ranker boosts big accounts",
            "weight": WEIGHTS["follower_asymmetry"],
            "points": round(asym * WEIGHTS["follower_asymmetry"], 3),
        }
    )

    contributions.append(
        {
            "signal": "media_bonus",
            "observed": post.has_media,
            "detail": "flat bonus for attached media",
            "weight": WEIGHTS["media_bonus"],
            "points": WEIGHTS["media_bonus"] if post.has_media else 0.0,
        }
    )

    age = post.age_hours(now)
    if age is not None:
        contributions.append(
            {
                "signal": "recency",
                "observed": round(age, 2),
                "detail": "%.2f hours old — the ranker prefers fresh outrage" % age,
                "weight": WEIGHTS["recency"],
                "points": round(age * WEIGHTS["recency"], 3),
            }
        )

    total = round(sum(c["points"] for c in contributions), 3)
    return total, contributions


def rank_chronological(posts: List[Post]) -> List[Post]:
    """The feed the giants took away: newest first, no scoring."""

    def _key(p: Post) -> str:
        return p.posted_at or ""

    return sorted(posts, key=_key, reverse=True)


def rank_bait(
    posts: List[Post], now: datetime | None = None
) -> List[Tuple[Post, float]]:
    """The feed the giants sell you: sorted by the disclosed bait score."""
    scored = [(p, score(p, now)[0]) for p in posts]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def transparency(post: Post, now: datetime | None = None) -> List[Dict[str, Any]]:
    """Per-signal contribution ledger for one post, highest first."""
    _, contributions = score(post, now)
    return sorted(contributions, key=lambda c: c["points"], reverse=True)


def flag_bait(post: Post) -> List[Dict[str, str]]:
    """Heuristic bait flags. Labeled HEURISTIC: pattern matches, not verdicts.

    A flag means 'this pattern is commonly used to farm engagement' —
    never 'this post is manipulative'. The author may simply be angry.
    """
    flags: List[Dict[str, str]] = []
    outrage = _word_hits(post.text, OUTRAGE_WORDS)
    if outrage:
        flags.append(
            {
                "flag": "outrage-language",
                "kind": "heuristic",
                "basis": "matched outrage words: %s" % ", ".join(outrage),
            }
        )
    farming = _phrase_hits(post.text, FARMING_PHRASES)
    if farming:
        flags.append(
            {
                "flag": "engagement-farming",
                "kind": "heuristic",
                "basis": "matched farming phrases: %s" % ", ".join(farming),
            }
        )
    if _QUESTION_BAIT_RE.search(post.text.strip()):
        flags.append(
            {
                "flag": "rage-bait-question",
                "kind": "heuristic",
                "basis": "ends with a question mark — questions harvest replies",
            }
        )
    if len(_CAPS_RUN_RE.findall(post.text)) >= 2:
        flags.append(
            {
                "flag": "caps-amplification",
                "kind": "heuristic",
                "basis": "2+ ALL-CAPS words — typographic shouting",
            }
        )
    if post.replies > 0 and post.likes > 0 and post.replies / post.likes > 2:
        flags.append(
            {
                "flag": "ratioed",
                "kind": "heuristic",
                "basis": "replies exceed 2x likes — high disagreement engagement",
            }
        )
    return flags


def compare(posts: List[Post], now: datetime | None = None) -> Dict[str, Any]:
    """Side-by-side report: chronological order vs bait order.

    Shows exactly which posts the ranker promoted or buried relative to
    the honest chronological feed, and the top signal behind each move.
    """
    now = now or datetime.now(timezone.utc)
    chrono = rank_chronological(posts)
    bait = rank_bait(posts, now)
    chrono_pos = {id(p): i for i, p in enumerate(chrono)}
    rows = []
    for bait_rank, (post, total) in enumerate(bait):
        top = transparency(post, now)[0]
        rows.append(
            {
                "author": post.author,
                "text": post.text[:120],
                "bait_score": total,
                "bait_rank": bait_rank + 1,
                "chrono_rank": chrono_pos[id(post)] + 1,
                "moved": (chrono_pos[id(post)] + 1) - (bait_rank + 1),
                "top_signal": top["signal"],
                "top_signal_points": top["points"],
                "flags": [f["flag"] for f in flag_bait(post)],
            }
        )
    return {
        "model": MODEL_VERSION,
        "weights": dict(WEIGHTS),
        "disclaimer": (
            "EDUCATIONAL SIMULATION. This model does not reproduce any real "
            "platform's ranker. Flags are heuristics, not verdicts."
        ),
        "posts": len(posts),
        "ranking": rows,
    }


def load_posts(path: str | Path) -> List[Post]:
    """Load user-supplied posts from a JSON file. Deny-closed on bad input."""
    p = Path(path)
    if not p.is_file():
        raise ValueError("no such file: %s" % p)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read posts JSON: %s" % exc) from exc
    if not isinstance(raw, list):
        raise ValueError("posts file must hold a JSON array of post objects")
    if not raw:
        raise ValueError("posts file holds no posts")
    if len(raw) > 10000:
        raise ValueError("refusing more than 10000 posts in one run")
    posts = []
    for i, item in enumerate(raw):
        try:
            posts.append(Post.from_dict(item))
        except ValueError as exc:
            raise ValueError("post %d refused: %s" % (i, exc)) from exc
    return posts


DEMO_POSTS: List[Post] = [
    Post(
        author="@local_news",
        text="City council votes 5-4 on the new transit plan. Details at the town hall Thursday.",
        posted_at="2026-09-16T14:00:00+00:00",
        likes=42,
        reposts=8,
        replies=6,
        follower_count=12000,
    ),
    Post(
        author="@outrage_daily",
        text="SHOCKING scandal EXPOSED — you won't BELIEVE what they did!! Comment below if you're FURIOUS",
        posted_at="2026-09-16T13:30:00+00:00",
        likes=900,
        reposts=400,
        replies=1200,
        follower_count=250000,
        has_media=True,
    ),
    Post(
        author="@neighbor_jo",
        text="Lost dog near Elm Park, brown lab, answers to Biscuit. Please share.",
        posted_at="2026-09-16T15:10:00+00:00",
        likes=30,
        reposts=45,
        replies=4,
        follower_count=210,
    ),
    Post(
        author="@growth_guru",
        text="I was BROKE and STUPID until I learned this one trick. Like and share if you want part 2!",
        posted_at="2026-09-16T12:00:00+00:00",
        likes=5000,
        reposts=2200,
        replies=300,
        follower_count=800000,
        has_media=True,
    ),
]
