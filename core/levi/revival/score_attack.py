"""Arcade score attack + initials leaderboard: the persistent local top-10.

Studied from: games-deadmechanics-20260916/findings.jsonl
[arch-games-score-attack] (Arcade score attack + initials leaderboard:
persistent local top-10 table on the cabinet; 3-initial entries as
identity-without-identity-theft; seeded-replay verification for claimed
scores).

This is an original, from-scratch implementation for LEVI. ``Leaderboard``
is a persistent local top-10 table: entries are (score, initials, date) and
only the top 10 survive — rank 11 falls off the cabinet. Initials are
exactly 3 uppercase characters ("identity without identity theft"): no
names, no accounts, nothing linkable. The table serializes to plain JSON for
local persistence (``save``/``load``); there is no network and no cloud.

Claimed scores carry *seeded-replay verification*: a ``ScoreClaim`` bundles
the score with the run's seed and the input log. ``verify_claim`` replays
the inputs through a deterministic scoring function registered by the game
and accepts the claim only if the replay reproduces the claimed score. The
default registered scorer is a documented toy (sum of input values times a
seed-derived multiplier) — games register their own real scorer via
``register_scorer``. Verification is honest about its limit: it proves the
score follows from the seed + inputs under the registered rules; it cannot
prove a human (rather than a script) produced the inputs.

Public surface:
- ``Leaderboard``: ``submit(score, initials)``, ``top(n=10)``,
  ``rank_of(score)``, ``save(path)``, ``Leaderboard.load(path)``.
- ``ScoreClaim``: ``(score, initials, seed, inputs)``;
  ``verify_claim(claim, scorer_name="default")``.
- ``register_scorer(name, fn)`` — a scorer is ``fn(seed, inputs) -> int``
  and must be deterministic.

Honest limits: initials are cosmetic identity; seeded replay verifies
score-from-inputs, not who played. Local persistence only.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple


ORIGIN = "levi-revival/score_attack"

MAX_ENTRIES = 10
INITIALS_LENGTH = 3


class ScoreError(ValueError):
    """Raised for invalid scores, initials, or claims."""


def normalize_initials(initials: str) -> str:
    """Exactly 3 uppercase characters; anything else is rejected."""
    cleaned = "".join(ch for ch in initials.upper() if ch.isalnum())
    if len(cleaned) != INITIALS_LENGTH:
        raise ScoreError(
            f"initials must be exactly {INITIALS_LENGTH} alphanumeric "
            f"characters, got {initials!r}"
        )
    return cleaned


@dataclass(frozen=True)
class ScoreEntry:
    score: int
    initials: str
    recorded_at: str


@dataclass(frozen=True)
class ScoreClaim:
    """A claimed score plus the evidence to replay it: seed + input log."""

    score: int
    initials: str
    seed: int
    inputs: Tuple[int, ...]


# -- deterministic scorers ----------------------------------------------
Scorer = Callable[[int, Sequence[int]], int]


def _default_scorer(seed: int, inputs: Sequence[int]) -> int:
    """Documented toy scorer: seed-derived multiplier over the input sum.

    Real games should register their own rules via ``register_scorer``;
    this exists so the verification *mechanism* is testable without one.
    """
    rng = random.Random(seed)
    multiplier = rng.randint(1, 5)
    base = sum(max(0, int(v)) for v in inputs)
    return base * multiplier


_scorers: Dict[str, Scorer] = {"default": _default_scorer}


def register_scorer(name: str, fn: Scorer) -> None:
    """Register a game's deterministic scoring function for replay checks."""
    if not name:
        raise ScoreError("scorer name must be non-empty")
    _scorers[name] = fn


def verify_claim(claim: ScoreClaim, scorer_name: str = "default") -> bool:
    """Replay the claim's inputs under the named scorer; accept on exact match."""
    try:
        scorer = _scorers[scorer_name]
    except KeyError:
        raise ScoreError(f"unknown scorer {scorer_name!r}") from None
    replayed = scorer(claim.seed, claim.inputs)
    return replayed == claim.score


@dataclass
class Leaderboard:
    """The persistent local top-10 table on the cabinet."""

    _entries: List[ScoreEntry] = field(default_factory=list)

    # -- submission ----------------------------------------------------
    def submit(self, score: int, initials: str) -> Optional[int]:
        """Record a score; returns its 1-based rank, or None if it missed the cut.

        Ties are ordered by submission time (earlier entry keeps the rank).
        """
        if score < 0:
            raise ScoreError("score cannot be negative")
        tag = normalize_initials(initials)
        entry = ScoreEntry(
            score=score,
            initials=tag,
            recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._entries.append(entry)
        self._entries.sort(key=lambda e: (-e.score, e.recorded_at))
        self._entries = self._entries[:MAX_ENTRIES]
        try:
            return self._entries.index(entry) + 1
        except ValueError:
            return None  # fell off the cabinet

    def submit_verified(
        self, claim: ScoreClaim, scorer_name: str = "default"
    ) -> Optional[int]:
        """Submit only if the seeded replay reproduces the claimed score."""
        if not verify_claim(claim, scorer_name):
            raise ScoreError(
                f"claim by {claim.initials!r} failed replay verification: "
                f"claimed {claim.score}"
            )
        return self.submit(claim.score, claim.initials)

    # -- queries -------------------------------------------------------
    def top(self, n: int = MAX_ENTRIES) -> List[ScoreEntry]:
        return list(self._entries[: max(0, n)])

    def rank_of(self, score: int) -> Optional[int]:
        """Where would this score land? None if it misses the top-10 cut."""
        if score < 0:
            raise ScoreError("score cannot be negative")
        rank = 1
        for entry in self._entries:
            if score > entry.score:
                return rank
            rank += 1
        return rank if len(self._entries) < MAX_ENTRIES else None

    def fingerprint(self) -> str:
        """Tamper-evident digest of the current table."""
        payload = json.dumps(
            [(e.score, e.initials, e.recorded_at) for e in self._entries],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # -- persistence ---------------------------------------------------
    def save(self, path: Path) -> Path:
        path = Path(path)
        data = [
            {"score": e.score, "initials": e.initials, "recorded_at": e.recorded_at}
            for e in self._entries
        ]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "Leaderboard":
        board = cls()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in raw:
            board._entries.append(
                ScoreEntry(
                    score=int(item["score"]),
                    initials=normalize_initials(item["initials"]),
                    recorded_at=str(item["recorded_at"]),
                )
            )
        board._entries.sort(key=lambda e: (-e.score, e.recorded_at))
        board._entries = board._entries[:MAX_ENTRIES]
        return board
