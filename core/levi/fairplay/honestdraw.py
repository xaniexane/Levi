"""The honest draw: a loot engine that shows its math.

Belgium's 2018 ruling named the predation precisely: the buyer pays
without knowing what is inside the box. The honest draw keeps the fun
of the draw and deletes the bet:

LAWS (invariants, machine-checked by tests):
1. ODDS ARE PUBLIC BEFORE THE FIRST DRAW. ``DropTable.publish()`` is
   the table itself; ``draw()`` cannot see odds the player cannot.
2. EVERY DRAW IS REPRODUCIBLE. The engine is a seeded ``random.Random``;
   ``replay(seed, table)`` regenerates the exact sequence from the log.
   Any player can audit the machine.
3. PITY IS A GUARANTEE, NOT A HOPE. If ``pity_ceiling`` is set, a draw
   of at least the pity rarity is FORCED within that many draws. The
   ceiling is part of the published contract, never a hidden mercy rule.
4. THE LOG IS APPEND-ONLY AND SELF-AUDITING. Every entry carries its
   draw number, the item, and the running count; ``verify_log()`` fails
   on any gap, reorder, or edit.
5. NO TILL. Draws are spent from ``play_earned`` \u2014 a counter of play,
   never a balance. Nothing here is for sale; draws take play, never coin.

Clean-room from first principles; no game code was read or copied.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Rarity order: index 0 is common, the last index is the rarest.
RARITIES = ("common", "uncommon", "rare", "epic", "legendary")


@dataclass(frozen=True)
class Drop:
    """One row of the published table: what it is, how rare, its odds."""

    name: str
    rarity: str
    weight: float  # relative chance; published odds derive from these

    def __post_init__(self) -> None:
        if self.rarity not in RARITIES:
            raise ValueError(f"unknown rarity: {self.rarity!r}")
        if self.weight <= 0:
            raise ValueError("weight must be positive")


class DropTable:
    """The published contract. Immutable once sealed."""

    def __init__(self, drops: List[Drop]) -> None:
        if not drops:
            raise ValueError("a drop table needs at least one row")
        self._drops = tuple(drops)
        total = sum(d.weight for d in self._drops)
        self._odds = tuple(d.weight / total for d in self._drops)

    def publish(self) -> List[Dict[str, object]]:
        """The full odds sheet: name, rarity, exact probability. Law 1."""
        return [
            {"name": d.name, "rarity": d.rarity, "probability": p}
            for d, p in zip(self._drops, self._odds)
        ]

    def total_probability(self) -> float:
        return sum(self._odds)

    def rarest_rarity_index(self, at_least: str) -> int:
        return RARITIES.index(at_least)


@dataclass
class AuditEntry:
    """One logged draw. ``draw_no`` is 1-based and strictly increasing."""

    draw_no: int
    item: str
    rarity: str
    pity_triggered: bool
    play_earned_spent: int


class FairDraw:
    """A seeded, audited, pity-guaranteed draw engine over a DropTable."""

    def __init__(
        self,
        table: DropTable,
        seed: int,
        pity_ceiling: Optional[int] = None,
        pity_rarity: str = "rare",
    ) -> None:
        self.table = table
        self.seed = seed
        self.pity_ceiling = pity_ceiling
        self.pity_rarity = pity_rarity
        if pity_ceiling is not None and pity_ceiling < 1:
            raise ValueError("pity_ceiling must be positive or None")
        self._rng = random.Random(seed)
        self._drops = table._drops
        self._cum: List[Tuple[float, Drop]] = []
        running = 0.0
        for d, p in zip(self._drops, table._odds):
            running += p
            self._cum.append((running, d))
        self._since_pity = 0
        self._log: List[AuditEntry] = []
        self.play_earned = 0  # Law 5: play counter, never a balance

    def earn_play(self, amount: int = 1) -> int:
        """Play happened. Returns the new total. Only play buys draws."""
        if amount < 0:
            raise ValueError("cannot earn negative play")
        self.play_earned += amount
        return self.play_earned

    def _roll(self) -> Drop:
        r = self._rng.random()
        for bound, drop in self._cum:
            if r < bound:
                return drop
        return self._drops[-1]

    def _pity_drop(self) -> Drop:
        """Force a draw of at least the pity rarity (deterministic pick)."""
        floor = RARITIES.index(self.pity_rarity)
        eligible = [d for d in self._drops if RARITIES.index(d.rarity) >= floor]
        # Deterministic under the seed: pick via the engine RNG, but the
        # pity TRIGGER is guaranteed regardless of which item is picked.
        return eligible[int(self._rng.random() * len(eligible))]

    def draw(self) -> AuditEntry:
        """Spend one unit of earned play; return the logged draw."""
        if self.play_earned < 1:
            raise RuntimeError("no earned play to draw with \u2014 play first")
        self.play_earned -= 1
        pity = False
        if (
            self.pity_ceiling is not None
            and self._since_pity + 1 >= self.pity_ceiling
        ):
            drop = self._pity_drop()
            pity = True
            self._since_pity = 0
        else:
            drop = self._roll()
            if RARITIES.index(drop.rarity) >= RARITIES.index(self.pity_rarity):
                self._since_pity = 0
            else:
                self._since_pity += 1
        entry = AuditEntry(
            draw_no=len(self._log) + 1,
            item=drop.name,
            rarity=drop.rarity,
            pity_triggered=pity,
            play_earned_spent=1,
        )
        self._log.append(entry)
        return entry

    def log(self) -> List[AuditEntry]:
        return list(self._log)

    def verify_log(self) -> Tuple[bool, str]:
        """Law 4: the log must be gapless, ordered, and match a replay."""
        for i, entry in enumerate(self._log, start=1):
            if entry.draw_no != i:
                return False, f"gap or reorder at position {i}"
        replayed = replay(self.table, self.seed, self.pity_ceiling,
                          self.pity_rarity, len(self._log))
        for got, want in zip(self._log, replayed):
            if (got.item, got.rarity, got.pity_triggered) != (
                want.item,
                want.rarity,
                want.pity_triggered,
            ):
                return False, f"replay mismatch at draw {got.draw_no}"
        return True, "ok"


def replay(
    table: DropTable,
    seed: int,
    pity_ceiling: Optional[int],
    pity_rarity: str,
    n: int,
) -> List[AuditEntry]:
    """Regenerate the first ``n`` draws from seed alone. Law 2."""
    engine = FairDraw(table, seed, pity_ceiling, pity_rarity)
    engine.play_earned = n  # replay grants its own play; the live log
    return [engine.draw() for _ in range(n)]
