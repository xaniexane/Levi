"""LEVI's write-as-you-read capture: commonplace entries under evolving heads,
retrievable through a dense grid index.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #6)

Two mechanisms, one instrument.

Half one — the commonplace: while reading, file excerpts and reflections
under topical *heads* (Memory, Craft, Doubt...). Heads are not fixed
taxonomy; ``ensure_head`` grows the scheme as the reader's interests move,
and ``rehead`` moves an entry when the scheme changes. The book is
append-only — entries carry sequence numbers, so nothing is rewritten.

Half two — the dense grid index: a compact vowel-consonant style bucket
system. Each head name is hashed into a two-letter bucket code (leading
vowel class × leading consonant class), and the index maps bucket → heads →
entry numbers. Retrieval walks the grid instead of re-reading the book:
``lookup(topic)`` resolves the bucket and returns matching entries without
scanning everything. ``grid`` exposes the whole index for inspection.

The promise the old method made: retrieval beats re-reading. The
``entry_count`` vs ``scan_cost`` story is honest — lookup touches the
bucket, not the book.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/commonplace"

# Vowel-class × consonant-class grid, in the old dense-index spirit.
VOWELS = "aeiou"
CONSONANT_CLASSES = "bcdfg hjklm npqrs tvwxz".split()  # 6 classes


def bucket_code(head: str) -> str:
    """Two-letter bucket for a head name: vowel class + consonant class."""
    name = head.strip().lower()
    first_vowel = next((ch for ch in name if ch in VOWELS), "a")
    first_cons = next((ch for ch in name if ch not in VOWELS and ch.isalpha()), "b")
    cons_class = next(
        (str(i) for i, cls in enumerate(CONSONANT_CLASSES) if first_cons in cls),
        "0",
    )
    return f"{first_vowel}{cons_class}"


@dataclass
class Head:
    """A topical head: name plus a note on why it exists (heads evolve)."""

    name: str
    rationale: str = ""
    entries: List[int] = field(default_factory=list)


@dataclass
class Entry:
    """One captured note: excerpt + reflection filed under a head."""

    seq: int
    head: str
    excerpt: str
    reflection: str = ""
    source: str = ""

    def text(self) -> str:
        return f"{self.excerpt}\n{self.reflection}".strip()


class Commonplace:
    """The book (append-only entries under evolving heads) + the grid index."""

    def __init__(self):
        self._entries: List[Entry] = []
        self._heads: Dict[str, Head] = {}
        self._grid: Dict[str, Dict[str, List[int]]] = {}  # bucket -> head -> [seq]

    # -- heads: the evolving scheme -----------------------------------------
    def ensure_head(self, name: str, rationale: str = "") -> Head:
        if name not in self._heads:
            self._heads[name] = Head(name=name, rationale=rationale)
        return self._heads[name]

    def heads(self) -> List[str]:
        return sorted(self._heads)

    def rehead(self, seq: int, new_head: str) -> Entry:
        """Move an entry to a different head when the scheme changes.

        The book is append-only, so the entry keeps its sequence number; only
        its head and the index move.
        """
        entry = self._by_seq(seq)
        old_head = entry.head
        self.ensure_head(new_head)
        if seq in self._heads[old_head].entries:
            self._heads[old_head].entries.remove(seq)
        entry.head = new_head
        self._heads[new_head].entries.append(seq)
        self._reindex_entry(entry)
        return entry

    # -- capture ------------------------------------------------------------
    def capture(
        self,
        head: str,
        excerpt: str,
        reflection: str = "",
        source: str = "",
    ) -> Entry:
        """File an excerpt+reflection under a head, indexed in one motion."""
        self.ensure_head(head)
        seq = len(self._entries)
        entry = Entry(
            seq=seq, head=head, excerpt=excerpt, reflection=reflection, source=source
        )
        self._entries.append(entry)
        self._heads[head].entries.append(seq)
        self._reindex_entry(entry)
        return entry

    # -- retrieval: the grid ------------------------------------------------
    def _reindex_entry(self, entry: Entry) -> None:
        # remove from any old bucket slot, then file under the current head
        for _bucket, heads in self._grid.items():
            for _h, seqs in heads.items():
                if entry.seq in seqs:
                    seqs.remove(entry.seq)
        bucket = bucket_code(entry.head)
        self._grid.setdefault(bucket, {}).setdefault(entry.head, []).append(entry.seq)

    def lookup(self, topic: str) -> List[Entry]:
        """Retrieve entries for a topic via the grid — no full-book scan.

        Matches the head whose name contains the topic (case-insensitive);
        the grid routes to the bucket first, then to the head's entries.
        """
        needle = topic.lower()
        hits: List[Entry] = []
        for _bucket, heads in self._grid.items():
            for head_name, seqs in heads.items():
                if needle in head_name.lower():
                    hits.extend(self._entries[s] for s in seqs)
        hits.sort(key=lambda e: e.seq)
        return hits

    def grid(self) -> Dict[str, Dict[str, List[int]]]:
        """The whole dense index: bucket → head → entry sequence numbers."""
        return {
            b: {h: list(s) for h, s in heads.items()} for b, heads in self._grid.items()
        }

    def entry_count(self) -> int:
        return len(self._entries)

    # -- internals ----------------------------------------------------------
    def _by_seq(self, seq: int) -> Entry:
        if not 0 <= seq < len(self._entries):
            raise KeyError(f"no entry with sequence {seq}")
        return self._entries[seq]
