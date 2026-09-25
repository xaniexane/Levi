"""Reversible prose — the L.W.P. press facility.

One sequence of word-palindromic clauses; every ordering is grammatical
prose; every start page in either direction is a story. This module is the
adopted, tested home of the proof of concept first built as standalone
scripts: the pool below is that hand-verified clause set, and every
function here is pure — stdlib only, deterministic, no I/O — so the press
runs anywhere offline.

A clause is admissible iff it is a word-level palindrome: it reads
identically forward and backward at the word level ("Tyrants fall, fall
tyrants"). Admissible clauses parse in both directions, so ANY ordering
of admissible clauses is grammatical prose, and order carries the story
arc — which is why the same words tell different stories on different
paths.

Reading paths:
  fall / return    full span, both directions — two stories, same words
  free directional any start clause, either direction, optional wraparound
  spiral           center-out alternating from any origin page

Acts (longer form):
  compose_acts     partition the pool into k contiguous acts (seeded cut
                   points), each with a seeded reading direction; labels
                   are neutral ordinals (Act I, Act II, ...) — no story
                   content lives in the form, only in his chapters
  act_slots        the palindromic act-visit order [1..k..1]: the book is
                   reversible at act altitude, the same way a clause is
                   reversible at word altitude
  act_book         the flat clause order of the composed acts — strictly
                   longer than any single-span reading when k >= 2
"""

from __future__ import annotations

import math
import random
import re
from typing import Dict, List, Sequence

_WORD = re.compile(r"[A-Za-z']+")


def words(text: str) -> List[str]:
    """Lowercased word tokens; punctuation is not part of the sequence."""
    return _WORD.findall(text.lower())


def is_palindromic_clause(clause: str) -> bool:
    """True iff the clause reads identically forward/backward at word level."""
    w = words(clause)
    return bool(w) and w == w[::-1]


def verify_pool(clauses: Sequence[str] = ()) -> List[str]:
    """Failure messages for inadmissible clauses; empty means the pool is clean."""
    pool = clauses if clauses else CLAUSES
    return [f"inadmissible clause: {c}" for c in pool
            if not is_palindromic_clause(c)]


# The hand-verified pool: 26 clauses, 104 words. Extend by appending new
# admissible clauses — every entry point re-verifies the pool first.
CLAUSES: List[str] = [
    "Dawn breaks, breaks dawn.",
    "Light rises, rises light.",
    "Birds sing, sing birds.",
    "Streets wake, wake streets.",
    "Bells ring, ring bells.",
    "Hope rises, rises hope.",
    "Crowds gather, gather crowds.",
    "Drums beat, beat drums.",
    "Swords clash, clash swords.",
    "Shields break, break shields.",
    "Walls fall, fall walls.",
    "Tyrants fall, fall tyrants.",
    "Chains break, break chains.",
    "Fire cleanses, cleanses fire.",
    "Ash falls, falls ash.",
    "Blood spills, spills blood.",
    "Voices rise, rise voices.",
    "Rivers rise, rise rivers.",
    "Storms rage, rage storms.",
    "Shadows lengthen, lengthen shadows.",
    "Light fails, fails light.",
    "Stars wake, wake stars.",
    "Dreams die, die dreams.",
    "Silence falls, falls silence.",
    "Seeds sleep, sleep seeds.",
    "Night comes, comes night.",
]


def full_paths(n: int) -> Dict[str, List[int]]:
    """1-based clause orders for the two full-span readings."""
    return {"fall": list(range(1, n + 1)), "return": list(range(n, 0, -1))}


def slice_path(start: int, direction: int, n: int,
               length: int | None = None, wraparound: bool = False) -> List[int]:
    """Free-directional path: 1-based start, direction +1/-1.

    Without wraparound the path runs to the edge (or ``length`` clauses).
    With wraparound it runs ``length`` clauses (default ``n``), circling
    past the ends — e.g. start=1, direction=-1 reads 1, n, n-1, ...
    """
    if not 1 <= start <= n:
        raise ValueError(f"start {start} out of range 1..{n}")
    if direction not in (1, -1):
        raise ValueError("direction must be +1 or -1")
    if wraparound:
        steps = n if length is None else length
        return [((start - 1 + direction * k) % n) + 1 for k in range(steps)]
    edge = n if direction == 1 else 1
    steps = abs(edge - start) + 1
    if length is not None:
        steps = min(steps, length)
    return [start + direction * k for k in range(steps)]


def spiral_path(origin: int, n: int) -> List[int]:
    """Center-out alternating path from a 1-based origin page.

    One step forward in time, one step back, widening until the whole
    span is held: origin, origin+1, origin-1, origin+2, ...
    """
    if not 1 <= origin <= n:
        raise ValueError(f"origin {origin} out of range 1..{n}")
    path = [origin]
    for k in range(1, n):
        for p in (origin + k, origin - k):
            if 1 <= p <= n and p not in path:
                path.append(p)
                if len(path) == n:
                    return path
    return path


