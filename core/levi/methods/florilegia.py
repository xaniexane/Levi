"""Florilegia: thematic anthologies of excerpts with provenance.

History: medieval Latin *florilegia* ("gatherings of flowers") — systematic,
often near-encyclopedic anthologies of excerpts (Church Fathers, Aristotle…)
organized by topic for preachers and scholars. *Manipulus florum* (Thomas of
Ireland, early 14th c.) is the exemplar. Unlike personal commonplace books,
florilegia were *authoritative and shared* — a pre-computed search index over
the inaccessible library.

In LEVI: :class:`Florilegium` builds shared, topic-organized anthologies of
the best passages from collective reading — each excerpt with source,
context, and a confidence note. The hard rule from history: compilers often
copied *other florilegia*, not the sources, compounding error — so every
excerpt records whether it was taken from the source itself or second-hand,
and second-hand excerpts are flagged for verification against the full
source. Always link back.

Honesty: USEFUL PATTERN — curated shared excerpts with provenance; not a
wiki, not a chat log.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from . import _persist

CONFIDENCE = ("high", "medium", "low")


@dataclass
class Excerpt:
    passage: str
    source: str  # full source reference (work, author)
    head: str  # topical head it is filed under
    context: str = ""  # where in the source / surrounding argument
    confidence: str = "medium"
    second_hand: bool = False  # True if copied from another florilegium/anthology
    second_hand_from: str = ""  # which anthology, if second_hand

    def validate(self) -> None:
        if not self.passage or not self.passage.strip():
            raise ValueError("passage must be non-empty")
        if not self.source or not self.source.strip():
            raise ValueError("source must be non-empty")
        if not self.head or not self.head.strip():
            raise ValueError("head must be non-empty")
        if self.confidence not in CONFIDENCE:
            raise ValueError(f"confidence must be one of {CONFIDENCE}")
        if self.second_hand and not self.second_hand_from.strip():
            raise ValueError("second-hand excerpts must name the anthology copied from")


class Florilegium:
    """A shared, topic-organized anthology with provenance chains."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("florilegium name must be non-empty")
        self.name = name.strip()
        self._store = _persist.store_path(store or f"florilegium-{self.name}")
        self.excerpts: list[Excerpt] = []
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"florilegium store {self._store} does not match {self.name!r}"
            )
        for ed in data.get("excerpts", []):
            ex = Excerpt(**ed)
            ex.validate()
            self.excerpts.append(ex)

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name, "excerpts": [asdict(e) for e in self.excerpts]},
        )

    def gather(self, excerpt: Excerpt) -> int:
        """Add an excerpt. Returns its index. Deny-closed: second-hand
        excerpts without a named source are rejected at validation."""
        excerpt.validate()
        self.excerpts.append(excerpt)
        return len(self.excerpts) - 1

    def under_head(self, head: str) -> list[tuple[int, Excerpt]]:
        h = head.strip().lower()
        return [
            (i, e) for i, e in enumerate(self.excerpts) if e.head.strip().lower() == h
        ]

    def heads(self) -> list[str]:
        seen: dict[str, str] = {}
        for e in self.excerpts:
            seen.setdefault(e.head.strip().lower(), e.head.strip())
        return sorted(seen.values(), key=str.lower)

    def needs_verification(self) -> list[tuple[int, Excerpt]]:
        """The 'florilegia of florilegia' audit: every second-hand excerpt
        must be checked against the full source before being quoted."""
        return [(i, e) for i, e in enumerate(self.excerpts) if e.second_hand]

    def render(self, head: str | None = None) -> str:
        items = self.excerpts if head is None else [e for _, e in self.under_head(head)]
        lines = [
            f"FLORILEGIUM: {self.name} — {len(items)} excerpts"
            + (f" under {head!r}" if head else "")
        ]
        for e in items:
            tag = " [SECOND-HAND — verify against source]" if e.second_hand else ""
            lines.append(f"\n“{e.passage}”{tag}")
            lines.append(f"  — {e.source}" + (f" ({e.context})" if e.context else ""))
            lines.append(f"  head: {e.head}; confidence: {e.confidence}")
        return "\n".join(lines)
