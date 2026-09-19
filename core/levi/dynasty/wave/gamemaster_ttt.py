# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Gamemaster's first real title: tic-tac-toe, end to end.

The platform's one-game-first proof: a REAL game engine (no dice-duel
simulation here) with a perfect-play minimax opponent and receipted
matches. Every turn of a match is hashed into a chain — each turn hash
binds the previous turn's hash, the move, and the board after it — so
a corrupt or reordered turn order cannot be constructed after the
fact: the chain simply will not verify.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Optional, Tuple

from levi.dynasty.dna import AgentError, scrub_text

__all__ = [
    "LINES",
    "MoveError",
    "apply_move",
    "best_move",
    "legal_moves",
    "new_board",
    "play_game",
    "verify_chain",
    "winner",
]

# Board: a 9-tuple, positions 0..8 row-major. Cells are 'X', 'O', or None.
Board = Tuple[Optional[str], ...]

LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)

_PLAYERS = ("X", "O")
_GENESIS = "genesis"
_MAX_NAME_LEN = 64


class MoveError(AgentError):
    """Illegal move, bad position, bad player, or bad game state."""


def _check_board(board: Any) -> Board:
    if not isinstance(board, (tuple, list)) or len(board) != 9:
        raise MoveError("board must be a 9-cell sequence")
    cells = tuple(board)
    for cell in cells:
        if cell not in ("X", "O", None):
            raise MoveError(f"bad cell value {cell!r}")
    return cells


def _check_player(player: Any) -> str:
    if player not in _PLAYERS:
        raise MoveError(f"player must be one of {_PLAYERS}, got {player!r}")
    return player


def _check_pos(pos: Any) -> int:
    if isinstance(pos, bool) or not isinstance(pos, int):
        raise MoveError(f"position must be an int 0..8, got {pos!r}")
    if not 0 <= pos <= 8:
        raise MoveError(f"position out of range 0..8, got {pos}")
    return pos


