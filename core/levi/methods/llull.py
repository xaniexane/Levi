"""Llull's combinatorial art (Ars Magna): exhaustive idea generation.

History: Ramon Llull's 13th–14th-century Ars — a finite alphabet of primitive
concepts on rotating wheels; aligning them generated every pairwise
proposition mechanically. Leibniz admired the *generative ideal*; critics
found the output mostly vacuous. Claims that Llull "invented computing" are
interpretive overreach — treat the genealogy as suggestive, not causal.

In LEVI: use Llull's *form* with grounded primitives. Given a finite
alphabet (constraints, actors, resources…), :class:`Ars` generates the full
cross-product (pairs, triples, …) and the human (or caller) supplies the
judgment about which combinations are meaningful — via the ``judge``
callback in :meth:`Ars.generate`. Ideation by exhaustion, with LEVI doing
the bookkeeping.

Honesty: INSPIRATIONAL — the mechanism is real (systematic exhaustion), but
the value lives entirely in the caller's judgment; the machine cannot tell
a gem from word salad.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence


class Ars:
    """Combinatorial generator over a finite primitive alphabet."""

    def __init__(self, alphabet: Sequence[str]):
        cleaned = [str(a).strip() for a in alphabet]
        if not cleaned:
            raise ValueError("alphabet must contain at least one primitive")
        if any(not a for a in cleaned):
            raise ValueError("alphabet primitives must be non-empty strings")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("alphabet primitives must be distinct")
        self.alphabet: tuple[str, ...] = tuple(cleaned)

    def __len__(self) -> int:
        return len(self.alphabet)

    def pairs(self) -> Iterator[tuple[str, str]]:
        """All unordered distinct pairs (Llull's first figure)."""
        n = len(self.alphabet)
        for i in range(n):
            for j in range(i + 1, n):
                yield (self.alphabet[i], self.alphabet[j])

    def triples(self) -> Iterator[tuple[str, str, str]]:
        """All unordered distinct triples."""
        n = len(self.alphabet)
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    yield (self.alphabet[i], self.alphabet[j], self.alphabet[k])

    def combinations(self, size: int) -> Iterator[tuple[str, ...]]:
        """All unordered distinct combinations of ``size`` primitives."""
        if not isinstance(size, int) or size < 2:
            raise ValueError("combination size must be an integer >= 2")
        if size > len(self.alphabet):
            raise ValueError("combination size exceeds alphabet size")
        # iterative index-based combination generation (stdlib itertools-free)
        indices = list(range(size))
        n = len(self.alphabet)
        while True:
            yield tuple(self.alphabet[i] for i in indices)
            for pos in range(size - 1, -1, -1):
                if indices[pos] < n - size + pos:
                    indices[pos] += 1
                    for q in range(pos + 1, size):
                        indices[q] = indices[q - 1] + 1
                    break
            else:
                return

    def count(self, size: int) -> int:
        """How many combinations of ``size`` exist (so callers can budget)."""
        if not isinstance(size, int) or size < 2 or size > len(self.alphabet):
            raise ValueError("invalid combination size")
        from math import comb

        return comb(len(self.alphabet), size)

    def generate(
        self,
        size: int,
        judge: Callable[[tuple[str, ...]], bool] | None = None,
        limit: int = 10_000,
    ) -> list[tuple[str, ...]]:
        """Generate combinations, keeping only those the ``judge`` approves.

        The judge is the human's (or caller's) part of Llull's bargain: the
        machine enumerates, the judge decides. Without a judge, everything
        is returned — word salad included, honestly labeled as unjudged.
        ``limit`` caps runaway alphabets (fail-safe, reported).
        """
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        kept: list[tuple[str, ...]] = []
        for combo in self.combinations(size):
            if judge is None or judge(combo):
                kept.append(combo)
            if len(kept) >= limit:
                break
        return kept

    def render(self, combo: Iterable[str], template: str = "{a} × {b}") -> str:
        """Render a pair as a proposition skeleton for the judge to evaluate."""
        items = list(combo)
        if len(items) != 2:
            return " × ".join(items)
        return template.format(a=items[0], b=items[1])
