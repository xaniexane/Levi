"""Card index: term lookup plus hop-bounded reachability.

Findability law: any entity/topic/decision is reachable from the card
index in <= 2 hops.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .sync import CardStore
from .types import Card

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class CardIndex:
    """Inverted term index over card titles and bodies."""

    def __init__(self, postings: dict[str, list[str]]) -> None:
        self._postings = postings

    @classmethod
    def build(cls, cards: list[Card]) -> CardIndex:
        postings: dict[str, set[str]] = defaultdict(set)
        for card in cards:
            for token in set(tokenize(card.title) + tokenize(card.body)):
                postings[token].add(card.id)
        return cls({t: sorted(ids) for t, ids in postings.items()})

    def lookup(self, query: str) -> list[str]:
        """Card ids matching any query token, in fixed order."""
        hits: set[str] = set()
        for token in tokenize(query):
            hits.update(self._postings.get(token, ()))
        return sorted(hits)

    @staticmethod
    def reachable(store: CardStore, start_id: str, max_hops: int = 2) -> set[str]:
        """Ids reachable from ``start_id`` within ``max_hops``.

        Links are traversed in both directions: a card and the cards it
        cites (or that cite it) are one hop apart.
        """
        adjacency: dict[str, set[str]] = defaultdict(set)
        for card in store.all():
            for link in card.links:
                adjacency[link.from_id].add(link.to_id)
                adjacency[link.to_id].add(link.from_id)
        seen = {start_id}
        frontier = {start_id}
        for _ in range(max_hops):
            nxt: set[str] = set()
            for node in frontier:
                for peer in adjacency.get(node, ()):
                    if peer not in seen:
                        seen.add(peer)
                        nxt.add(peer)
            frontier = nxt
        return seen

    def find(self, store: CardStore, query: str, max_hops: int = 2) -> list[str]:
        """Index hits for ``query`` plus everything within ``max_hops``."""
        out: set[str] = set()
        for hit in self.lookup(query):
            out |= self.reachable(store, hit, max_hops)
        return sorted(out)
