"""Otlet's Mundaneum & UDC: relational notation — a faithful sketch.

History: Paul Otlet's Brussels *Mundaneum* (from 1895) — an attempt to index
the world's knowledge on 3×5 cards (over 15 million by the 1930s) using the
Universal Decimal Classification with *relational operators* (+, :, ::)
expressing how subjects connect. It ran a mail-in query service, and Otlet
sketched networked "electric telescopes" — the famous "paper internet." It
died when funding was withdrawn in 1934 and the occupation dispersed the
collection. "The internet made of paper" is romanticized — it was a
centralized card catalog with a mail-in Q&A desk, not a network. The real
lesson is *relational indexing and query services*.

In LEVI: a deliberately *sketch-level* relational layer. :class:`Mundaneum`
stores facts as (subject, relation, object) triples under hierarchical
UDC-style notation, with typed relations (supports, contradicts, extends,
exemplifies, about). :meth:`Mundaneum.brief` traverses the relation graph
around a topic and returns a structured brief with contradictions flagged —
the query-service shape, where the assistant retrieves and synthesizes and
the user never touches the index.

Honesty: INSPIRATIONAL — labeled a faithful sketch, not a working
world-brain. Centralized world-indexing does not scale; the relational
query-service discipline is what transfers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import _persist

RELATIONS = ("about", "supports", "contradicts", "extends", "exemplifies", "relates")

_NOTATION = re.compile(r"^[0-9]+(\.[0-9]+)*$")


@dataclass
class Card:
    notation: str  # UDC-style hierarchical class, e.g. "004.738.5"
    subject: str
    relation: str  # one of RELATIONS
    object: str
    note: str = ""  # the fact, in one line

    def validate(self) -> None:
        if not _NOTATION.fullmatch(self.notation or ""):
            raise ValueError(
                f"notation {self.notation!r} must be UDC-style digits (e.g. '004.738.5')"
            )
        if not self.subject or not self.subject.strip():
            raise ValueError("subject must be non-empty")
        if self.relation not in RELATIONS:
            raise ValueError(f"relation must be one of {RELATIONS}")
        if not self.object or not self.object.strip():
            raise ValueError("object must be non-empty")


class Mundaneum:
    """Sketch of a relational index: hierarchical notation + typed relations
    + a query-service brief. Local, small, honest about its limits."""

    def __init__(self, store: str = "mundaneum"):
        self._store = _persist.store_path(store)
        self.cards: list[Card] = []
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or "cards" not in data:
            raise _persist.CorruptStoreError(
                f"mundaneum store {self._store} has bad shape"
            )
        for cd in data["cards"]:
            card = Card(**cd)
            card.validate()
            self.cards.append(card)

    def save(self) -> None:
        _persist.save_json(self._store, {"cards": [asdict(c) for c in self.cards]})

    def file(self, card: Card) -> int:
        """File a relational card. Returns its index."""
        card.validate()
        self.cards.append(card)
        return len(self.cards) - 1

    def under(self, notation: str) -> list[tuple[int, Card]]:
        """Hierarchical retrieval: cards at or below a notation branch."""
        if not _NOTATION.fullmatch(notation or ""):
            raise ValueError(f"bad notation {notation!r}")
        prefix = notation + "."
        return [
            (i, c)
            for i, c in enumerate(self.cards)
            if c.notation == notation or c.notation.startswith(prefix)
        ]

    def about(self, topic: str) -> list[tuple[int, Card]]:
        t = topic.strip().lower()
        if not t:
            raise ValueError("topic must be non-empty")
        return [
            (i, c)
            for i, c in enumerate(self.cards)
            if t in c.subject.lower() or t in c.object.lower() or t in c.note.lower()
        ]

    def brief(self, topic: str) -> dict:
        """The query-service answer: what the cards say about ``topic``,
        structured by relation, with contradictions flagged up front."""
        hits = self.about(topic)
        by_relation: dict[str, list[dict]] = {r: [] for r in RELATIONS}
        for i, c in hits:
            by_relation[c.relation].append(
                {
                    "card": i,
                    "notation": c.notation,
                    "subject": c.subject,
                    "object": c.object,
                    "note": c.note,
                }
            )
        return {
            "topic": topic,
            "cards_consulted": len(hits),
            "contradictions": by_relation["contradicts"],
            "supporting": by_relation["supports"],
            "extensions": by_relation["extends"],
            "examples": by_relation["exemplifies"],
            "related": [by_relation["about"], by_relation["relates"]],
            "disclaimer": (
                "sketch-level relational index — verify against the "
                "full sources before quoting"
            ),
        }
