"""Hotseat — the forgotten local-multiplayer mechanic, revived.

Pass-and-play: two players, one keyboard, no accounts, no servers, no
matchmaking queue, no ranked ladder to monetize. TicTacToe and Nim ship
as the first two tables; the engine is generic — new games implement the
small HotseatGame surface and plug in.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="hotseat",
    progress_portable=True,
    odds_declared=True,
)


class GameError(Exception):
    """Illegal moves."""


# ---------------------------------------------------------------------------
# Engine surface
# ---------------------------------------------------------------------------


class HotseatGame:
    """Minimal surface a pass-and-play game implements."""

    game_id: str = "hotseat"

    def current_player(self) -> int:
        raise NotImplementedError

    def legal_moves(self) -> List[str]:
        raise NotImplementedError

    def apply_move(self, move: str) -> None:
        raise NotImplementedError

    def winner(self) -> Optional[int]:
        """None = ongoing; 0/1 = player index; -1 = draw."""
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError

    def move_help(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> Dict:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Dict) -> "HotseatGame":
        raise NotImplementedError


# ---------------------------------------------------------------------------
# TicTacToe
# ---------------------------------------------------------------------------


class TicTacToe(HotseatGame):
    game_id = "hotseat-tictactoe"
    MARKS = ("X", "O")

    def __init__(self):
        self.board: List[str] = [" "] * 9
        self.turn = 0

    def current_player(self) -> int:
        return self.turn % 2

    def legal_moves(self) -> List[str]:
        return [str(i) for i, cell in enumerate(self.board) if cell == " "]

    def move_help(self) -> str:
        return "play a cell 0-8 (row-major: 0|1|2 / 3|4|5 / 6|7|8)"

    def apply_move(self, move: str) -> None:
        move = move.strip()
        if move not in self.legal_moves():
            raise GameError(
                "cell %r is not free (free: %s)" % (move, ", ".join(self.legal_moves()))
            )
        self.board[int(move)] = self.MARKS[self.current_player()]
        self.turn += 1

    def winner(self) -> Optional[int]:
        lines = [
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        ]
        for a, b, c in lines:
            if self.board[a] != " " and self.board[a] == self.board[b] == self.board[c]:
                return self.MARKS.index(self.board[a])
        if " " not in self.board:
            return -1
        return None

    def describe(self) -> str:
        rows = []
        for r in range(3):
            rows.append(" %s | %s | %s " % tuple(self.board[r * 3 : (r + 1) * 3]))
            if r < 2:
                rows.append("---+---+---")
        return "\n".join(rows)

    def to_dict(self) -> Dict:
        return {"board": self.board, "turn": self.turn}

    @classmethod
    def from_dict(cls, data: Dict) -> "TicTacToe":
        game = cls()
        game.board = list(data["board"])
        game.turn = int(data["turn"])
        return game


# ---------------------------------------------------------------------------
# Nim — the ancient impartial game (heaps 3-4-5)
# ---------------------------------------------------------------------------


class Nim(HotseatGame):
    game_id = "hotseat-nim"

    def __init__(self, heaps: Tuple[int, ...] = (3, 4, 5)):
        self.heaps: List[int] = list(heaps)
        self.turn = 0

    def current_player(self) -> int:
        return self.turn % 2

    def legal_moves(self) -> List[str]:
        moves = []
        for i, h in enumerate(self.heaps):
            for take in range(1, h + 1):
                moves.append("%d %d" % (i, take))
        return moves

    def move_help(self) -> str:
        return (
            "play '<heap> <take>', e.g. '1 3' removes 3 from heap 1. "
            "Take the last object to WIN."
        )

    def apply_move(self, move: str) -> None:
        parts = move.strip().split()
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise GameError("use '<heap> <take>', e.g. '1 3'")
        heap, take = int(parts[0]), int(parts[1])
        if not (0 <= heap < len(self.heaps)):
            raise GameError("heap must be 0-%d" % (len(self.heaps) - 1))
        if not (1 <= take <= self.heaps[heap]):
            raise GameError(
                "heap %d has %d — take 1-%d"
                % (heap, self.heaps[heap], self.heaps[heap])
            )
        self.heaps[heap] -= take
        self.turn += 1

    def winner(self) -> Optional[int]:
        if all(h == 0 for h in self.heaps):
            return (self.turn - 1) % 2  # last move wins
        return None

    def describe(self) -> str:
        lines = []
        for i, h in enumerate(self.heaps):
            lines.append("heap %d: %s (%d)" % (i, "*" * h if h else "-", h))
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {"heaps": self.heaps, "turn": self.turn}

    @classmethod
    def from_dict(cls, data: Dict) -> "Nim":
        game = cls(tuple(data["heaps"]))
        game.turn = int(data["turn"])
        return game


TABLES: Dict[str, type] = {
    "tictactoe": TicTacToe,
    "nim": Nim,
}


# ---------------------------------------------------------------------------
# Match driver
# ---------------------------------------------------------------------------


def play_hotseat(
    game: HotseatGame,
    players: Tuple[str, str] = ("Player 1", "Player 2"),
    store=None,
    slot: Optional[str] = None,
) -> Optional[int]:
    """Run a pass-and-play match. Returns the winner (None/draw handling by caller)."""
    from levi.games.saves import SaveStore

    store = store or SaveStore()
    slot = slot or game.game_id
    print(
        "HOTSEAT — %s. %s vs %s. One keyboard, no accounts."
        % (game.game_id, players[0], players[1])
    )
    print(game.move_help())
    print("Type 'save' to save mid-game, 'quit' to abandon (no penalty).\n")

    existing = store.list_slots(game.game_id)
    if slot in existing:
        ans = input("Resume saved match in slot %r? [y/N] " % slot).strip().lower()
        if ans == "y":
            game = type(game).from_dict(store.load(game.game_id, slot))

    while True:
        print(game.describe())
        w = game.winner()
        if w is not None:
            if w == -1:
                print("\nDraw. Nobody lost anything.")
            else:
                print("\n%s wins!" % players[w])
            store.delete(game.game_id, slot)
            return w if w != -1 else None
        who = players[game.current_player()]
        try:
            text = input("%s > " % who).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return None
        if text.lower() in ("quit", "q", "exit"):
            print("Match abandoned. No streaks were harmed.")
            return None
        if text.lower() == "save":
            store.save(game.game_id, slot, game.to_dict())
            print("Saved to slot %r." % slot)
            continue
        try:
            game.apply_move(text)
        except GameError as exc:
            print(exc)
