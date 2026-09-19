"""The Stumble button: one-button serendipity; delight is the only metric.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #4] (the stumble button: one-button serendipity across archive,
bookmarks, feeds; the only metric is delight).

This is an original, from-scratch implementation for LEVI. A ``Vault`` holds
``Artifact``s in named collections (``archive``, ``bookmarks``, ``feeds``,
or anything the owner defines). ``stumble()`` returns one artifact at
random — weighted to favor underexplored shelves so the button keeps
surprising rather than re-serving the same hits.

The only metric is delight, recorded as honestly as possible: after a
stumble the owner may log ``delight`` or ``meh`` (``record_reaction``). The
module tracks per-collection delight rates and, over time, gently biases the
draw toward collections that have historically delighted — never toward
"engagement", watch-time, or anything else. There is no profile, no
personalization vector, no model: just counts.

Seeding: pass ``seed=`` for a reproducible draw order (tests, rituals).
Otherwise draws use the global random stream.

Honest limits:
- "Delight" is a self-reported label, not a detected emotion. The module
  counts what the owner says; it cannot tell whether they really delighted.
- The delight bias is gentle by construction (Laplace smoothing): a new
  collection with zero history still gets drawn, so the button never
  collapses onto one shelf.
- Draws are uniform-within-collection, then collection-weighted: popularity
  *within* a shelf never matters.

Public surface:
- ``Artifact``, ``Vault``: ``add``, ``stumble``, ``record_reaction``,
  ``delight_rates``, ``collections``, ``stats``.

stdlib-only. No network. Deterministic when seeded.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/stumble-button"


@dataclass
class Artifact:
    """One stumbleable thing, filed on one shelf of the vault."""

    id: int
    title: str
    collection: str
    locator: str = ""  # url, path, note — wherever the thing lives
    note: str = ""


class VaultError(ValueError):
    """Raised when an artifact or reaction reference is invalid."""


class Vault:
    """Collections of artifacts plus the one-button draw."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._artifacts: Dict[int, Artifact] = {}
        self._by_collection: Dict[str, List[int]] = {}
        self._next_id = 1
        # delight bookkeeping: per-collection (delights, total draws)
        self._delights: Dict[str, int] = {}
        self._draws: Dict[str, int] = {}
        self._rng = random.Random(seed)
        self._last_draw: Optional[int] = None

    # -- stocking the vault ---------------------------------------------------

    def add(
        self,
        title: str,
        collection: str,
        locator: str = "",
        note: str = "",
    ) -> Artifact:
        title = title.strip()
        collection = collection.strip()
        if not title:
            raise VaultError("an artifact needs a title")
        if not collection:
            raise VaultError("an artifact needs a collection")
        artifact = Artifact(
            id=self._next_id,
            title=title,
            collection=collection,
            locator=locator.strip(),
            note=note.strip(),
        )
        self._artifacts[artifact.id] = artifact
        self._by_collection.setdefault(collection, []).append(artifact.id)
        self._next_id += 1
        return artifact

    def get(self, artifact_id: int) -> Artifact:
        try:
            return self._artifacts[artifact_id]
        except KeyError:
            raise VaultError(f"no artifact #{artifact_id}") from None

    def collections(self) -> List[str]:
        return sorted(self._by_collection)

    # -- the button -------------------------------------------------------------

    def _collection_weight(self, collection: str) -> float:
        """Delight-biased weight with Laplace smoothing: new shelves still draw."""
        delights = self._delights.get(collection, 0)
        draws = self._draws.get(collection, 0)
        # (delights + 1) / (draws + 2): starts at 0.5 for unknown shelves.
        return (delights + 1) / (draws + 2)

    def stumble(self) -> Artifact:
        """One artifact. Serendipity, gently steered by past delight."""
        if not self._artifacts:
            raise VaultError("the vault is empty — add artifacts first")
        collections = list(self._by_collection)
        weights = [self._collection_weight(c) for c in collections]
        chosen = self._rng.choices(collections, weights=weights, k=1)[0]
        artifact_id = self._rng.choice(self._by_collection[chosen])
        self._draws[chosen] = self._draws.get(chosen, 0) + 1
        self._last_draw = artifact_id
        return self._artifacts[artifact_id]

    # -- the only metric ----------------------------------------------------------

    def record_reaction(self, artifact_id: int, delighted: bool) -> None:
        """Log whether the last stumble delighted. Self-reported, counted."""
        artifact = self.get(artifact_id)
        if delighted:
            self._delights[artifact.collection] = (
                self._delights.get(artifact.collection, 0) + 1
            )

    def delight_rates(self) -> Dict[str, float]:
        """Observed delight per collection. Unknown shelves report 0.5."""
        return {c: self._collection_weight(c) for c in self._by_collection}

    def stats(self) -> Dict[str, object]:
        return {
            "artifacts": len(self._artifacts),
            "collections": self.collections(),
            "draws": dict(self._draws),
            "delights": dict(self._delights),
            "delight_rates": self.delight_rates(),
        }

    def __len__(self) -> int:
        return len(self._artifacts)
