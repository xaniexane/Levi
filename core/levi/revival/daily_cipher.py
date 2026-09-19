"""Deterministic daily cipher: a puzzle game that never punishes missed days.

Studied from: games-hunt-20260916-0022/report.md [Find 3 — levi_application]
(Deterministic daily cipher: a daily puzzle game that never punishes missed
days; any date catch-up-playable).

This is an original, from-scratch implementation for LEVI. Each calendar day
gets one cipher puzzle, generated *deterministically* from the date itself —
no server, no stored puzzle bank, no network. The day's seed is
``sha256("levi-daily-cipher:" + YYYYMMDD)``; the seed drives a monoalphabetic
substitution cipher over a daily word drawn from a built-in wordlist, plus a
fixed hint budget. Because the puzzle is a pure function of the date, any
day — past or present — is catch-up playable: ``puzzle_for(date)`` reproduces
exactly the puzzle that day always had.

The anti-punishment design is explicit: there is no streak, no decay, no
"missed day" penalty anywhere in the state. ``DailyCipherLog`` records plays
per date but treats every date as independent; a missed day is simply an
unplayed day, indistinguishable from a future one.

Guessing is letter-mapping work: the player proposes plain→cipher or
cipher→plain letter guesses; ``check_guess`` tells them which letters of the
current mapping are right. Solving requires the full correct mapping.

Public surface:
- ``puzzle_for(date)`` -> ``DailyPuzzle`` (``date``, ``cipher_text``,
  ``hint_letter``, ``word_length``); ``puzzle_for("2026-09-16")`` or a
  ``datetime.date``.
- ``DailyPuzzle.solve(guesses)`` and ``check_guess(mapping)``.
- ``DailyCipherLog``: ``record(date, solved)``, ``played(date)``,
  ``summary()`` — per-date records, no streaks, no penalties.

Honest limits: the cipher is a simple substitution over a small wordlist —
it's a toy puzzle, not cryptography. The daily word is chosen by hashing the
date into the wordlist; wordlist quality bounds puzzle quality.

stdlib-only. No network. Fully deterministic.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple, Union


ORIGIN = "levi-revival/daily_cipher"

# Small built-in wordlist; the daily word is picked by hashing the date.
# Kept modest on purpose: the puzzle's fun comes from the mapping work,
# not vocabulary breadth.
_WORDLIST = (
    "cipher",
    "lantern",
    "harbor",
    "meadow",
    "quartz",
    "thunder",
    "garden",
    "voyage",
    "ember",
    "forest",
    "silver",
    "comet",
    "tide",
    "willow",
    "falcon",
    "breeze",
    "stone",
    "river",
    "oak",
    "maple",
    "cedar",
    "birch",
    "elm",
    "pine",
    "north",
    "south",
    "east",
    "west",
    "dawn",
    "dusk",
    "planet",
    "orbit",
    "lunar",
    "solar",
    "nova",
    "cosmos",
)

DateLike = Union[str, date]


def _normalize_date(d: DateLike) -> date:
    if isinstance(d, date):
        return d
    try:
        year, month, day = (int(part) for part in d.split("-"))
        return date(year, month, day)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"date must be YYYY-MM-DD or a date, got {d!r}") from exc


def _seed_for(d: date) -> int:
    digest = hashlib.sha256(f"levi-daily-cipher:{d.isoformat()}".encode()).hexdigest()
    return int(digest, 16)


def _substitution(rng: random.Random) -> Dict[str, str]:
    """A random monoalphabetic substitution: plain letter -> cipher letter."""
    letters = [chr(c) for c in range(ord("a"), ord("z") + 1)]
    shuffled = letters[:]
    rng.shuffle(shuffled)
    return dict(zip(letters, shuffled, strict=True))


@dataclass(frozen=True)
class DailyPuzzle:
    """One day's cipher puzzle."""

    puzzle_date: date
    cipher_text: str
    hint: Tuple[str, str]  # (plain_letter, cipher_letter) revealed up front
    word_length: int
    _plain_word: str = field(repr=False)
    _mapping: Dict[str, str] = field(repr=False)  # plain -> cipher

    def check_guess(self, cipher_to_plain: Dict[str, str]) -> Dict[str, bool]:
        """Score a guessed mapping: cipher letter -> is that plain letter right?"""
        result: Dict[str, bool] = {}
        for cipher_letter, guess in cipher_to_plain.items():
            guess = guess.lower()
            plain = next(
                (p for p, c in self._mapping.items() if c == cipher_letter), None
            )
            result[cipher_letter] = plain is not None and guess == plain
        return result

    def solve(self, guessed_word: str) -> bool:
        """True when the guessed word is the day's word."""
        return guessed_word.strip().lower() == self._plain_word

    def reveal(self) -> str:
        """The day's answer (for after play, or for honest testing)."""
        return self._plain_word


def puzzle_for(d: DateLike) -> DailyPuzzle:
    """Generate the puzzle for any date — pure function of the date."""
    day = _normalize_date(d)
    rng = random.Random(_seed_for(day))
    word = _WORDLIST[rng.randrange(len(_WORDLIST))]
    mapping = _substitution(rng)
    cipher_text = "".join(mapping[ch] for ch in word)
    # Hint: reveal one true plain->cipher pair from the middle of the word.
    hint_pos = len(word) // 2
    hint = (word[hint_pos], mapping[word[hint_pos]])
    return DailyPuzzle(
        puzzle_date=day,
        cipher_text=cipher_text,
        hint=hint,
        word_length=len(word),
        _plain_word=word,
        _mapping=mapping,
    )


@dataclass
class DailyCipherLog:
    """Per-date play records. No streaks, no decay, no missed-day penalties."""

    _plays: Dict[date, bool] = field(default_factory=dict)

    def record(self, d: DateLike, solved: bool) -> None:
        self._plays[_normalize_date(d)] = bool(solved)

    def played(self, d: DateLike) -> Optional[bool]:
        """None if the date was never played — a missed day is just unplayed."""
        return self._plays.get(_normalize_date(d))

    def summary(self) -> Dict[str, int]:
        solved = sum(1 for v in self._plays.values() if v)
        return {
            "days_played": len(self._plays),
            "days_solved": solved,
            "days_missed_penalty": 0,  # there is no penalty, ever
        }

    def unplayed_dates(self, dates: Iterable[DateLike]) -> List[date]:
        """Which of these dates are still catch-up playable (never played)."""
        return [d for d in (_normalize_date(x) for x in dates) if d not in self._plays]