def _check_name(name: Any, what: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise MoveError(f"{what} must be a non-empty string")
    clean = name.strip()
    if len(clean) > _MAX_NAME_LEN:
        raise MoveError(f"{what} too long (>{_MAX_NAME_LEN} chars)")
    if any(ord(c) < 32 for c in clean):
        raise MoveError(f"{what} carries control characters")
    return scrub_text(clean)


def _other(player: str) -> str:
    return "O" if player == "X" else "X"


def new_board() -> Board:
    """A fresh empty board."""
    return (None,) * 9


def legal_moves(board: Board) -> List[int]:
    """Ascending list of empty positions."""
    board = _check_board(board)
    return [i for i, cell in enumerate(board) if cell is None]


def apply_move(board: Board, player: str, pos: int) -> Board:
    """Return a NEW board with ``player`` at ``pos``; never mutates.

    Raises MoveError for a bad player, a bad position, an occupied
    cell, or a move on a finished game.
    """
    board = _check_board(board)
    player = _check_player(player)
    pos = _check_pos(pos)
    if winner(board) is not None:
        raise MoveError("the game is already over")
    if board[pos] is not None:
        raise MoveError(f"cell {pos} is already taken by {board[pos]!r}")
    return board[:pos] + (player,) + board[pos + 1 :]


def winner(board: Board) -> Optional[str]:
    """'X' | 'O' | 'draw' | None (game still on)."""
    board = _check_board(board)
    for a, b, c in LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    if all(cell is not None for cell in board):
        return "draw"
    return None


def _minimax(
    board: Board, to_move: str, maximizer: str, depth: int, depth_limit: int
) -> int:
    """Score from ``maximizer``'s view. Terminal states win/lose/draw;
    past ``depth_limit`` the heuristic is neutral (0)."""
    result = winner(board)
    if result == maximizer:
        return 10 - depth
    if result == _other(maximizer):
        return depth - 10
    if result == "draw":
        return 0
    if depth >= depth_limit:
        return 0
    scores = (
        _minimax(
            apply_move(board, to_move, pos),
            _other(to_move),
            maximizer,
            depth + 1,
            depth_limit,
        )
        for pos in legal_moves(board)
    )
    return max(scores) if to_move == maximizer else min(scores)


def best_move(board: Board, player: str, depth_limit: int = 9) -> int:
    """Perfect-play move within the depth limit.

    With ``depth_limit=9`` a full game fits inside the horizon, so play
    is perfect: never loses, takes wins, blocks losses. Ties break to
    the lowest position index — fully deterministic.
    """
    board = _check_board(board)
    player = _check_player(player)
    if isinstance(depth_limit, bool) or not isinstance(depth_limit, int):
        raise MoveError("depth_limit must be an int")
    if depth_limit < 1:
        raise MoveError("depth_limit must be >= 1")
    if winner(board) is not None:
        raise MoveError("best_move on a finished game")
    best: Optional[int] = None
    best_score = float("-inf")
    for pos in legal_moves(board):  # ascending: first win keeps lowest index
        score = _minimax(
            apply_move(board, player, pos), _other(player), player, 1, depth_limit
        )
        if score > best_score:
            best_score = score
            best = pos
    assert best is not None  # game not over, so a move exists
    return best


def _board_str(board: Board) -> str:
    return "".join(cell if cell is not None else "." for cell in board)


def _turn_hash(prev_hash: str, turn: int, player: str, pos: int, board: Board) -> str:
    body = f"{prev_hash}|{turn}:{player}:{pos}:{_board_str(board)}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _random_move(board: Board, rng: random.Random) -> int:
    return rng.choice(legal_moves(board))


def play_game(
    player_x: str,
    player_o: str,
    x_moves: Optional[List[int]] = None,
    o_policy: str = "minimax",
    o_seed: int = 0,
) -> Dict[str, Any]:
    """Play a full tic-tac-toe match to its end, receipted per turn.

    ``x_moves`` is an optional scripted move list for X (each must be
    legal when played, else MoveError); when the script runs out, X
    falls back to minimax. ``o_policy`` is 'minimax' or 'random'.

    Returns the match record: winner, per-turn move log, the hash chain,
    and the final hash. The chain is constructed as it is played —
    there is no API to insert, reorder, or rewrite a turn, so a corrupt
    turn order is impossible by construction.
    """
    x = _check_name(player_x, "player_x")
    o = _check_name(player_o, "player_o")
    if x == o:
        raise MoveError("a match needs two distinct players")
    if o_policy not in ("minimax", "random"):
        raise MoveError(f"unknown o_policy {o_policy!r}")
    if x_moves is not None:
        if not isinstance(x_moves, list):
            raise MoveError("x_moves must be a list of positions or None")
        for pos in x_moves:
            _check_pos(pos)

    script = list(x_moves) if x_moves else []
    rng = random.Random(f"ttt|{o_seed}|{x}|{o}")
    board = new_board()
    moves: List[Dict[str, Any]] = []
    turn_hashes: List[str] = []
    prev = _GENESIS
    turn = 0

    while winner(board) is None:
        mark = "X" if turn % 2 == 0 else "O"
        name = x if mark == "X" else o
        if mark == "X" and script:
            pos = script.pop(0)
            if pos not in legal_moves(board):
                raise MoveError(f"scripted X move {pos} is illegal on turn {turn + 1}")
        elif mark == "O" and o_policy == "random":
            pos = _random_move(board, rng)
        else:
            pos = best_move(board, mark)
        board = apply_move(board, mark, pos)
        turn += 1
        turn_hash = _turn_hash(prev, turn, mark, pos, board)
        moves.append(
            {
                "turn": turn,
                "player": mark,
                "name": name,
                "pos": pos,
                "turn_hash": turn_hash,
            }
        )
        turn_hashes.append(turn_hash)
        prev = turn_hash

    return {
        "game": "tic-tac-toe",
        "player_x": x,
        "player_o": o,
        "winner": winner(board),
        "moves": moves,
        "turn_hashes": turn_hashes,
        "final_hash": prev,
    }


def verify_chain(match: Dict[str, Any]) -> bool:
    """Recompute the turn chain from the move log; True iff it holds.

    Catches any tampering: a swapped turn, a changed position, or a
    forged hash breaks the chain at (or before) the altered turn.
    """
    try:
        moves = match["moves"]
        if not isinstance(moves, list) or not moves:
            return False
        board = new_board()
        prev = _GENESIS
        for i, move in enumerate(moves, start=1):
            if move.get("turn") != i:
                return False
            player = move.get("player")
            pos = move.get("pos")
            board = apply_move(board, player, pos)
            expected = _turn_hash(prev, i, player, pos, board)
            if move.get("turn_hash") != expected:
                return False
            prev = expected
        return prev == match.get("final_hash") and len(
            match.get("turn_hashes", [])
        ) == len(moves)
    except (MoveError, TypeError, KeyError, AttributeError):
        return False
