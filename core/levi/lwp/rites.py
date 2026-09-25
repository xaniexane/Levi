"""L.W.P. Rites — the casting of lots: tarot, dice, and the writer's journal.

The Living Bible (``levi.lwp.living_bible``) is the world's memory; rites are
how the writer consults chance before the memory is written. A draw or a roll
is never canon by itself — every casting is recorded as a PROPOSED event and
the writer confirms or rejects it, same ternary law as the bible
(PROPOSED / CONFIRMED / REJECTED). The press proposes; the writer disposes.

Three tools, one loop:

- ``TarotDeck`` — the full 78-card deck (22 major arcana + 56 minor:
  4 suits x 14), drawn DESTRUCTIVELY: no card repeats until the deck is
  reshuffled. Per-draw reversal odds are configurable (default 6%, inside
  the 2-10% band where reversals feel organic).
- ``Dice`` — the classic D&D set (d4, d6, d8, d10, d12, d20, d100).
- ``RitesJournal`` — a Markdown journal. Every entry auto-tags with its
  timestamp plus the last roll and the last draw; ``export()`` writes the
  whole log as a single ``.md`` file.

Original work only: card names are the traditional public-domain
arcana/suit names. Cards carry bare structural data (name, arcana, suit,
number, reversed flag) — no borrowed meanings text, no content dump.

Honest contract
---------------
- Everything is deterministic given a seed: ``random.Random`` with an
  explicit seed, never the global RNG. Deterministic = repeatable.
- stdlib only, no network, no analytics, no accounts.
- Local-first: ``home`` is caller-supplied (the echoverse entry pattern);
  nothing assumes ``~/.levi``. Journal files are written mode 0600.
- Mythos stays poetry: draws suggest; they never declare. No mythic or
  sentience-adjacent claims anywhere in this module.
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.lwp.living_bible import PROPOSED

_RECORD_MODE = 0o600

# ---------------------------------------------------------------------------
# The deck — traditional public-domain names, structural data only.
# ---------------------------------------------------------------------------

MAJOR_ARCANA = (
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun",
    "Judgement", "The World",
)

SUITS = ("Wands", "Cups", "Swords", "Pentacles")
RANKS = (
    "Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
    "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King",
)

DEFAULT_REVERSAL_ODDS = 0.06  # inside the 2-10% band


@dataclass(frozen=True)
class Card:
    name: str
    arcana: str  # "major" | "minor"
    suit: Optional[str] = None
    number: Optional[int] = None  # 0-21 for major, 1-14 for minor
    reversed: bool = False

    def describe(self) -> str:
        rev = " (reversed)" if self.reversed else ""
        return f"{self.name}{rev}"


def _build_deck() -> List[Card]:
    cards: List[Card] = [
        Card(name=name, arcana="major", number=i)
        for i, name in enumerate(MAJOR_ARCANA)
    ]
    for suit in SUITS:
        for i, rank in enumerate(RANKS, start=1):
            cards.append(
                Card(name=f"{rank} of {suit}", arcana="minor",
                     suit=suit, number=i)
            )
    return cards


@dataclass
class Draw:
    card: Card
    event_id: int
    at: str
    status: str = PROPOSED


class TarotDeck:
    """78 cards, drawn destructively. No repeats until reshuffle."""

    def __init__(self, seed: Optional[int] = None,
                 reversal_odds: float = DEFAULT_REVERSAL_ODDS):
        if not 0.0 <= reversal_odds <= 1.0:
            raise ValueError("reversal_odds must be between 0 and 1")
        self._rng = random.Random(seed)
        self._seed = seed
        self.reversal_odds = reversal_odds
        self._stock: List[Card] = []
        self._drawn = 0
        self.reshuffle()

    def reshuffle(self) -> None:
        """Restore the full 78-card stock and shuffle it."""
        self._stock = _build_deck()
        self._rng.shuffle(self._stock)

    def remaining(self) -> int:
        return len(self._stock)

    def draw(self, n: int = 1) -> List[Draw]:
        if n < 1:
            raise ValueError("draw at least one card")
        if n > len(self._stock):
            raise ValueError(
                f"only {len(self._stock)} cards left; reshuffle first")
        out: List[Draw] = []
        for _ in range(n):
            base = self._stock.pop()
            reversed_ = self._rng.random() < self.reversal_odds
            card = Card(name=base.name, arcana=base.arcana, suit=base.suit,
                        number=base.number, reversed=reversed_)
            self._drawn += 1
            out.append(Draw(card=card, event_id=self._drawn,
                            at=_utcnow()))
        return out


# ---------------------------------------------------------------------------
# Dice — the classic set, same seeded determinism.
# ---------------------------------------------------------------------------

DICE = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20,
        "d100": 100}
_DIE_RE = re.compile(r"^d(\d+)$", re.IGNORECASE)


@dataclass
class Roll:
    die: str
    sides: int
    value: int
    event_id: int
    at: str
    status: str = PROPOSED


class Dice:
    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._seed = seed
        self._rolled = 0

    def roll(self, die: str = "d20") -> Roll:
        key = die.lower()
        if key not in DICE:
            raise ValueError(f"unknown die {die!r}; choose from "
                             f"{sorted(DICE)}")
        sides = DICE[key]
        self._rolled += 1
        return Roll(die=key, sides=sides,
                    value=self._rng.randint(1, sides),
                    event_id=self._rolled, at=_utcnow())


# ---------------------------------------------------------------------------
# Journal — every entry tagged with timestamp + last roll + last draw.
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Entry:
    event_id: int
    at: str
    text: str
    last_roll: Optional[str] = None
    last_draw: Optional[str] = None
    status: str = PROPOSED

    def to_markdown(self) -> str:
        lines = [f"## {self.at} — entry {self.event_id}", ""]
        lines.append(self.text)
        lines.append("")
        lines.append(f"- roll: {self.last_roll or '—'}")
        lines.append(f"- draw: {self.last_draw or '—'}")
        lines.append(f"- status: {self.status}")
        lines.append("")
        return "\n".join(lines)


class RitesJournal:
    """Append-only journal under a caller-supplied home directory."""

    def __init__(self, home: Path, name: str = "rites"):
        self._dir = Path(home) / ".levi" / "lwp" / name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._dir / "journal.jsonl"
        self._entries: List[Entry] = []
        self._count = 0

    def note(self, text: str,
             last_roll: Optional[Roll] = None,
             last_draw: Optional[Draw] = None) -> Entry:
        self._count += 1
        entry = Entry(
            event_id=self._count,
            at=_utcnow(),
            text=text,
            last_roll=(f"{last_roll.die} → {last_roll.value}"
                       if last_roll else None),
            last_draw=(last_draw.card.describe() if last_draw else None),
        )
        self._entries.append(entry)
        line = (f"{entry.at}\t{entry.event_id}\t{entry.status}\t"
                f"{entry.last_roll or ''}\t{entry.last_draw or ''}\t"
                f"{entry.text.replace(chr(10), ' ')}")
        with open(self._log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        os.chmod(self._log_path, _RECORD_MODE)
        return entry

    def export(self, path: Optional[Path] = None) -> Path:
        """Write the whole log as a single Markdown file."""
        out = Path(path) if path is not None else self._dir / "journal.md"
        body = ["# Rites journal", "",
                f"Exported {_utcnow()} — {len(self._entries)} entries", ""]
        for entry in self._entries:
            body.append(entry.to_markdown())
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(body))
        os.chmod(out, _RECORD_MODE)
        return out


# ---------------------------------------------------------------------------
# Rites — the loop: one seed, deck + dice + journal together.
# ---------------------------------------------------------------------------

class Rites:
    """One seeded casting session: deck, dice, and journal as a loop."""

    def __init__(self, seed: Optional[int] = None, home: Optional[Path] = None,
                 reversal_odds: float = DEFAULT_REVERSAL_ODDS):
        self.deck = TarotDeck(seed=seed, reversal_odds=reversal_odds)
        # Offset the dice stream so deck and dice don't march in lockstep.
        self.dice = Dice(seed=None if seed is None else seed + 1)
        self._journal: Optional[RitesJournal] = None
        self._home = Path(home) if home is not None else None
        self._last_roll: Optional[Roll] = None
        self._last_draw: Optional[Draw] = None
        self._castings: List[Dict[str, str]] = []

    @property
    def journal(self) -> RitesJournal:
        if self._journal is None:
            if self._home is None:
                raise ValueError("home is required: pass an explicit home "
                                 "directory; nothing assumes ~/.levi")
            self._journal = RitesJournal(self._home)
        return self._journal

    def draw(self, n: int = 1) -> List[Draw]:
        draws = self.deck.draw(n)
        self._last_draw = draws[-1]
        for d in draws:
            self._castings.append({
                "kind": "draw",
                "event_id": str(d.event_id),
                "at": d.at,
                "summary": f"drew {d.card.describe()}",
                "status": PROPOSED,
            })
        return draws

    def roll(self, die: str = "d20") -> Roll:
        self._last_roll = self.dice.roll(die)
        self._castings.append({
            "kind": "roll",
            "event_id": str(self._last_roll.event_id),
            "at": self._last_roll.at,
            "summary": f"rolled {self._last_roll.die} → "
                       f"{self._last_roll.value}",
            "status": PROPOSED,
        })
        return self._last_roll

    def note(self, text: str) -> Entry:
        """Journal one line, auto-tagged with the last roll and last draw."""
        return self.journal.note(text, last_roll=self._last_roll,
                                 last_draw=self._last_draw)

    def export(self, path: Optional[Path] = None) -> Path:
        return self.journal.export(path)

    def propose(self) -> List[Dict[str, str]]:
        """All castings as PROPOSED events for the writer to confirm —
        ready-shaped for the Living Bible's ternary lifecycle, never
        auto-canon."""
        return [dict(c) for c in self._castings]


__all__ = [
    "DEFAULT_REVERSAL_ODDS",
    "DICE",
    "Card",
    "Dice",
    "Draw",
    "Entry",
    "Rites",
    "RitesJournal",
    "Roll",
    "TarotDeck",
]
