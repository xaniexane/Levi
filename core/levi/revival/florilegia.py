"""LEVI's community-curated excerpt canon: gathered wisdom with provenance intact.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #7)

The old mechanism: a community gathers the passages worth keeping — each
excerpt tagged by topic and traced back to its source (author, work, place
in the work) — and a *canon* is the curated, ordered selection the
community stands behind. Because the library might be inaccessible, a
pre-computed index over the excerpts does the finding: topics, authors,
and full-text lookup over the gathered set, not the shelves.

``Excerpt`` is the unit: text + topic tags + ``Provenance`` (author, work,
locator, and the collector who brought it in). ``Florilegium`` is the
gathering: ``gather`` adds excerpts, ``by_topic`` / ``by_author`` /
``search`` query the pre-computed index. ``Canon`` is the curated ordered
set: ``curate`` selects excerpts into a fixed order with the curator's
rationale; the canon holds references, not copies, so the gathering stays
the single source of truth. ``canon_text`` renders the ordered canon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

ORIGIN = "levi-revival/florilegia"


@dataclass
class Provenance:
    """Where an excerpt came from and who carried it in."""

    author: str
    work: str
    locator: str = ""  # chapter/page/section — wherever it lives in the work
    collected_by: str = ""  # the community member who gathered it

    def citation(self) -> str:
        parts = [self.author, self.work]
        if self.locator:
            parts.append(self.locator)
        base = ", ".join(parts)
        if self.collected_by:
            base += f" (gathered by {self.collected_by})"
        return base


@dataclass
class Excerpt:
    """One gathered passage: text, topic tags, provenance."""

    id: int
    text: str
    topics: List[str]
    provenance: Provenance

    def has_topic(self, topic: str) -> bool:
        needle = topic.lower()
        return any(needle in t.lower() for t in self.topics)


@dataclass
class Canon:
    """A curated ordered set of excerpts: the community's standing selection."""

    name: str
    rationale: str = ""
    excerpt_ids: List[int] = field(default_factory=list)

    def curate(self, excerpt_id: int) -> None:
        if excerpt_id not in self.excerpt_ids:
            self.excerpt_ids.append(excerpt_id)

    def uncurate(self, excerpt_id: int) -> None:
        if excerpt_id in self.excerpt_ids:
            self.excerpt_ids.remove(excerpt_id)

    def __len__(self) -> int:
        return len(self.excerpt_ids)


class Florilegium:
    """The gathering: indexed excerpts + named canons over them."""

    def __init__(self):
        self._excerpts: Dict[int, Excerpt] = {}
        self._next_id = 0
        self._canons: Dict[str, Canon] = {}
        # pre-computed index: the library is treated as inaccessible
        self._topic_index: Dict[str, List[int]] = {}
        self._author_index: Dict[str, List[int]] = {}

    # -- gathering ----------------------------------------------------------
    def gather(
        self,
        text: str,
        topics: Sequence[str],
        provenance: Provenance,
    ) -> Excerpt:
        excerpt = Excerpt(
            id=self._next_id,
            text=text,
            topics=list(topics),
            provenance=provenance,
        )
        self._excerpts[self._next_id] = excerpt
        for topic in excerpt.topics:
            self._topic_index.setdefault(topic.lower(), []).append(excerpt.id)
        self._author_index.setdefault(provenance.author.lower(), []).append(excerpt.id)
        self._next_id += 1
        return excerpt

    def get(self, excerpt_id: int) -> Optional[Excerpt]:
        return self._excerpts.get(excerpt_id)

    # -- the pre-computed index ----------------------------------------------
    def by_topic(self, topic: str) -> List[Excerpt]:
        """Excerpts under a topic, via the index — no shelf-scanning."""
        ids = self._topic_index.get(topic.lower(), [])
        return [self._excerpts[i] for i in ids]

    def by_author(self, author: str) -> List[Excerpt]:
        ids = self._author_index.get(author.lower(), [])
        return [self._excerpts[i] for i in ids]

    def search(self, phrase: str) -> List[Excerpt]:
        """Full-text lookup over the gathered excerpts only."""
        needle = phrase.lower()
        return [e for e in self._excerpts.values() if needle in e.text.lower()]

    def topics(self) -> List[str]:
        return sorted(self._topic_index)

    # -- canons ---------------------------------------------------------------
    def canon(self, name: str, rationale: str = "") -> Canon:
        if name not in self._canons:
            self._canons[name] = Canon(name=name, rationale=rationale)
        return self._canons[name]

    def canon_text(self, name: str) -> List[Dict[str, str]]:
        """Render a canon in its curated order: passage + citation."""
        canon = self._canons.get(name)
        if canon is None:
            raise KeyError(f"no canon named {name!r}")
        rendered = []
        for eid in canon.excerpt_ids:
            excerpt = self._excerpts.get(eid)
            if excerpt is None:
                continue  # a canon reference may outlive a withdrawn excerpt
            rendered.append(
                {"text": excerpt.text, "citation": excerpt.provenance.citation()}
            )
        return rendered

    def __len__(self) -> int:
        return len(self._excerpts)
