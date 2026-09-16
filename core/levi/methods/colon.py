"""Ranganathan colon classification: PMEST faceted synthesis.

History: S. R. Ranganathan's 1933 *analytico-synthetic* classification —
instead of enumerating every subject in a fixed hierarchy (like Dewey),
build any subject at cataloging time from five universal facets —
**P**ersonality, **M**atter, **E**nergy, **S**pace, **T**ime — joined by
colons. "Research in the cure of tuberculosis in India in 1950" = Medicine :
Disease : Treatment : India : 1950. The universe of knowledge is *generated*,
not listed. The universalist claim (five facets suffice for all knowledge)
didn't survive contact with real domains — borrow the *mechanism* (synthesis
from facets), not the *metaphysics*.

In LEVI: :class:`ColonClassifier` synthesizes colon numbers from facet
assignments, round-trips them back into facets, and pivots an indexed
collection on any facet. Facet *sets* are domain-configurable per collection
(Ranganathan's mechanism without his universalism): the default is PMEST,
but a collection may define its own facets (client, topic, method, year…).

Honesty: LOAD-BEARING — faceted synthesis is a real mechanism; the
colon number becomes a URL-like address for any idea.
"""

from __future__ import annotations


DEFAULT_FACETS = ("Personality", "Matter", "Energy", "Space", "Time")


class ColonClassifier:
    """Faceted synthesis engine: facets in, colon number out, and back."""

    def __init__(self, facets: tuple[str, ...] = DEFAULT_FACETS):
        if len(facets) < 2:
            raise ValueError("need at least 2 facets")
        if len(set(facets)) != len(facets):
            raise ValueError("facet names must be distinct")
        if any(not f or not f.strip() for f in facets):
            raise ValueError("facet names must be non-empty")
        self.facets: tuple[str, ...] = tuple(f.strip() for f in facets)
        self.items: dict[str, dict[str, str]] = {}  # item_id -> {facet: value}

    def classify(self, item_id: str, **facet_values: str) -> str:
        """Assign facet values to an item; returns its synthesized colon number.

        Missing facets are left blank (denoted by empty segments); unknown
        facet names are rejected — deny-closed."""
        item_id = item_id.strip()
        if not item_id:
            raise ValueError("item_id must be non-empty")
        unknown = set(facet_values) - set(self.facets)
        if unknown:
            raise ValueError(f"unknown facets: {sorted(unknown)} (known: {list(self.facets)})")
        assignment = {}
        for facet in self.facets:
            value = str(facet_values.get(facet, "")).strip()
            if ":" in value:
                raise ValueError(f"facet value {value!r} may not contain ':'")
            assignment[facet] = value
        self.items[item_id] = assignment
        return self.colon_number(item_id)

    def colon_number(self, item_id: str) -> str:
        """Synthesize the colon number for a classified item."""
        if item_id not in self.items:
            raise KeyError(f"item {item_id!r} is not classified")
        return ":".join(self.items[item_id][f] for f in self.facets)

    def parse(self, colon_number: str) -> dict[str, str]:
        """Analyze a colon number back into its facet values (round-trip)."""
        parts = colon_number.split(":")
        if len(parts) != len(self.facets):
            raise ValueError(
                f"colon number has {len(parts)} segments, expected {len(self.facets)}"
            )
        return {facet: part for facet, part in zip(self.facets, parts)}

    def pivot(self, facet: str, value: str) -> list[str]:
        """Slice the collection: all items with this facet value."""
        if facet not in self.facets:
            raise ValueError(f"unknown facet {facet!r}")
        v = value.strip().lower()
        return sorted(i for i, a in self.items.items() if a[facet].lower() == v)

    def facet_values(self, facet: str) -> list[str]:
        """The vocabulary actually in use for a facet (for building filters)."""
        if facet not in self.facets:
            raise ValueError(f"unknown facet {facet!r}")
        return sorted({a[facet] for a in self.items.values() if a[facet]})
