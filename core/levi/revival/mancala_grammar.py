"""LEVI's mancala grammar: one sowing mechanic, thousands of games.

Studied from: pre-digital-computation-20260916/report.md [Beat C #14, LOAD-BEARING].

The shape being studied: mancala is not a game but a *game grammar*.
Three independent choices compose the whole family:

- *topology*: how many pits per side, how they connect;
- *sowing*: which direction seeds travel, where they may land;
- *capture*: what a well-placed last seed takes, and when turns repeat.

Change one dial and you have a different playable game from the same
mechanic. ``mancala_grammar`` rebuilds that shape from scratch,
LEVI-native: a generic ``MancalaGame`` driven by a ``Rules`` record, plus
named presets (kalah-style, oware-style) showing the grammar at work.

Honest limits: the engine is the rules kernel — legal moves, sowing,
capture, extra turns, end-of-game. It ships no AI opponent; ``suggest``
offers a shallow heuristic (greedy capture count) and says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


ORIGIN = "levi-revival/mancala-grammar"


class MancalaError(Exception):
    """Base class for mancala failures."""


@dataclass(frozen=True)
class Rules:
    """The three grammar dials, plus endgame handling.

    capture: "none" | "empty" (kalah-style: last seed in an empty own pit
             captures it plus the opposite pit) | "owari" (oware-style:
             last seed making an opponent pit hold 2 or 3 captures it,
             chaining backwards).
    extra_turn: last seed in your own store grants another turn.
    end: "capture" (when one side empties, each side's leftovers go to its
         owner's store) | "stop" (leftover seeds stay where they lie and
         only stores count — the oware way).
    """

    pits: int = 6
    seeds: int = 4
    direction: int = 1  # +1 counterclockwise, -1 clockwise
    capture: str = "empty"
    extra_turn: bool = True
    end: str = "capture"

    def __post_init__(self):
        if self.pits < 1:
            raise MancalaError("pits must be >= 1")
        if self.seeds < 1:
            raise MancalaError("seeds must be >= 1")
        if self.direction not in (1, -1):
            raise MancalaError("direction must be +1 or -1")
        if self.capture not in ("none", "empty", "owari"):
            raise MancalaError(f"unknown capture rule {self.capture!r}")
        if self.end not in ("capture", "stop"):
            raise MancalaError(f"unknown end rule {self.end!r}")


def kalah_rules(pits: int = 6, seeds: int = 4) -> Rules:
    """The familiar Western schoolyard game, as one grammar setting."""
    return Rules(
        pits=pits, seeds=seeds, capture="empty", extra_turn=True, end="capture"
    )


def oware_rules() -> Rules:
    """West-African oware, as one grammar setting (store = capture pile)."""
    return Rules(pits=6, seeds=4, capture="owari", extra_turn=False, end="stop")


@dataclass
class SowOutcome:
    player: int
    pit: int
    last_index: int
    captured: int
    extra_turn: bool
    game_over: bool


class MancalaGame:
    """A game played on ``Rules``. Board layout:

    pits[0:pits]            — player 0's side
    pits[pits:2*pits]       — player 1's side
    stores[0], stores[1]    — the two stores (player 1's store is skipped
                              while player 0 sows, and vice versa)
    """

    def __init__(self, rules: Optional[Rules] = None):
        self.rules = rules or kalah_rules()
        n = self.rules.pits
        self.pits: List[int] = [self.rules.seeds] * (2 * n)
        self.stores: List[int] = [0, 0]
        self.turn: int = 0
        self.over: bool = False

    # -- queries ---------------------------------------------------------

    def side(self, player: int) -> range:
        n = self.rules.pits
        return range(0, n) if player == 0 else range(n, 2 * n)

    def owns(self, player: int, index: int) -> bool:
        return index in self.side(player)

    def opposite(self, index: int) -> int:
        return 2 * self.rules.pits - 1 - index

    def legal_moves(self, player: int) -> List[int]:
        if self.over or player != self.turn:
            return []
        return [i for i in self.side(player) if self.pits[i] > 0]

    def is_over(self) -> bool:
        n = self.rules.pits
        return self.over or not any(self.pits[0:n]) or not any(self.pits[n:])

    # -- play ------------------------------------------------------------

    def _cycle(self, player: int) -> List[int]:
        """Sow-order cycle for ``player``: own pits, own store, enemy pits.

        The own store is encoded as ``2 * pits``; the opponent's store is
        skipped entirely. ``direction == -1`` reverses each side.
        """
        n = self.rules.pits
        store = 2 * n
        if player == 0:
            own = list(range(n))
            opp = list(range(n, 2 * n))
        else:
            own = list(range(n, 2 * n))
            opp = list(range(n))
        if self.rules.direction == -1:
            own = own[::-1]
            opp = opp[::-1]
        return own + [store] + opp

    def sow(self, player: int, pit: int) -> SowOutcome:
        if self.over:
            raise MancalaError("game is over")
        if player != self.turn:
            raise MancalaError(f"it is player {self.turn}'s turn")
        if not self.owns(player, pit):
            raise MancalaError(f"pit {pit} is not player {player}'s")
        if self.pits[pit] == 0:
            raise MancalaError(f"pit {pit} is empty")

        n = self.rules.pits
        store = 2 * n
        seeds = self.pits[pit]
        self.pits[pit] = 0

        cycle = self._cycle(player)
        start = cycle.index(pit)
        last = -1
        captured = 0
        for k in range(seeds):
            pos = cycle[(start + 1 + k) % len(cycle)]
            if pos == store:
                self.stores[player] += 1
            else:
                self.pits[pos] += 1
            last = pos

        extra = False
        if last == store:
            if self.rules.extra_turn:
                extra = True
        else:
            # _capture applies the grammar's capture dial: "empty" fires
            # only on your own pits, "owari" only on the opponent's.
            captured = self._capture(player, last)

        game_over = self.is_over()
        if game_over:
            self._finish()
        elif not extra:
            self.turn = 1 - player

        return SowOutcome(
            player=player,
            pit=pit,
            last_index=last,
            captured=captured,
            extra_turn=extra and not game_over,
            game_over=game_over,
        )

    def _capture(self, player: int, last: int) -> int:
        rule = self.rules.capture
        if rule == "empty":
            # Kalah-style: last seed landed in an empty own pit (it now
            # holds exactly 1) — take it plus the opposite pit.
            if self.owns(player, last) and self.pits[last] == 1:
                opp = self.opposite(last)
                taken = self.pits[last] + self.pits[opp]
                self.pits[last] = 0
                self.pits[opp] = 0
                self.stores[player] += taken
                return taken
        elif rule == "owari":
            # Oware-style: only opponent pits, chaining backwards along
            # the sow order while the pit holds 2 or 3 after the sow.
            # (Grand-slam handling omitted — documented limit.)
            cycle = self._cycle(player)
            store = 2 * self.rules.pits
            taken = 0
            ci = cycle.index(last)
            for _ in range(len(cycle)):
                pos = cycle[ci % len(cycle)]
                if pos == store or self.owns(player, pos):
                    break
                if self.pits[pos] not in (2, 3):
                    break
                taken += self.pits[pos]
                self.pits[pos] = 0
                ci -= 1
            self.stores[player] += taken
            return taken
        return 0

    def _finish(self) -> None:
        self.over = True
        if self.rules.end == "capture":
            n = self.rules.pits
            for i in range(n):
                self.stores[0] += self.pits[i]
                self.pits[i] = 0
            for i in range(n, 2 * n):
                self.stores[1] += self.pits[i]
                self.pits[i] = 0

    def winner(self) -> Optional[int]:
        """0/1 for the winner, None for a draw or an unfinished game."""
        if not self.over:
            return None
        if self.stores[0] > self.stores[1]:
            return 0
        if self.stores[1] > self.stores[0]:
            return 1
        return None

    def score(self) -> Tuple[int, int]:
        return (self.stores[0], self.stores[1])

    def suggest(self, player: int) -> Optional[int]:
        """Greedy heuristic: the legal move capturing the most seeds now.

        This is a one-ply heuristic, not an AI — it sees no replies.
        """
        best: Optional[int] = None
        best_gain = -1
        for pit in self.legal_moves(player):
            clone = self.clone()
            out = clone.sow(player, pit)
            gain = out.captured + (1 if out.extra_turn else 0)
            if gain > best_gain:
                best_gain = gain
                best = pit
        return best

    def clone(self) -> "MancalaGame":
        g = MancalaGame(self.rules)
        g.pits = list(self.pits)
        g.stores = list(self.stores)
        g.turn = self.turn
        g.over = self.over
        return g
