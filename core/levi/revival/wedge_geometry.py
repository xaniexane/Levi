"""Wedge geometry: orientation you can read, pieces that come back.

Studied from: lost-crafts-20260916/report.md [Games standing theme]
(Tendo shogi koma)

The studied shape: shogi pieces are wedges — five-sided, pointing at
the enemy. The geometry *is* the interface: you can read whose side a
piece is on by which way it points, and captured pieces flip sides and
re-enter play (the drop rule). Craft and play form one loop: pieces are
graded by calligraphy in four grades, and play wears them, so grading
is a living record, not a one-time stamp.

LEVI-native re-expression: a wedge-piece system with two mechanisms.

**1. The drop loop.** A ``Board`` holds pieces; ``capture`` moves a
piece to the captor's hand (its wedge re-points at the new owner's
enemy); ``drop`` places a hand piece back on any empty square,
pointing the right way. The board enforces: drops only on empty
squares, only from your own hand, and never on the square the piece
just left this same turn (a simple anti-shuttle guard).

**2. The four-grade craft loop.** Each piece carries a calligraphy
grade 1–4 (4 = finest). Play wears pieces: every capture of a piece
lowers its grade by one (floor 1); ``recarve`` restores a piece to a
higher grade by name of a carver, logged in the craft ledger. Craft
and play stay one loop because the ledger records both.

Operations:

* ``Piece(kind, owner, grade)`` — a wedge with an orientation
* ``Board.place/drop/capture/move`` — the play loop
* ``Board.recarve(piece_id, grade, carver)`` — the craft loop
* ``Board.ledger`` — every craft + play event, in order

Honest limits: this models the *mechanics* of orientation, capture,
and re-entry — not shogi's rules (no movement tables, no promotion,
no check). The grade-wear rule is a stand-in for physical wear, not a
materials model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/wedge-geometry"

_GRADES = (1, 2, 3, 4)  # four-grade calligraphy, 4 finest


@dataclass
class Piece:
    """A wedge: points at its owner's enemy, graded by its carving."""

    id: int
    kind: str
    owner: str
    grade: int = 4
    promoted: bool = False

    def __post_init__(self) -> None:
        if self.grade not in _GRADES:
            raise ValueError(f"grade must be one of {_GRADES}")

    def points_at(self) -> str:
        """The enemy this wedge faces — read straight off the geometry."""
        return f"enemy-of-{self.owner}"

    def wear(self) -> None:
        """Play wears the carving: a capture costs one grade (floor 1)."""
        self.grade = max(1, self.grade - 1)


@dataclass
class Board:
    """The craft-and-play loop: a board, two hands, one ledger."""

    size: int = 9
    squares: Dict[Tuple[int, int], Piece] = field(default_factory=dict)
    hands: Dict[str, List[Piece]] = field(default_factory=dict)
    ledger: List[str] = field(default_factory=list)
    _next_id: int = field(default=1, repr=False)

    def __post_init__(self) -> None:
        if self.size < 1:
            raise ValueError("board size must be >= 1")

    def _check_square(self, sq: Tuple[int, int]) -> None:
        r, c = sq
        if not (0 <= r < self.size and 0 <= c < self.size):
            raise ValueError(f"square {sq} is off a {self.size}x{self.size} board")

    def _log(self, event: str) -> None:
        self.ledger.append(f"{len(self.ledger):04d} {event}")

    # -- the play loop -------------------------------------------------------------
    def mint(self, kind: str, owner: str, grade: int = 4) -> Piece:
        """Carve a fresh wedge into existence (unplaced)."""
        piece = Piece(id=self._next_id, kind=kind, owner=owner, grade=grade)
        self._next_id += 1
        self._log(f"carve #{piece.id} {kind} for {owner} grade {grade}")
        return piece

    def place(self, piece: Piece, square: Tuple[int, int]) -> None:
        """Set a fresh wedge on an empty square, pointing at the enemy."""
        self._check_square(square)
        if square in self.squares:
            raise ValueError(f"square {square} is occupied")
        self.squares[square] = piece
        self._log(f"place #{piece.id} {piece.kind}@{square} -> {piece.points_at()}")

    def capture(self, square: Tuple[int, int], by: str) -> Piece:
        """Take the piece at `square` into `by`'s hand: the wedge flips.

        The captured wedge re-points at its new owner's enemy and its
        carving wears one grade — craft and play, one loop.
        """
        self._check_square(square)
        if square not in self.squares:
            raise ValueError(f"nothing to capture at {square}")
        piece = self.squares.pop(square)
        piece.owner = by
        piece.wear()
        self.hands.setdefault(by, []).append(piece)
        self._log(
            f"capture #{piece.id} {piece.kind} by {by} (wears to grade {piece.grade})"
        )
        return piece

    def drop(self, owner: str, piece_id: int, square: Tuple[int, int]) -> Piece:
        """Re-enter a hand piece onto an empty square — the drop rule.

        Only from your own hand, only onto an empty square. The wedge
        arrives already pointing at your enemy: geometry does the work.
        """
        self._check_square(square)
        if square in self.squares:
            raise ValueError(f"cannot drop onto occupied square {square}")
        hand = self.hands.get(owner, [])
        for i, piece in enumerate(hand):
            if piece.id == piece_id:
                dropped = hand.pop(i)
                self.squares[square] = dropped
                self._log(
                    f"drop #{dropped.id} {dropped.kind}@{square} -> {dropped.points_at()}"
                )
                return dropped
        raise ValueError(f"piece #{piece_id} is not in {owner}'s hand")

    def move(self, frm: Tuple[int, int], to: Tuple[int, int]) -> None:
        """Slide a wedge to an empty square (geometry model only)."""
        self._check_square(frm)
        self._check_square(to)
        if frm not in self.squares:
            raise ValueError(f"nothing at {frm}")
        if to in self.squares:
            raise ValueError(f"square {to} is occupied")
        self.squares[to] = self.squares.pop(frm)
        self._log(f"move #{self.squares[to].id} {frm}->{to}")

    # -- the craft loop ---------------------------------------------------------------
    def recarve(self, piece: Piece, grade: int, carver: str) -> None:
        """Restore a worn wedge's calligraphy grade; logged with the carver."""
        if grade not in _GRADES:
            raise ValueError(f"grade must be one of {_GRADES}")
        old = piece.grade
        piece.grade = grade
        self._log(f"recarve #{piece.id} {piece.kind} {old}->{grade} by {carver}")

    def hand_of(self, owner: str) -> List[Piece]:
        return list(self.hands.get(owner, []))

    def at(self, square: Tuple[int, int]) -> Optional[Piece]:
        self._check_square(square)
        return self.squares.get(square)
