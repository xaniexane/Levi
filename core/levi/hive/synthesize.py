"""Hive intelligence — the many thinking as one, mechanically.

``reasoning_round(seats, topic, contributions)``: seats contribute
reflection outputs (statements); the hive synthesizes with rules only:

  * corroboration counting — the same claim (exact or near-duplicate,
    Jaccard >= 0.7 on content words) made by >= 2 seats becomes a
    consensus item with per-seat supporters;
  * conflict surfacing — within a corroborated cluster, statements
    that differ by negation ("not", "never", "no", "n't", "cannot")
    are surfaced as a conflict WITH provenance on both sides;
  * no smoothing — every other statement is listed as an individual
    position with its seat's name on it. Disagreements are shown, not
    averaged away.

Output carries per-seat contribution records. Mode is always
reported ("rules"). Every emitted claim passes the sentience-claim
guard — the hive synthesizes functional statements, never phenomenal
ones.

This is Levi's head-function made mechanical. It does not make any
seat multi-substrate and does not blur the MSSI reservation: the
synthesis is a function over contributed texts, not a new mind.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from levi.founders import roster
from levi.growth import guards as _guards
from levi.growth import journal as _journal

_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset(
    "the and for with that this from have has had were was are but not you your "
    "levi when what which while where their there then than them they our out can "
    "will would should could about into over after before between through during "
    "never cannot".split()
)
_NEG = re.compile(
    r"\b(not|never|no|n't|cannot|isn't|aren't|don't|doesn't|won't)\b", re.I
)
_NEAR_DUP = 0.7


def _words(text: str) -> frozenset:
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOP)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def reasoning_round(
    seats: List[str],
    topic: str,
    contributions: Dict[str, List[str]],
    *,
    round_id: str = "",
) -> Dict[str, Any]:
    """One collective reasoning round. Returns the synthesis.

    ``contributions`` maps seat key -> list of statement strings.
    Every seat in ``seats`` must appear (an empty list is a valid
    contribution — silence is recorded, not punished). Unknown seats
    raise KeyError (deny-open).
    """
    for k in seats:
        roster.get_seat(k)
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("reasoning_round: topic must be a non-empty string")
    if not isinstance(contributions, dict):
        raise ValueError("reasoning_round: contributions must be a dict")
    missing = [k for k in seats if k not in contributions]
    if missing:
        raise ValueError("reasoning_round: no contributions from seats %r" % missing)
    for k, stmts in contributions.items():
        if k not in seats:
            raise ValueError(
                "reasoning_round: contributions from non-round seat %r" % k
            )
        if not isinstance(stmts, list) or not all(isinstance(s, str) for s in stmts):
            raise ValueError(
                "reasoning_round: contributions[%r] must be a list of strings" % k
            )

    round_id = round_id or _journal.new_cycle_id()

    # flatten: (seat, statement, words)
    items: List[Tuple[str, str, frozenset]] = []
    for seat in seats:
        for s in contributions[seat]:
            s = s.strip()
            if not s:
                continue
            _guards.assert_no_sentience_claim(s)  # guard: never synthesize this
            items.append((seat, s, _words(s)))

    # cluster near-duplicates
    clusters: List[List[int]] = []
    for i in range(len(items)):
        placed = False
        for c in clusters:
            if _jaccard(items[i][2], items[c[0]][2]) >= _NEAR_DUP:
                c.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    consensus: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    positions: List[Dict[str, Any]] = []
    for c in clusters:
        supporters = sorted({items[i][0] for i in c})
        if len(supporters) >= 2:
            stmts = [items[i][1] for i in c]
            neg = [s for s in stmts if _NEG.search(s)]
            if neg and len(neg) != len(stmts):
                # same claim cluster, but some seats negate it —
                # surface the disagreement with provenance, both sides
                conflicts.append(
                    {
                        "claim": items[c[0]][1],
                        "asserted_by": sorted(
                            {items[i][0] for i in c if items[i][1] not in neg}
                        ),
                        "negated_by": sorted(
                            {items[i][0] for i in c if items[i][1] in neg}
                        ),
                        "negated_statements": neg,
                        "note": "the same claim is asserted and negated — "
                        "shown, not smoothed",
                    }
                )
            else:
                consensus.append(
                    {
                        "claim": items[c[0]][1],
                        "supporters": supporters,
                        "count": len(supporters),
                    }
                )
        else:
            seat, stmt, _w = items[c[0]]
            positions.append({"seat": seat, "statement": stmt})

    return {
        "round_id": round_id,
        "topic": topic.strip(),
        "mode": "rules",
        "seats": len(seats),
        "contributions": {k: list(v) for k, v in contributions.items()},
        "consensus": consensus,
        "conflicts": conflicts,
        "positions": positions,
        "note": "mechanical synthesis: corroboration counted, conflicts "
        "surfaced with provenance, disagreements never smoothed. No "
        "seat is made multi-substrate by participating.",
    }
