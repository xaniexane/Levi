"""Listing forge — ultra-sales listings per platform, from intake facts only.

Modeled on the gem's ultra-sales engine (premium high-conversion language,
urgency+scarcity, emojis in titles/descriptions, hashtags only at the bottom)
with L1/L2 guards: every claim traces to intake, scarcity only from real
quantity.
"""

from __future__ import annotations

import re
from typing import Dict, List

from levi.salesman import Item

_PLATFORMS = ("marketplace", "vinted", "x", "tiktok")

_CONDITION_LABEL = {
    "new": "Brand new ✨",
    "like-new": "Like new — barely used",
    "used-good": "Good used condition",
    "used-fair": "Fair condition — priced to reflect it",
    "parts": "For parts / repair",
}

_EMOJI = {
    "marketplace": "🔥",
    "vinted": "💎",
    "x": "⚡",
    "tiktok": "🎯",
}


def _stopwords() -> set:
    return {
        "the", "and", "for", "with", "this", "that", "from", "your",
        "brand", "new", "used", "great", "nice",
    }


def hashtags(item: Item, n: int = 8) -> List[str]:
    words = re.findall(r"[A-Za-z0-9]+", f"{item.brand} {item.name} {item.category}".lower())
    tags = []
    for w in words:
        if w not in _stopwords() and w not in tags:
            tags.append("#" + w)
        if len(tags) >= n:
            break
    tags.append("#resale")
    return tags[: n + 1]


def _scarcity_line(item: Item) -> str:
    # L2: only real scarcity.
    if item.quantity == 1:
        return "Only 1 available — when it's gone, it's gone."
    return f"{item.quantity} available."


def forge_listing(item: Item, platform: str, price: float) -> Dict[str, str]:
    """Build a listing. Raises on unknown platform. Pure function."""
    if platform not in _PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}; choose {', '.join(_PLATFORMS)}")
    problems = item.validate()
    if problems:
        raise ValueError(f"bad intake: {'; '.join(problems)}")

    emoji = _EMOJI[platform]
    title = f"{emoji} {item.name} — {_CONDITION_LABEL[item.condition]}"
    if item.size:
        title += f" ({item.size})"

    lines = [f"{emoji} {item.name}", ""]
    lines.append(_CONDITION_LABEL[item.condition] + ".")
    if item.brand:
        lines.append(f"Brand: {item.brand}")
    if item.includes:
        lines.append("Includes: " + ", ".join(item.includes))
    # L1: flaws disclosed, always. No invented test claims.
    if item.flaws:
        lines.append("Flaws (priced in): " + "; ".join(item.flaws))
    else:
        lines.append("No flaws on record.")
    lines.append("")
    lines.append(_scarcity_line(item))
    if platform in ("marketplace", "vinted"):
        lines.append("Local pickup in Springfield, IL or ask about shipping.")
    elif platform == "x":
        lines.append("DM to claim. First come, first served.")
    else:
        lines.append("Comment SOLD to claim 👇")
    lines.append("")
    lines.append(" ".join(hashtags(item)))

    body = "\n".join(lines)
    return {
        "platform": platform,
        "title": title,
        "price": f"${price:.2f}",
        "body": body,
    }
