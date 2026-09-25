"""Housekeeping sync: re-derive cards and re-resolve links.

``CardStore.sync_cycle(view)`` re-derives every card from the current
memory state, re-resolves links mechanically, and returns the cards that
changed. Links are never edited by hand: after any corpus change the
next cycle rebuilds them from the facts, so there are no dangling links
— a link whose target no longer has a card is dropped, not left hanging.

Contradictory facts produce ``contradicts`` links between the two cards:
disagreements are surfaced, never merged silently.
"""

from __future__ import annotations

from .derive import card_id_for, derive, derive_decision
from .types import Card, Decision, Link, MemoryView


def _resolve_links(cards: list[Card], view: MemoryView) -> list[Card]:
    """Attach freshly resolved links to every card (pure of the view)."""
    ids = {c.id for c in cards}
    fact_entity: dict[str, str] = {}
    for fact in view.all_facts():
        fact_entity[fact.id] = fact.entity_id

    pending: dict[str, set[Link]] = {c.id: set() for c in cards}

    def add(card_id: str, to_id: str, relation: str) -> None:
        if card_id in pending and to_id in ids and to_id != card_id:
            pending[card_id].add(Link(card_id, to_id, relation))

    for fact in view.all_facts():
        src = card_id_for(fact.entity_id)
        for target in fact.refers_to:
            add(src, card_id_for(target), "cites")
        if fact.supersedes and fact.supersedes in fact_entity:
            add(src, card_id_for(fact_entity[fact.supersedes]), "supersedes")
        for other_id in fact.conflicts_with:
            if other_id not in fact_entity:
                continue
            other_card = card_id_for(fact_entity[other_id])
            if other_card == src:
                continue
            # Canonical direction: one link per conflicting pair.
            lo, hi = sorted((src, other_card))
            if lo in pending and hi in ids:
                pending[lo].add(Link(lo, hi, "contradicts"))

    for card in cards:
        if not card.id.startswith("card:decision:"):
            continue
        decision_id = card.id[len("card:decision:") :]
        dec = _find_decision(view, decision_id)
        if dec is None:
            continue
        add(card.id, card_id_for(dec.entity_id), "about")
        if dec.decider_entity_id:
            add(card.id, card_id_for(dec.decider_entity_id), "decided-by")

    out = []
    for card in cards:
        links = tuple(
            sorted(pending[card.id], key=lambda link: (link.to_id, link.relation))
        )
        out.append(
            Card(
                id=card.id,
                kind=card.kind,
                title=card.title,
                body=card.body,
                links=links,
                sources=card.sources,
                version=card.version,
                updated_at=card.updated_at,
            )
        )
    return out


def _find_decision(view: MemoryView, decision_id: str) -> Decision | None:
    for entity_id in view.entity_ids():
        for dec in view.decisions_about(entity_id):
            if dec.id == decision_id:
                return dec
    return None


class CardStore:
    """The maintained card set: derived views, never a store of record."""

    def __init__(self) -> None:
        self._cards: dict[str, Card] = {}

    def sync_cycle(self, view: MemoryView) -> list[Card]:
        """One housekeeping cycle: re-derive, re-link, report changes."""
        cards = [derive(e, view) for e in view.entity_ids()]
        for entity_id in view.entity_ids():
            for dec in view.decisions_about(entity_id):
                cards.append(derive_decision(dec, view))
        # Dedupe by card id (an entity id could theoretically collide with
        # a decision card id); first derivation wins, deterministically.
        seen: dict[str, Card] = {}
        for card in sorted(cards, key=lambda c: c.id):
            seen.setdefault(card.id, card)
        cards = _resolve_links(list(seen.values()), view)

        changed = [c for c in cards if self._cards.get(c.id) != c]
        self._cards = {c.id: c for c in cards}
        return sorted(changed, key=lambda c: c.id)

    def get(self, card_id: str) -> Card | None:
        return self._cards.get(card_id)

    def all(self) -> list[Card]:
        return sorted(self._cards.values(), key=lambda c: c.id)

    def to_json(self) -> str:
        """Canonical JSON of the whole card set (determinism checks)."""
        import json

        return json.dumps(
            [c.to_dict() for c in self.all()],
            sort_keys=True,
            separators=(",", ":"),
        )

    def __len__(self) -> int:
        return len(self._cards)
