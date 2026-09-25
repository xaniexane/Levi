"""Codebreak — a Mastermind-style deduction game.

The dead-genre-adjacent revival: pure logic, no luck, no purchases, no
timers. Guess the 4-peg code (colors A-F); each guess returns black pegs
(right color, right place) and white pegs (right color, wrong place).
Odds are honest: 6^4 = 1296 possibilities, stated up front.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="codebreak",
    progress_portable=True,
    odds_declared=True,
)

COLORS = ("A", "B", "C", "D", "E", "F")
PEGS = 4
MAX_ATTEMPTS = 10
POSSIBILITIES = len(COLORS) ** PEGS  # 1296 — the honest odds


class CodebreakError(Exception):
    """Bad guesses."""


def feedback(secret: Tuple[str, ...], guess: Tuple[str, ...]) -> Tuple[int, int]:
    """(black, white) feedback for a guess against the secret."""
    black = sum(1 for s, g in zip(secret, guess, strict=True) if s == g)
    # white: color matches excluding black positions
    s_rem = [s for s, g in zip(secret, guess, strict=True) if s != g]
    g_rem = [g for s, g in zip(secret, guess, strict=True) if s != g]
    white = 0
    for g in g_rem:
        if g in s_rem:
            white += 1
            s_rem.remove(g)
    return black, white


def parse_guess(text: str) -> Tuple[str, ...]:
    guess = tuple(c.upper() for c in text.strip() if c.isalpha())
    if len(guess) != PEGS or any(c not in COLORS for c in guess):
        raise CodebreakError(
            "guess must be %d letters from %s (e.g. ABDF)" % (PEGS, "".join(COLORS))
        )
    return guess


@dataclass
class CodebreakGame:
    secret: Tuple[str, ...]
    attempts: int = 0
    history: List[Tuple[str, int, int]] = field(default_factory=list)
    solved: bool = False

    def guess(self, text: str) -> Tuple[int, int]:
        """Make a guess; returns (black, white)."""
        if self.solved:
            raise CodebreakError("already solved — start a new game")
        if self.attempts >= MAX_ATTEMPTS:
            raise CodebreakError(
                "out of attempts — the code was %s" % "".join(self.secret)
            )
        pegs = parse_guess(text)
        black, white = feedback(self.secret, pegs)
        self.attempts += 1
        self.history.append(("".join(pegs), black, white))
        if black == PEGS:
            self.solved = True
        return black, white

    @property
    def remaining(self) -> int:
        return MAX_ATTEMPTS - self.attempts

    def to_dict(self) -> Dict:
        return {
            "secret": list(self.secret),
            "attempts": self.attempts,
            "history": [list(h) for h in self.history],
            "solved": self.solved,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CodebreakGame":
        game = cls(secret=tuple(data["secret"]))
        game.attempts = int(data.get("attempts", 0))
        game.history = [(h[0], int(h[1]), int(h[2])) for h in data.get("history", [])]
        game.solved = bool(data.get("solved", False))
        return game


def new_game(seed: "int | None" = None) -> CodebreakGame:
    rng = random.Random(seed)
    secret = tuple(rng.choice(COLORS) for _ in range(PEGS))
    return CodebreakGame(secret=secret)


# ---------------------------------------------------------------------------
# Interactive play
# ---------------------------------------------------------------------------


def play(store=None, slot: str = "codebreak", seed: "int | None" = None) -> None:
    """Terminal play loop. Save/resume via the portable save store."""
    from levi.games.saves import SaveStore

    store = store or SaveStore()
    print(
        "CODEBREAK — guess the %d-peg code. Colors: %s. %d attempts."
        % (PEGS, " ".join(COLORS), MAX_ATTEMPTS)
    )
    print("Honest odds: 1 in %d. Type 'save', 'quit', or your guess." % POSSIBILITIES)
    existing = store.list_slots("codebreak")
    if existing and slot in existing:
        ans = input("Resume saved game in slot %r? [y/N] " % slot).strip().lower()
        if ans == "y":
            game = CodebreakGame.from_dict(store.load("codebreak", slot))
        else:
            game = new_game(seed)
    else:
        game = new_game(seed)

    while True:
        print("\nAttempt %d/%d" % (game.attempts + 1, MAX_ATTEMPTS))
        for guess, black, white in game.history:
            print("  %s  black=%d white=%d" % (guess, black, white))
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if text.lower() in ("quit", "q", "exit"):
            print("The code was %s." % "".join(game.secret))
            return
        if text.lower() == "save":
            store.save("codebreak", slot, game.to_dict())
            print(
                "Saved to slot %r. Export it any time: "
                "python -m levi.games saves export codebreak %s <file>" % (slot, slot)
            )
            continue
        try:
            black, white = game.guess(text)
        except CodebreakError as exc:
            print(exc)
            continue
        if game.solved:
            print(
                "Solved in %d attempts! The code was %s."
                % (game.attempts, "".join(game.secret))
            )
            store.delete("codebreak", slot)
            return
        if game.attempts >= MAX_ATTEMPTS:
            print("Out of attempts. The code was %s." % "".join(game.secret))
            store.delete("codebreak", slot)
            return
        print(
            "black=%d (right color, right place)  white=%d (right color, wrong place)"
            % (black, white)
        )
