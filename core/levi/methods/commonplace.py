"""Commonplace books + Locke's index: indexed personal knowledge capture.

History: early-modern readers copied excerpts, maxims, and observations into
notebooks under reusable topical "heads" (Virtue, Friendship, Taxes…).
John Locke's innovation was a compact two-page alphabetical index with a
vowel-consonant grid, letting him file any excerpt under a head in seconds
and find it later. Without the index, a commonplace book is a junk drawer.

In LEVI: :class:`CommonplaceBook` captures excerpts under *your own* evolving
heads, each with provenance back to its source, and maintains the dense
Locke-style alphabetical index for retrieval. :meth:`audit_heads` fights
the historical failure mode (heads ossifying into authority-copying) with
rule-based heuristics — merge/split/stale suggestions, honestly labeled as
heuristics, never silent reorganization.

Honesty: LOAD-BEARING — capture → own-ontology filing → dense index →
retrieval is a complete working mechanism, local-first.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import _persist


@dataclass
class Excerpt:
    text: str
    source: str = ""
    page: str = ""
    captured: str = ""  # ISO date of capture
    note: str = ""      # your own gloss

    def validate(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("excerpt text must be non-empty")


@dataclass
class Head:
    name: str
    excerpts: list[Excerpt] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("head name must be non-empty")


class CommonplaceBook:
    """Your indexed commonplace book: capture under heads, retrieve by index."""

    def __init__(self, store: str = "commonplace"):
        self._store = _persist.store_path(store)
        self.heads: dict[str, Head] = {}
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or "heads" not in data:
            raise _persist.CorruptStoreError(f"commonplace store {self._store} has bad shape")
        for name, hd in data["heads"].items():
            head = Head(name=name, excerpts=[Excerpt(**e) for e in hd.get("excerpts", [])])
            head.validate()
            self.heads[name] = head

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"heads": {name: asdict(h) for name, h in self.heads.items()}},
        )

    # ---- capture ---------------------------------------------------------
    def add_head(self, name: str) -> Head:
        name = name.strip()
        head = Head(name=name)
        head.validate()
        key = name.lower()
        if key in self.heads:
            raise ValueError(f"head {name!r} already exists")
        self.heads[key] = head
        return head

    def capture(self, head_name: str, excerpt: Excerpt) -> None:
        """File an excerpt under a head (creating the head if new)."""
        excerpt.validate()
        key = head_name.strip().lower()
        if key not in self.heads:
            self.add_head(head_name.strip())
        self.heads[key].excerpts.append(excerpt)

    # ---- Locke's index ---------------------------------------------------
    def index(self) -> dict[str, list[str]]:
        """The dense alphabetical index: initial-letter -> sorted head names.

        Locke's trick was fitting the whole retrieval key on two pages; here
        the index maps each initial letter to its heads so lookup is instant.
        """
        idx: dict[str, list[str]] = {}
        for head in self.heads.values():
            initial = head.name[0].upper()
            idx.setdefault(initial, []).append(head.name)
        for initial in idx:
            idx[initial].sort(key=str.lower)
        return dict(sorted(idx.items()))

    def retrieve(self, head_name: str) -> list[Excerpt]:
        key = head_name.strip().lower()
        if key not in self.heads:
            raise KeyError(f"no head {head_name!r}")
        return list(self.heads[key].excerpts)

    def search(self, query: str) -> list[tuple[str, Excerpt]]:
        """Full-text search across all heads; returns (head, excerpt)."""
        q = query.strip().lower()
        if not q:
            raise ValueError("query must be non-empty")
        hits = []
        for head in self.heads.values():
            for ex in head.excerpts:
                if q in ex.text.lower() or q in ex.note.lower() or q in ex.source.lower():
                    hits.append((head.name, ex))
        return hits

    # ---- the modern fix for ossification ---------------------------------
    def audit_heads(self) -> dict[str, list[str]]:
        """Rule-based heuristics (labeled as such): suggest merges for heads
        that overlap lexically, flag stale heads with few excerpts, and spot
        heads that may deserve splitting (very long). Nothing is reorganized
        automatically — the assistant proposes, you dispose."""
        names = [h.name for h in self.heads.values()]
        suggestions: dict[str, list[str]] = {"merge_candidates": [], "stale": [], "split_candidates": []}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                wa, wb = set(a.lower().split()), set(b.lower().split())
                if wa & wb:
                    suggestions["merge_candidates"].append(f"{a!r} ~ {b!r} (shared words)")
        for head in self.heads.values():
            n = len(head.excerpts)
            if n <= 1:
                suggestions["stale"].append(f"{head.name!r} ({n} excerpt{'s' if n != 1 else ''})")
            elif n >= 50:
                suggestions["split_candidates"].append(f"{head.name!r} ({n} excerpts)")
        return suggestions
