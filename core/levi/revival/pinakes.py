"""LEVI's critical annotated catalog: finding and evaluating in one motion.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #4)

The old mechanism: a catalog of works where every entry carries the
librarian's *judgment* — a rating, a note on the author's context, links
to related works, and a flag for authenticity. The catalog doesn't just
find; it evaluates. Search returns entries WITH their judgments, so the
reader never has to re-derive what's already known about a work.

``Pinax`` holds ``Entry`` records. ``add`` registers one with its full
critical apparatus. ``search`` matches on title, author, tags, and note
text — and returns the entries with judgment attached, sorted by rating
so the best-known-good lands on top. ``evaluate(title)`` pulls the
judgment alone. ``cross_references`` walks the see-also graph. The
``authentic`` flag distinguishes works verified as genuine from dubious
ones; ``flag(title, authentic=False)`` can mark something suspect after
the fact. ``of_rating(min_rating)`` filters the canon-quality shelf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival/pinakes"

# Ratings run 1-5. An entry without evidence is authentic="unknown" — never
# assumed genuine.


@dataclass
class Entry:
    """One cataloged work with its critical judgment."""

    title: str
    author: str
    rating: int  # 1-5, the librarian's judgment
    context: str  # biography/context note: who wrote it, where it stands
    tags: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)  # cross-references (titles)
    authentic: str = "unknown"  # "genuine" | "dubious" | "unknown"

    def __post_init__(self):
        if not 1 <= self.rating <= 5:
            raise ValueError(f"rating must be 1..5, got {self.rating}")
        if self.authentic not in ("genuine", "dubious", "unknown"):
            raise ValueError(
                f"authentic must be genuine|dubious|unknown, got {self.authentic}"
            )

    def judgment(self) -> Dict[str, Any]:
        """The critical apparatus alone: rating, context, authenticity."""
        return {
            "title": self.title,
            "author": self.author,
            "rating": self.rating,
            "context": self.context,
            "authentic": self.authentic,
        }


class Pinax:
    """The annotated catalog: search finds, judgment evaluates."""

    def __init__(self):
        self._entries: Dict[str, Entry] = {}

    def add(self, entry: Entry) -> Entry:
        """Register an entry. Title is the key; re-adding replaces honestly."""
        self._entries[entry.title] = entry
        return entry

    def get(self, title: str) -> Optional[Entry]:
        return self._entries.get(title)

    def search(self, query: str) -> List[Entry]:
        """Find by title/author/tags/context, WITH judgments, best first.

        Finding and evaluating in one motion: every hit carries its rating,
        context, and authenticity flag, sorted rating-descending.
        """
        needle = query.lower()
        hits = []
        for entry in self._entries.values():
            haystack = " ".join(
                [entry.title, entry.author, entry.context] + entry.tags
            ).lower()
            if needle in haystack:
                hits.append(entry)
        hits.sort(key=lambda e: (-e.rating, e.title))
        return hits

    def evaluate(self, title: str) -> Dict[str, Any]:
        """Pull the judgment for one work alone."""
        entry = self._entries.get(title)
        if entry is None:
            raise KeyError(f"catalog holds no {title!r}")
        return entry.judgment()

    def of_rating(self, min_rating: int) -> List[Entry]:
        """The quality shelf: everything rated at least this high."""
        return sorted(
            (e for e in self._entries.values() if e.rating >= min_rating),
            key=lambda e: (-e.rating, e.title),
        )

    def cross_references(self, title: str) -> List[Entry]:
        """Walk the see-also graph one hop from this entry."""
        entry = self._entries.get(title)
        if entry is None:
            raise KeyError(f"catalog holds no {title!r}")
        return [self._entries[t] for t in entry.see_also if t in self._entries]

    def flag(self, title: str, authentic: str, note: str = "") -> Entry:
        """Update the authenticity verdict after the fact; appends the note
        to the context so the judgment trail is visible."""
        entry = self._entries.get(title)
        if entry is None:
            raise KeyError(f"catalog holds no {title!r}")
        if authentic not in ("genuine", "dubious", "unknown"):
            raise ValueError(
                f"authentic must be genuine|dubious|unknown, got {authentic}"
            )
        entry.authentic = authentic
        if note:
            entry.context = f"{entry.context} [flagged: {note}]"
        return entry

    def genuine_only(self) -> List[Entry]:
        """Everything verified genuine — the safe shelf."""
        return [e for e in self._entries.values() if e.authentic == "genuine"]

    def __len__(self) -> int:
        return len(self._entries)
