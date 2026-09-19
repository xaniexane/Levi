"""Post-coordinate indexing: tag documents after collection, combine at query time.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #9)

The load-bearing mechanism of the edge-notched card deck, reimplemented
from scratch: no pre-built hierarchy, no folders. Documents ("cards")
enter the collection unindexed. Features ("holes") are assigned
*after* collection — at any time, by you or the assistant. A query
("needles") names features; the matching documents are the ones whose
holes line up with every needle. One shake searches the whole deck.

The mechanics here are set operations: AND is intersection (cards whose
notches let every needle pass — they fall), OR is union, NOT is
difference. The physical "shake" becomes :meth:`EdgeIndex.shake`, and
:meth:`EdgeIndex.shake_with_explain` shows which needles were used and
why each surviving card fell.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is post-coordinate indexing (index after
collection, combine features at query time). Not revived: physical
cards, hole-capacity limits, or overlapping-code false drops.
"""

from __future__ import annotations

import json
from pathlib import Path


ORIGIN = "levi-revival/edgeindex"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EdgeIndexError(Exception):
    """Base class for edge-index failures."""


class UnknownDocument(EdgeIndexError):
    """The document is not in the deck."""


class UnknownFeature(EdgeIndexError):
    """The feature is not registered on any card."""


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------


class EdgeIndex:
    """A deck of notched cards: documents tagged after collection."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.docs: dict[str, str] = {}  # doc_id -> title/note
        self.features: dict[str, set[str]] = {}  # feature -> doc_ids (the holes)
        self._tagged: dict[str, set[str]] = {}  # doc_id -> features
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "edgeindex.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.docs = dict(data.get("docs", {}))
        self.features = {k: set(v) for k, v in data.get("features", {}).items()}
        self._tagged = {k: set(v) for k, v in data.get("tagged", {}).items()}

    def save(self) -> Path:
        """Persist the deck. Only meaningful when constructed with a path."""
        if self.path is None:
            raise EdgeIndexError("no path: this deck is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "docs": self.docs,
                    "features": {k: sorted(v) for k, v in self.features.items()},
                    "tagged": {k: sorted(v) for k, v in self._tagged.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- collecting (indexing comes later) --------------------------------
    def add_document(self, doc_id: str, title: str = "") -> None:
        """File a card in the deck. No features assigned — post-coordinate
        indexing means the tagging happens after collection, not during."""
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        self.docs[doc_id] = title or doc_id
        self._tagged.setdefault(doc_id, set())

    # -- notching (tagging after collection) ------------------------------
    def tag(self, doc_id: str, *features: str) -> set[str]:
        """Notch holes for ``features`` on a card. New features register
        themselves — no vocabulary committee, the tagger decides. Returns
        the card's full feature set."""
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)
        for feature in features:
            name = feature.strip()
            if not name:
                raise ValueError("feature names must be non-empty")
            self.features.setdefault(name, set()).add(doc_id)
            self._tagged[doc_id].add(name)
        return set(self._tagged[doc_id])

    def untag(self, doc_id: str, *features: str) -> set[str]:
        """Fill a hole back in: remove features from a card."""
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)
        for feature in features:
            name = feature.strip()
            if name in self.features:
                self.features[name].discard(doc_id)
            self._tagged[doc_id].discard(name)
        return set(self._tagged[doc_id])

    def card_features(self, doc_id: str) -> set[str]:
        """Every feature notched on a card."""
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)
        return set(self._tagged[doc_id])

    def feature_cards(self, feature: str) -> set[str]:
        """Every card carrying a feature — the hole, seen from the side."""
        return set(self.features.get(feature, set()))

    # -- the needle-shake ---------------------------------------------------
    def _require_features(self, *features: str) -> None:
        for feature in features:
            if feature not in self.features:
                raise UnknownFeature(feature)

    def shake(
        self,
        require: tuple[str, ...] = (),
        any_of: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
    ) -> list[str]:
        """One shake of the deck. ``require`` needles must all pass through
        (Boolean AND — the falling cards), ``any_of`` needles let pooled
        selections through (OR), ``exclude`` needles hold cards up (NOT).

        With no needles at all, the whole deck drops — no constraint, no
        filtering."""
        needles = set(require) | set(any_of) | set(exclude)
        self._require_features(*needles)

        if require:
            survivors = set.intersection(*(self.features[f] for f in require))
        elif any_of:
            survivors = set()
        else:
            survivors = set(self.docs)

        if any_of:
            pooled = set.union(*(self.features[f] for f in any_of))
            survivors = survivors & pooled if require else pooled

        for feature in exclude:
            survivors -= self.features[feature]
        return sorted(survivors)

    def shake_with_explain(
        self,
        require: tuple[str, ...] = (),
        any_of: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
    ) -> dict:
        """The shake, narrated: which needles were pushed through which
        holes, and why each surviving card fell."""
        results = self.shake(require=require, any_of=any_of, exclude=exclude)
        needles = []
        for feature in require:
            needles.append(
                {
                    "feature": feature,
                    "role": "AND",
                    "would_fall": sorted(self.features[feature]),
                }
            )
        for feature in any_of:
            needles.append(
                {
                    "feature": feature,
                    "role": "OR",
                    "would_fall": sorted(self.features[feature]),
                }
            )
        for feature in exclude:
            needles.append(
                {
                    "feature": feature,
                    "role": "NOT",
                    "would_hold": sorted(self.features[feature]),
                }
            )
        return {
            "needles": needles,
            "deck_size": len(self.docs),
            "fell": results,
            "titles": {d: self.docs[d] for d in results},
        }

    def doc_count(self) -> int:
        return len(self.docs)


__all__ = [
    "ORIGIN",
    "EdgeIndexError",
    "UnknownDocument",
    "UnknownFeature",
    "EdgeIndex",
]
