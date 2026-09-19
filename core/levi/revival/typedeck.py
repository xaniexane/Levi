"""LEVI's typed-link card web: links with *meaning*, and browsers that draw them.

Studied from: retired-software-revival-research-20260916-0004/report.md (§14).

The load-bearing mechanism of NoteCards: links are *typed* and directional
(``supports``, ``refutes``, ``elaborates``, ``defines`` — not just
"related"), and "browser" cards render *computed structural diagrams* of
the network. Plain links say only "related" and show you pages; typed
links say *why* and let the browser draw the shape of an argument — claims,
evidence, contradictions — as indented text you can actually read.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


ORIGIN = "levi-revival/typedeck"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TypedeckError(Exception):
    """Base class for typedeck failures."""


class UnknownLinkType(TypedeckError):
    """The relationship word isn't in the deck's vocabulary."""

    def __init__(self, rel: str, vocabulary: Iterable[str]):
        super().__init__(
            f"{rel!r} is not a link type here; the deck speaks "
            f"{sorted(set(vocabulary))}"
        )
        self.rel = rel


class UnknownCard(TypedeckError):
    """A link or browser named a card that isn't in the deck."""

    def __init__(self, card_id: str):
        super().__init__(f"no card {card_id!r} in this deck")
        self.card_id = card_id


# ---------------------------------------------------------------------------
# Cards and typed links
# ---------------------------------------------------------------------------


@dataclass
class TCard:
    """One idea card. ``kind`` is a free label: claim, evidence, question..."""

    card_id: str
    title: str
    body: str = ""
    kind: str = "note"


@dataclass(frozen=True)
class TypedLink:
    """A first-class, typed, directional link between two cards."""

    source: str
    rel: str
    target: str


class Deck:
    """A web of idea cards joined by typed links.

    The vocabulary is deliberate and small: ``supports``, ``refutes``,
    ``elaborates``, ``defines`` — plus whatever the author adds, because
    the deck's language is the deck's own business.
    """

    DEFAULT_VOCABULARY = ("supports", "refutes", "elaborates", "defines")

    def __init__(self, vocabulary: Optional[Iterable[str]] = None):
        self.vocabulary = tuple(vocabulary or self.DEFAULT_VOCABULARY)
        self.cards: dict[str, TCard] = {}
        self.links: list[TypedLink] = []

    # -- authoring ----------------------------------------------------------
    def add_card(
        self, card_id: str, title: str, body: str = "", kind: str = "note"
    ) -> TCard:
        if card_id in self.cards:
            raise TypedeckError(f"card {card_id!r} is already in the deck")
        card = TCard(card_id=card_id, title=title, body=body, kind=kind)
        self.cards[card_id] = card
        return card

    def link(self, source: str, rel: str, target: str) -> TypedLink:
        """Join two cards with a typed, directional link."""
        if rel not in self.vocabulary:
            raise UnknownLinkType(rel, self.vocabulary)
        for card_id in (source, target):
            if card_id not in self.cards:
                raise UnknownCard(card_id)
        edge = TypedLink(source=source, rel=rel, target=target)
        if edge not in self.links:
            self.links.append(edge)
        return edge

    def unlink(self, source: str, rel: str, target: str) -> None:
        edge = TypedLink(source=source, rel=rel, target=target)
        if edge not in self.links:
            raise TypedeckError(f"no such link: {source} -{rel}-> {target}")
        self.links.remove(edge)

    # -- reading ------------------------------------------------------------
    def card(self, card_id: str) -> TCard:
        if card_id not in self.cards:
            raise UnknownCard(card_id)
        return self.cards[card_id]

    def out_links(self, card_id: str) -> list[TypedLink]:
        return [lnk for lnk in self.links if lnk.source == card_id]

    def in_links(self, card_id: str) -> list[TypedLink]:
        return [lnk for lnk in self.links if lnk.target == card_id]

    def by_rel(self, rel: str) -> list[TypedLink]:
        if rel not in self.vocabulary:
            raise UnknownLinkType(rel, self.vocabulary)
        return [lnk for lnk in self.links if lnk.rel == rel]

    def argument(
        self, root_id: str, rels: Optional[Iterable[str]] = None
    ) -> dict[str, list[TCard]]:
        """Group the cards reachable from ``root_id`` by link type —
        the raw material a browser draws from."""
        if root_id not in self.cards:
            raise UnknownCard(root_id)
        wanted = set(rels) if rels else set(self.vocabulary)
        grouped: dict[str, list[TCard]] = {rel: [] for rel in wanted}
        seen = {root_id}
        frontier = [root_id]
        while frontier:
            current = frontier.pop()
            for lnk in self.out_links(current):
                if lnk.rel not in wanted:
                    continue
                grouped[lnk.rel].append(self.cards[lnk.target])
                if lnk.target not in seen:
                    seen.add(lnk.target)
                    frontier.append(lnk.target)
        return grouped


# ---------------------------------------------------------------------------
# The structural browser: computed argument-structure diagrams
# ---------------------------------------------------------------------------


_ARROW = {
    "supports": "supports",
    "refutes": "refutes",
    "elaborates": "elaborates",
    "defines": "defines",
}


def browse(
    deck: Deck,
    root_id: str,
    max_depth: int = 4,
    rels: Optional[Iterable[str]] = None,
) -> str:
    """Render a computed argument-structure diagram as indented text.

    Follows typed links out from the root, drawing each relationship as
    a labeled branch. Cycles are marked and not re-entered; depth is
    capped so a tangled web still reads.
    """
    if root_id not in deck.cards:
        raise UnknownCard(root_id)
    wanted = list(rels) if rels else list(deck.vocabulary)
    lines: list[str] = []
    _draw(
        deck,
        root_id,
        wanted,
        lines,
        depth=0,
        max_depth=max_depth,
        seen=set(),
        prefix="",
    )
    return "\n".join(lines)


def _draw(
    deck: Deck,
    card_id: str,
    wanted: list[str],
    lines: list[str],
    depth: int,
    max_depth: int,
    seen: set[str],
    prefix: str,
) -> None:
    card = deck.cards[card_id]
    arrow = _ARROW.get
    label = f"[{card.kind}] {card.title}"
    if depth == 0:
        lines.append(label)
    seen = seen | {card_id}
    children: list[tuple[str, str]] = []
    for lnk in deck.out_links(card_id):
        if lnk.rel in wanted:
            children.append((lnk.rel, lnk.target))
    for i, (rel, target_id) in enumerate(children):
        last = i == len(children) - 1
        branch = "└─" if last else "├─"
        child_prefix = prefix + ("   " if last else "│  ")
        target = deck.cards[target_id]
        verb = arrow(rel, rel)
        if target_id in seen:
            lines.append(
                f"{prefix}{branch} {verb} → [{target.kind}] {target.title} (seen)"
            )
            continue
        lines.append(f"{prefix}{branch} {verb} → [{target.kind}] {target.title}")
        if depth + 1 < max_depth:
            _draw(
                deck, target_id, wanted, lines, depth + 1, max_depth, seen, child_prefix
            )
        elif deck.out_links(target_id):
            lines.append(f"{child_prefix}…")


def debate(deck: Deck, root_id: str) -> dict[str, int]:
    """A one-glance tally of an argument: how many supports, refutes, ..."""
    grouped = deck.argument(root_id)
    return {rel: len(cards) for rel, cards in grouped.items()}


__all__ = [
    "TypedeckError",
    "UnknownLinkType",
    "UnknownCard",
    "TCard",
    "TypedLink",
    "Deck",
    "browse",
    "debate",
]