def reading(order: Sequence[int], clauses: Sequence[str] = ()) -> List[str]:
    """Clause texts in path order (1-based indices)."""
    pool = clauses if clauses else CLAUSES
    return [pool[i - 1] for i in order]


def reading_words(order: Sequence[int], clauses: Sequence[str] = ()) -> List[str]:
    """The word sequence of a path — the reversible unit itself."""
    return [w for c in reading(order, clauses) for w in words(c)]


def story_counts(n: int) -> Dict[str, int]:
    """How many distinct stories n clauses hold, by path family."""
    return {
        "full_span": 2,
        "slices_either_direction": n * (n + 1),
        "wraparound_circular": 2 * n,
        "spiral_origins": n,
        "permutations": math.factorial(n),
    }


def press_run(count: int, seed: int,
              clauses: Sequence[str] = ()) -> List[Dict[str, object]]:
    """Print ``count`` verified books at once — the press run.

    Each book is one ordering of the pool: the same words, a different
    arc. The pool is verified first; any inadmissible clause halts the
    run with ValueError. Every emitted order is a verified permutation.
    Seeded RNG makes the run reproducible. Returns book dicts; writing
    files is left to the caller (this module does no I/O).
    """
    pool = list(clauses) if clauses else list(CLAUSES)
    failures = verify_pool(pool)
    if failures:
        raise ValueError(f"press halted: {'; '.join(failures)}")
    n = len(pool)
    rng = random.Random(seed)
    books = []
    for index in range(1, count + 1):
        order = list(range(1, n + 1))
        rng.shuffle(order)
        assert sorted(order) == list(range(1, n + 1))
        books.append({
            "index": index,
            "seed": seed,
            "order": order,
            "words": sum(len(words(c)) for c in pool),
            "clauses": n,
        })
    return books


# --- Acts: the longer form -------------------------------------------------
# An act holds a contiguous slice of the clause pool, read in its seeded
# direction. The acts partition the pool (every clause in exactly one act),
# and the book visits them in the palindromic slot order [1..k..1] — act
# altitude mirrors word altitude: reversible as a unit. Labels are neutral
# ordinals on purpose; story content belongs to his chapters, never the form.

_MAX_ACTS = 12  # mirrors the press cast bound: a book holds at most 12 acts

_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")


def act_slots(k: int) -> List[int]:
    """Palindromic act-visit order for k acts: [1, 2, ..., k, ..., 2, 1].

    Length 2k-1; the order is its own reverse, so the book reads the same
    act sequence forward and backward — reversible at act altitude.
    """
    if k < 1:
        raise ValueError(f"act count {k} out of range (need >= 1)")
    return list(range(1, k + 1)) + list(range(k - 1, 0, -1))


def compose_acts(
    k: int, seed: int, clauses: Sequence[str] = ()
) -> List[Dict[str, object]]:
    """Partition the pool into k contiguous acts with seeded cut points.

    The pool is verified first — an inadmissible clause halts composition
    with ValueError, same as press_run. Cut points are a seeded sample of
    the n-1 boundaries, so every act holds >= 1 clause and the acts
    partition 1..n exactly. Each act gets a seeded reading direction and
    a neutral ordinal label. k is bounded 1..12 (and never exceeds n).
    Deterministic: same (k, seed, pool) -> byte-identical acts.
    """
    pool = list(clauses) if clauses else list(CLAUSES)
    failures = verify_pool(pool)
    if failures:
        raise ValueError(f"composition halted: {'; '.join(failures)}")
    n = len(pool)
    if not 1 <= k <= min(_MAX_ACTS, n):
        raise ValueError(
            f"act count {k} out of range 1..{min(_MAX_ACTS, n)} (pool holds {n})"
        )
    rng = random.Random(seed)
    cuts = sorted(rng.sample(range(1, n), k - 1))
    boundaries = [0] + cuts + [n]
    directions = [rng.choice((1, -1)) for _ in range(k)]
    acts = []
    for i, (first, last, direction) in enumerate(
        zip(boundaries[:-1], boundaries[1:], directions, strict=True), start=1
    ):
        first, last = first + 1, last  # 1-based clause indices
        path = (
            list(range(first, last + 1))
            if direction == 1
            else list(range(last, first - 1, -1))
        )
        acts.append(
            {
                "act": f"Act {_ROMAN[i - 1]}",
                "index": i,
                "first": first,
                "last": last,
                "direction": direction,
                "path": path,
                "seed": seed,
            }
        )
    return acts


def act_book(acts: Sequence[Dict[str, object]]) -> List[int]:
    """Flat clause order of a composed book: each act slot's path in turn.

    Slots repeat acts (the palindrome), so clause indices recur — that is
    the form: for k >= 2 the book is strictly longer than any single-span
    reading (2n - size of the middle act > n).
    """
    if not acts:
        raise ValueError("act_book needs at least one act")
    slots = act_slots(len(acts))
    return [idx for s in slots for idx in acts[s - 1]["path"]]
