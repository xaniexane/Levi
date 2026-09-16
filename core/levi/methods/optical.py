"""Optical-coincidence ("peek-a-boo") cards: inverted bitmask retrieval.

History: a rival to edge-notched cards (Taylor 1915; Batten/Cordonnier
c. 1940–50 literature systems): *one card per term* instead of one per
document. Each term-card has a grid of numbered positions; you punch the
document numbers where that term occurs. Stack the term-cards and hold them
to the light — positions where light shines through *all* cards are the
documents containing *all* terms. Boolean AND, computed optically.

In LEVI: the representational inversion is the lesson. :class:`LightTable`
keeps term-cards (term -> bitmask of document numbers); a query stacks the
cards and the intersection is a bitwise AND — the computer doing what the
light used to do. :meth:`LightTable.view` renders the optical-coincidence
grid so you can *see* which documents sit at the intersection. Distinct from
``edgenotch``: that indexes documents->features; this indexes terms->documents.

Honesty: USEFUL PATTERN — the inversion trick is load-bearing; the punched
cards are not.
"""

from __future__ import annotations


class LightTable:
    """Term-cards over a fixed document grid; intersection by stacking."""

    MAX_DOCS = 256  # bitmask width for the optical grid

    def __init__(self):
        self.documents: list[str] = []  # doc_id by grid position
        self.cards: dict[str, int] = {}  # term -> bitmask of doc positions

    # ---- filing ----------------------------------------------------------
    def add_document(self, doc_id: str) -> int:
        """Assign a grid position to a document. Returns the position."""
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("doc_id must be non-empty")
        if doc_id in self.documents:
            raise ValueError(f"document {doc_id!r} already on the table")
        if len(self.documents) >= self.MAX_DOCS:
            raise OverflowError("light table is full (256 documents)")
        self.documents.append(doc_id)
        return len(self.documents) - 1

    def punch(self, term: str, doc_id: str) -> None:
        """Punch a hole: record that ``term`` occurs in ``doc_id``."""
        term = term.strip().lower()
        if not term:
            raise ValueError("term must be non-empty")
        if doc_id not in self.documents:
            raise KeyError(f"document {doc_id!r} is not on the table")
        pos = self.documents.index(doc_id)
        self.cards[term] = self.cards.get(term, 0) | (1 << pos)

    def index_document(self, doc_id: str, terms: list[str]) -> None:
        """File a document with all its terms at once."""
        self.add_document(doc_id)
        for term in terms:
            self.punch(term, doc_id)

    # ---- the light -------------------------------------------------------
    def coincide(self, terms: list[str]) -> list[str]:
        """Stack the term-cards and hold to the light: documents where light
        shines through *every* card (Boolean AND)."""
        if not terms:
            raise ValueError("coincidence needs at least one term")
        mask: int | None = None
        for term in terms:
            key = term.strip().lower()
            if key not in self.cards:
                return []  # a blank card blocks all light
            mask = self.cards[key] if mask is None else mask & self.cards[key]
            if mask == 0:
                return []
        assert mask is not None
        return [
            self.documents[pos] for pos in range(len(self.documents)) if mask >> pos & 1
        ]

    def view(self, terms: list[str]) -> str:
        """Render the optical-coincidence grid: rows = terms, columns =
        documents, '●' = punched, '○' = blocked. The AND column lights up
        where every row has ●."""
        if not terms:
            raise ValueError("view needs at least one term")
        keys = [t.strip().lower() for t in terms]
        header = "term \\ doc | " + " ".join(
            f"{i:>3}" for i in range(len(self.documents))
        )
        lines = [header, "-" * len(header)]
        masks = []
        for term, key in zip(terms, keys):
            mask = self.cards.get(key, 0)
            masks.append(mask)
            row = " ".join(
                "  ●" if mask >> pos & 1 else "  ○"
                for pos in range(len(self.documents))
            )
            lines.append(f"{term[:9]:<9} | {row}")
        lines.append("-" * len(header))
        combined = masks[0]
        for m in masks[1:]:
            combined &= m
        row = " ".join(
            "  ●" if combined >> pos & 1 else "  ○"
            for pos in range(len(self.documents))
        )
        lines.append(f"{'AND':<9} | {row}")
        hits = self.coincide(terms)
        lines.append(
            f"light through: {hits if hits else '— (no document matches all terms)'}"
        )
        return "\n".join(lines)

    def terms(self) -> list[str]:
        return sorted(self.cards)
