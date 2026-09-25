"""LEVI's combinatorial ideation engine: enumerate every k-combination, then judge.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #2)

The old mechanism: take a small set of primitives (subjects, predicates,
values — anything discrete) and exhaustively combine them by a fixed
procedure, producing every possible pairing the procedure allows. The
exhaustion is the point: no lucky accidents, no missed pairs. A separate
judging step then marks which combinations are *meaningful* — the machine
enumerates, a judge evaluates.

``combinations`` enumerates k-combinations of the primitive set in a fixed,
deterministic order (sorted-lexicographic on the canonical order of the
primitives). ``run`` walks every combination and applies the judging hook —
a callable taking the combination tuple and returning True/False — then
``report`` returns the meaningful set, grouped and counted.

Determinism is a hard property here, not a vibe: same primitives, same k,
same judge ⇒ same report, every run. Judges that are pure functions keep
the whole pipeline reproducible; stateful judges are the caller's business
and their own warning label.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, Tuple

ORIGIN = "levi-revival/combart"

Judge = Callable[[Tuple[Any, ...]], bool]


@dataclass
class Combination:
    """One enumerated combination and the judge's verdict on it."""

    members: Tuple[Any, ...]
    meaningful: bool = False


@dataclass
class IdeationRun:
    """The full result of one enumerate-and-judge pass."""

    primitives: List[Any]
    k: int
    all_combinations: List[Combination] = field(default_factory=list)

    @property
    def meaningful(self) -> List[Tuple[Any, ...]]:
        return [c.members for c in self.all_combinations if c.meaningful]

    @property
    def total(self) -> int:
        return len(self.all_combinations)

    @property
    def judged(self) -> int:
        return sum(1 for c in self.all_combinations if c.meaningful)

    def report(self) -> Dict[str, Any]:
        return {
            "primitives": list(self.primitives),
            "k": self.k,
            "total_combinations": self.total,
            "meaningful_count": self.judged,
            "meaningful": [list(m) for m in self.meaningful],
        }


def canonical_order(primitives: Sequence[Any]) -> List[Any]:
    """Fixed, deterministic ordering of the primitive set (deduped)."""
    seen: Dict[Any, None] = {}
    for p in primitives:
        seen[p] = None
    ordered = list(seen.keys())
    try:
        return sorted(ordered)
    except TypeError:
        return ordered  # mixed types: fall back to first-seen order


def enumerate_combinations(primitives: Sequence[Any], k: int) -> List[Tuple[Any, ...]]:
    """All k-combinations in a fixed deterministic order.

    Raises ValueError if k is out of range.
    """
    ordered = canonical_order(primitives)
    if k < 1 or k > len(ordered):
        raise ValueError(f"k must be in 1..{len(ordered)}, got {k}")
    return [tuple(c) for c in itertools.combinations(ordered, k)]


def run(
    primitives: Sequence[Any],
    k: int,
    judge: Judge,
    judge_hint: str = "",
) -> IdeationRun:
    """Enumerate every k-combination, apply the judge, return the run.

    The judge is a callable(combination_tuple) -> bool. A True verdict marks
    the combination meaningful; exceptions raised by the judge are NOT
    swallowed — a broken judge should be loud, not silently productive.
    """
    ordered = canonical_order(primitives)
    result = IdeationRun(primitives=ordered, k=k)
    for members in enumerate_combinations(ordered, k):
        verdict = bool(judge(members))
        result.all_combinations.append(Combination(members=members, meaningful=verdict))
    return result


def report(run_result: IdeationRun) -> Dict[str, Any]:
    """The meaningful set plus counts, ready for LEVI's downstream tools."""
    return run_result.report()


def pair_judge(meaningful_pairs: Sequence[Sequence[Any]]) -> Judge:
    """Build a deterministic judge from an explicit allow-list of pairs."""
    allowed = {tuple(sorted(p)) for p in meaningful_pairs}

    def judge(members: Tuple[Any, ...]) -> bool:
        try:
            key = tuple(sorted(members))
        except TypeError:
            key = members
        return key in allowed

    judge.__name__ = "pair_judge"
    return judge


def thematic_judge(required: Sequence[Any]) -> Judge:
    """Build a judge that marks meaningful any combination containing one
    of the required anchor members — a thematic filter over the enumeration."""
    anchors = set(required)

    def judge(members: Tuple[Any, ...]) -> bool:
        return any(m in anchors for m in members)

    judge.__name__ = "thematic_judge"
    return judge
