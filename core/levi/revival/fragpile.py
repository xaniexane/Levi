"""fragpile — dump-now fragment recall.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 15).

The load-bearing idea: capture is frictionless — you dump a text
fragment now and think later. Recall is by typing *any fragment you
remember*: the pile narrows as you type, ranking by match quality and
recency.

LEVI's take: ``FragPile`` is one in-memory pile of fragments with
timestamps. ``narrow(query)`` is an incremental substring filter —
every extra character can only shrink the result set — scored by
match quality (coverage of the query, earliness of the hit) blended
with recency. Nothing is filed, tagged, or organized: the query *is*
the index.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

ORIGIN = "levi-revival/fragpile"


@dataclass
class Fragment:
    """One dumped fragment."""

    text: str
    seq: int  # insertion order: higher == more recent


@dataclass
class PileStats:
    fragments: int


class FragPile:
    """A single pile of text fragments with progressive recall."""

    def __init__(self) -> None:
        self._fragments: List[Fragment] = []
        self._seq = 0

    # -- capture -------------------------------------------------------
    def dump(self, text: str) -> Fragment:
        """Dump a fragment now. No filing, no tags, no questions."""
        text = text.strip()
        if not text:
            raise ValueError("cannot dump an empty fragment")
        self._seq += 1
        frag = Fragment(text=text, seq=self._seq)
        self._fragments.append(frag)
        return frag

    def stats(self) -> PileStats:
        return PileStats(fragments=len(self._fragments))

    # -- recall --------------------------------------------------------
    def _score(self, frag: Fragment, query: str) -> float:
        """Match quality x recency. Higher is better."""
        text = frag.text.lower()
        q = query.lower()
        pos = text.find(q)
        if pos == -1:
            return 0.0
        coverage = len(q) / max(len(text), 1)  # query covers how much
        earliness = 1.0 / (1.0 + pos)  # hit near the start wins
        recency = frag.seq / max(self._seq, 1)  # 0..1
        return 0.5 * coverage + 0.3 * earliness + 0.2 * recency

    def narrow(self, query: str) -> List[Fragment]:
        """Recall by typing any remembered fragment.

        Each call is an incremental substring filter: results contain the
        query as a contiguous substring, ranked by match quality blended
        with recency. An empty query returns the pile, newest first.
        """
        if not query.strip():
            return sorted(self._fragments, key=lambda f: -f.seq)
        scored = [
            (self._score(f, query), f)
            for f in self._fragments
            if query.lower() in f.text.lower()
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [frag for _, frag in scored]

    def narrow_step(self, previous: List[Fragment], char: str) -> List[Fragment]:
        """One keystroke deeper: re-filter the previous result set.

        Because a longer query is a stricter substring, narrowing the
        *previous* results with the accumulated query gives the same
        answer as re-scanning the pile — this is the progressive
        narrowing the mechanism promises.
        """
        if not previous:
            return []
        last_query = getattr(self, "_last_query", "")
        query = last_query + char
        self._last_query = query
        return self.narrow(query)

    def begin_typing(self) -> None:
        """Reset the keystroke accumulator for a fresh progressive query."""
        self._last_query = ""
