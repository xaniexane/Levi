"""Peer-judged masterpiece as credential; the guild retains the piece as corpus.

Studied from: lost-crafts-20260916/report.md [Batch 1] (the chef-d'œuvre: a
masterpiece judged by peers as the credential for master rank, with the guild
keeping the piece as a reference corpus for future learners).

This is an original, from-scratch implementation for LEVI. A maker submits a
``Piece`` describing their artifact. Registered ``Peer`` judges score it
against a fixed rubric (rubric dimensions are configurable weights). When
enough distinct peers have scored, the piece is ``judged``: if its weighted
mean meets the pass threshold and no dimension falls below a veto floor, the
maker earns the master credential and the piece enters the ``ReferenceCorpus``
— an indexed, searchable archive of retained masterworks future learners can
study. Peer scoring is blind to other peers' scores until judging closes, and
every score is recorded on the piece so judging is accountable.

The "guild retains the piece" rule is honored honestly: retention is an
explicit, inspectable archive with provenance (maker, judges, rubric, scores),
not a hidden vault.

Public surface:
- ``Guild``: ``register_peer(name)``, ``submit_piece(...)``, ``score(...)``,
  ``judge(piece_id)`` -> ``Verdict``, ``corpus`` (``ReferenceCorpus``),
  ``credentialed`` (maker -> rank).
- ``Verdict`` carries the mean score, per-dimension means, and pass/fail.

stdlib-only. No network. Deterministic (rubric-weighted means, no randomness).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

ORIGIN = "levi-revival/chef-d-uvre"

DEFAULT_RUBRIC: Dict[str, float] = {
    "craft": 0.40,
    "design": 0.30,
    "material": 0.20,
    "finish": 0.10,
}
PASS_THRESHOLD = 0.70
VETO_FLOOR = 0.40
MIN_PEERS = 3


class ReviewError(ValueError):
    """Raised when a review step cannot be honored."""


@dataclass
class Peer:
    name: str
    rank: str = "master"


@dataclass
class ScoreCard:
    peer: str
    marks: Dict[str, float]  # rubric dimension -> 0.0..1.0


@dataclass
class Piece:
    piece_id: int
    maker: str
    title: str
    description: str
    scores: List[ScoreCard] = field(default_factory=list)
    judged: bool = False


@dataclass
class Verdict:
    piece_id: int
    maker: str
    mean: float
    dimension_means: Dict[str, float]
    passed: bool
    reason: str


class ReferenceCorpus:
    """The guild's retained masterworks: provenance + scores, searchable."""

    def __init__(self) -> None:
        self._pieces: List[Piece] = []

    def retain(self, piece: Piece) -> None:
        self._pieces.append(piece)

    def __len__(self) -> int:
        return len(self._pieces)

    def by_maker(self, maker: str) -> List[Piece]:
        return [p for p in self._pieces if p.maker == maker]

    def search(self, term: str) -> List[Piece]:
        term = term.lower()
        return [
            p
            for p in self._pieces
            if term in p.title.lower() or term in p.description.lower()
        ]

    def study(self, piece_id: int) -> Piece:
        for p in self._pieces:
            if p.piece_id == piece_id:
                return p
        raise ReviewError(f"no retained piece {piece_id}")


