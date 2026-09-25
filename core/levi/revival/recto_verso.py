"""Tension-set records: recto (content) + verso (provenance) on every write.

Studied from: lost-crafts-20260916/report.md [Batch 4] (Parchment / Vellum)

The studied shape: parchment is collagen stretched under tension and
dried — the material *remembers* the tension it was made under. A leaf
has two faces: recto (the writing side) and verso (the back, which
later carried notes about the text itself).

LEVI-native re-expression: every write produces a two-faced record.
The **recto** is the content. The **verso** is a provenance index
stamped at write time: author, source, timestamp, and a hash chaining
back to the previous record (the "tension" line that keeps the whole
hide aligned). Both faces are queryable: search content on the recto,
search provenance on the verso.

The tension metaphor is operationalized honestly: each record carries a
**tension score** — how well the content's self-declared claims match
the weight of its provenance (e.g. a record claiming high confidence
but citing a weak source is slack; strong claims on strong sources are
taut). Slack records are flagged, not rejected: LEVI surfaces the
mismatch and lets the reader decide.

Operations:

* ``Hide.write(content, author, source, claims)`` — make a record
* ``Hide.read_recto(id) / Hide.read_verso(id)`` — either face
* ``Hide.search_recto(keyword) / Hide.search_verso(**fields)`` — query
  content or provenance independently
* ``Hide.chain_ok()`` — verify the tension line (hash chain)
* ``Hide.slack()`` — records whose tension score falls below the bar

Honest limits: the tension score is a heuristic over declared fields —
it checks consistency of what was *declared*, it cannot verify the
truth of the source itself. Hashing is SHA-256 from the standard
library.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


ORIGIN = "levi-revival/recto-verso"

# source-weight table: how much trust a provenance source carries (0..1)
_SOURCE_WEIGHT: Dict[str, float] = {
    "primary": 1.0,
    "measured": 0.9,
    "cited": 0.7,
    "recalled": 0.5,
    "hearsay": 0.3,
    "unknown": 0.1,
}

# claim-strength the content may declare (0..1)
_CLAIM_LEVEL: Dict[str, float] = {
    "fact": 1.0,
    "estimate": 0.6,
    "guess": 0.3,
    "rumor": 0.1,
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Recto:
    """The writing side: the content itself."""

    text: str
    claim: str  # one of _CLAIM_LEVEL keys


@dataclass
class Verso:
    """The back of the leaf: the provenance index, stamped at write time."""

    author: str
    source: str  # one of _SOURCE_WEIGHT keys
    written_at: str
    prev_hash: str
    self_hash: str = ""

    def weight(self) -> float:
        return _SOURCE_WEIGHT[self.source]


@dataclass
class Leaf:
    """One tension-set record: recto content + verso provenance."""

    id: int
    recto: Recto
    verso: Verso

    def tension(self) -> float:
        """Alignment of claim strength vs provenance weight, 0..1.

        Taut (1.0) = the claim asks no more than the source can carry.
        Slack (<0.5) = strong words on weak backing.
        """
        claim = _CLAIM_LEVEL[self.recto.claim]
        weight = self.verso.weight()
        if claim <= weight:
            return 1.0
        return round(max(0.0, weight / claim), 3)


@dataclass
class Hide:
    """The stretched skin: an ordered chain of two-faced records."""

    leaves: List[Leaf] = field(default_factory=list)
    slack_bar: float = 0.5

    def _tip(self) -> str:
        return self.leaves[-1].verso.self_hash if self.leaves else "TENSION::start"

    def write(
        self, content: str, author: str, source: str = "unknown", claim: str = "guess"
    ) -> Leaf:
        """Make a record: recto content, verso provenance, both queryable."""
        if not content or not content.strip():
            raise ValueError("content must be non-empty")
        if source not in _SOURCE_WEIGHT:
            raise ValueError(f"source must be one of {sorted(_SOURCE_WEIGHT)}")
        if claim not in _CLAIM_LEVEL:
            raise ValueError(f"claim must be one of {sorted(_CLAIM_LEVEL)}")
        verso = Verso(
            author=author,
            source=source,
            written_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            prev_hash=self._tip(),
        )
        payload = f"{len(self.leaves)}|{content}|{claim}|{author}|{source}|{verso.written_at}|{verso.prev_hash}"
        verso.self_hash = _hash(payload)
        leaf = Leaf(
            id=len(self.leaves), recto=Recto(text=content, claim=claim), verso=verso
        )
        self.leaves.append(leaf)
        return leaf

    # -- either face ------------------------------------------------------------------
    def read_recto(self, id: int) -> Recto:
        return self._leaf(id).recto

    def read_verso(self, id: int) -> Verso:
        return self._leaf(id).verso

    def _leaf(self, id: int) -> Leaf:
        if not (0 <= id < len(self.leaves)):
            raise ValueError(f"no leaf {id}")
        return self.leaves[id]

    # -- querying ----------------------------------------------------------------------
    def search_recto(self, keyword: str) -> List[Leaf]:
        """Find records by content."""
        kw = keyword.lower()
        return [leaf for leaf in self.leaves if kw in leaf.recto.text.lower()]

    def search_verso(
        self, author: Optional[str] = None, source: Optional[str] = None
    ) -> List[Leaf]:
        """Find records by provenance."""
        out = self.leaves
        if author is not None:
            out = [leaf for leaf in out if leaf.verso.author == author]
        if source is not None:
            out = [leaf for leaf in out if leaf.verso.source == source]
        return out

    # -- the tension line ---------------------------------------------------------------
    def chain_ok(self) -> bool:
        """True if every record still links to the one before it."""
        prev = "TENSION::start"
        for leaf in self.leaves:
            if leaf.verso.prev_hash != prev:
                return False
            prev = leaf.verso.self_hash
        return True

    def slack(self) -> List[Leaf]:
        """Records stretched past the bar: strong claims on weak backing."""
        return [leaf for leaf in self.leaves if leaf.tension() < self.slack_bar]

    def tension_report(self) -> List[Dict[str, object]]:
        return [
            {
                "id": leaf.id,
                "claim": leaf.recto.claim,
                "source": leaf.verso.source,
                "tension": leaf.tension(),
                "taut": leaf.tension() >= self.slack_bar,
            }
            for leaf in self.leaves
        ]
