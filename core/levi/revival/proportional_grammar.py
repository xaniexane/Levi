"""A proportional design grammar: one scale, a whole set, reproducible.

Studied from: lost-crafts-20260916/report.md [Games standing theme]
(Staunton chess carving)

The studied shape: the Staunton pattern is not a set of drawings — it
is a *grammar*. Every piece derives from a height ladder (king tallest
down to pawn shortest) and proportion rules like the 40% base rule
(base diameter ≈ 40% of the piece's height). Any carver who learns the
grammar can reproduce the set at any scale without the original pieces
in front of them.

LEVI-native re-expression: a grammar that generates a full, coherent
piece set from a single scale parameter and *validates* candidate specs
against its rules. The grammar is:

* **height ladder** — king > queen > rook > bishop > knight > pawn,
  with fixed relative heights (king = 1.0, the rest as fractions)
* **40% base rule** — base diameter = 0.40 × height, every piece
* **headroom rule** — pieces must stay distinguishable: adjacent pieces
  on the ladder differ by at least 6% of the king's height
* **crown mark** — the king carries the tallest finial (its signature),
  the queen's coronet sits lower; finials are ordered, not equal

Operations:

* ``grammar(scale_mm)`` — build the canonical spec for a set
* ``spec_for(piece, scale_mm)`` — one piece's dimensions
* ``validate(spec)`` — list of rule violations (empty = canonical)
* ``ladder(scale_mm)`` — ordered (piece, height) pairs, tallest first

Honest limits: a design grammar, not a carving guide — it outputs
dimensions and pass/fail rules, not toolpaths. "Distinctness" is
measured on heights only; real sets also differ by silhouette, which
this model leaves to the carver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/proportional-grammar"

# canonical height ladder: piece -> fraction of king height.
# Ordered to match _FINIAL_ORDER, every step >= 6% of king height.
_LADDER: Dict[str, float] = {
    "king": 1.00,
    "queen": 0.92,
    "bishop": 0.82,
    "rook": 0.74,
    "knight": 0.64,
    "pawn": 0.52,
}

_BASE_RATIO = 0.40  # the 40% base rule
_MIN_GAP = 0.06  # minimum ladder step, as fraction of king height
_FINIAL_ORDER = ("king", "queen", "bishop", "rook", "knight", "pawn")


@dataclass
class PieceSpec:
    """Dimensions of one piece, derived from the grammar."""

    piece: str
    height: float  # mm
    base_dia: float  # mm — grammar says 0.40 * height
    finial_rank: int  # position in the finial order (0 = tallest)

    def as_dict(self) -> Dict[str, float]:
        return {
            "piece": self.piece,
            "height": round(self.height, 2),
            "base_dia": round(self.base_dia, 2),
            "finial_rank": self.finial_rank,
        }


def spec_for(piece: str, scale_mm: float) -> PieceSpec:
    """Derive one piece's dimensions from the king height `scale_mm`."""
    if piece not in _LADDER:
        raise ValueError(f"unknown piece {piece!r}; ladder is {sorted(_LADDER)}")
    if scale_mm <= 0:
        raise ValueError("scale must be positive")
    height = round(scale_mm * _LADDER[piece], 2)
    return PieceSpec(
        piece=piece,
        height=height,
        base_dia=round(height * _BASE_RATIO, 2),
        finial_rank=_FINIAL_ORDER.index(piece),
    )


def grammar(scale_mm: float) -> Dict[str, PieceSpec]:
    """The whole canonical set from one scale number."""
    return {piece: spec_for(piece, scale_mm) for piece in _LADDER}


def ladder(scale_mm: float) -> List[Tuple[str, float]]:
    """Ordered (piece, height) pairs, tallest first."""
    return sorted(
        ((piece, spec_for(piece, scale_mm).height) for piece in _LADDER),
        key=lambda t: t[1],
        reverse=True,
    )


def validate(specs: Dict[str, PieceSpec]) -> List[str]:
    """Check a candidate set against the grammar. Empty list = canonical.

    Accepts any mapping of piece name -> PieceSpec (e.g. a hand-tuned
    set); reports every rule it breaks.
    """
    problems: List[str] = []
    missing = [p for p in _LADDER if p not in specs]
    if missing:
        problems.append(f"missing pieces from the ladder: {missing}")
    for name, spec in specs.items():
        if name not in _LADDER:
            problems.append(f"{name!r} is not in the grammar's ladder")
            continue
        if spec.piece != name:
            problems.append(f"spec key {name!r} holds piece {spec.piece!r}")
        # 40% base rule
        expected_base = spec.height * _BASE_RATIO
        if abs(spec.base_dia - expected_base) > 0.01 * spec.height:
            problems.append(
                f"{name}: base {spec.base_dia} breaks the 40% rule "
                f"(expected {expected_base:.2f} for height {spec.height})"
            )
        # ladder order + headroom
    ordered = [p for p in _FINIAL_ORDER if p in specs]
    king_h = specs["king"].height if "king" in specs else None
    for upper, lower in zip(ordered, ordered[1:], strict=False):
        uh, lh = specs[upper].height, specs[lower].height
        if uh <= lh:
            problems.append(f"{upper} ({uh}) is not taller than {lower} ({lh})")
        elif king_h and (uh - lh) < _MIN_GAP * king_h:
            problems.append(
                f"{upper}/{lower} gap {uh - lh:.2f} below headroom "
                f"({_MIN_GAP * king_h:.2f})"
            )
    # finial order
    ranks = [specs[p].finial_rank for p in ordered]
    if ranks != sorted(ranks):
        problems.append("finial ranks are not ordered with the ladder")
    # king wears the tallest finial
    if "king" in specs and specs["king"].finial_rank != 0:
        problems.append("king must carry finial rank 0 (the tallest)")
    return problems
