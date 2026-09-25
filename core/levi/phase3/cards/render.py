"""Render cards as readable plain-speech text (CLI surface).

Readable, not cryptic: the card's truth is the deterministic template
render; this module only lays it out.
"""

from __future__ import annotations

from .types import Card


def render(card: Card) -> str:
    """Render one card as plain text."""
    lines = [
        "card %s [%s] (version %d)" % (card.id, card.kind, card.version),
        "title: %s" % card.title,
        "body:",
    ]
    for body_line in card.body.splitlines():
        lines.append("  " + body_line)
    if card.links:
        lines.append("links:")
        for link in card.links:
            lines.append("  - %s -> %s" % (link.relation, link.to_id))
    else:
        lines.append("links: none")
    lines.append("sources: %s" % (", ".join(card.sources) if card.sources else "none"))
    return "\n".join(lines)


def render_index(cards: list[Card]) -> str:
    """One-line-per-card index listing."""
    return "\n".join(
        "%s [%s] %s" % (c.id, c.kind, c.title)
        for c in sorted(cards, key=lambda c: c.id)
    )