class Guild:
    """Runs peer-judged masterpieces and keeps the reference corpus."""

    def __init__(
        self,
        name: str,
        rubric: Optional[Mapping[str, float]] = None,
        pass_threshold: float = PASS_THRESHOLD,
        veto_floor: float = VETO_FLOOR,
        min_peers: int = MIN_PEERS,
    ) -> None:
        if not name:
            raise ReviewError("guild name must be non-empty")
        self.name = name
        self.rubric = dict(rubric) if rubric else dict(DEFAULT_RUBRIC)
        if abs(sum(self.rubric.values()) - 1.0) > 1e-9:
            raise ReviewError("rubric weights must sum to 1.0")
        self.pass_threshold = pass_threshold
        self.veto_floor = veto_floor
        self.min_peers = min_peers
        self._peers: Dict[str, Peer] = {}
        self._pieces: Dict[int, Piece] = {}
        self._next_id = 1
        self._credentialed: Dict[str, str] = {}
        self.corpus = ReferenceCorpus()

    # -- peers & submissions ---------------------------------------------
    def register_peer(self, name: str, rank: str = "master") -> Peer:
        if name in self._peers:
            raise ReviewError(f"peer {name!r} already registered")
        peer = Peer(name=name, rank=rank)
        self._peers[name] = peer
        return peer

    def submit_piece(self, maker: str, title: str, description: str) -> Piece:
        if maker in self._peers:
            raise ReviewError(
                "a registered peer cannot judge their own work; submit as non-peer"
            )
        piece = Piece(
            piece_id=self._next_id, maker=maker, title=title, description=description
        )
        self._next_id += 1
        self._pieces[piece.piece_id] = piece
        return piece

    # -- scoring -----------------------------------------------------------
    def score(self, piece_id: int, peer: str, marks: Mapping[str, float]) -> ScoreCard:
        piece = self._pieces.get(piece_id)
        if piece is None:
            raise ReviewError(f"no piece {piece_id}")
        if piece.judged:
            raise ReviewError(f"piece {piece_id} already judged")
        if peer not in self._peers:
            raise ReviewError(f"{peer!r} is not a registered peer")
        if peer == piece.maker:
            raise ReviewError("maker cannot score their own piece")
        if any(s.peer == peer for s in piece.scores):
            raise ReviewError(f"{peer!r} already scored piece {piece_id}")
        marks = dict(marks)
        missing = set(self.rubric) - set(marks)
        if missing:
            raise ReviewError(f"marks missing rubric dimensions: {sorted(missing)}")
        for dim, value in marks.items():
            if dim not in self.rubric:
                raise ReviewError(f"unknown rubric dimension {dim!r}")
            if not 0.0 <= value <= 1.0:
                raise ReviewError(f"mark for {dim!r} out of range: {value}")
        card = ScoreCard(peer=peer, marks=marks)
        piece.scores.append(card)
        return card

    def ready(self, piece_id: int) -> bool:
        piece = self._pieces.get(piece_id)
        if piece is None:
            raise ReviewError(f"no piece {piece_id}")
        return len(piece.scores) >= self.min_peers

    # -- judging -----------------------------------------------------------
    def judge(self, piece_id: int) -> Verdict:
        piece = self._pieces.get(piece_id)
        if piece is None:
            raise ReviewError(f"no piece {piece_id}")
        if piece.judged:
            raise ReviewError(f"piece {piece_id} already judged")
        if not self.ready(piece_id):
            raise ReviewError(
                f"piece {piece_id} needs {self.min_peers} peer scores, has {len(piece.scores)}"
            )
        dim_means = {
            dim: sum(card.marks[dim] for card in piece.scores) / len(piece.scores)
            for dim in self.rubric
        }
        mean = sum(self.rubric[dim] * dim_means[dim] for dim in self.rubric)
        vetoed = [d for d, m in dim_means.items() if m < self.veto_floor]
        passed = mean >= self.pass_threshold and not vetoed
        if passed:
            reason = f"mean {mean:.3f} >= {self.pass_threshold} and no dimension below veto floor"
            self.corpus.retain(piece)
            self._credentialed[piece.maker] = "master"
        elif vetoed:
            reason = f"vetoed: dimensions below floor {self.veto_floor}: {vetoed}"
        else:
            reason = f"mean {mean:.3f} below threshold {self.pass_threshold}"
        piece.judged = True
        return Verdict(
            piece_id=piece_id,
            maker=piece.maker,
            mean=mean,
            dimension_means=dim_means,
            passed=passed,
            reason=reason,
        )

    def rank_of(self, maker: str) -> Optional[str]:
        return self._credentialed.get(maker)

    def credentials(self) -> Dict[str, str]:
        return dict(self._credentialed)
