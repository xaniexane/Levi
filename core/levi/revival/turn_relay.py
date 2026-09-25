"""Async turn relay: the play-by-mail ritual as portable file-drop envelopes.

Studied from: dead-game-genres-2026-09-16/report.md [Build shortlist - dead
multiplayer ritual revival] (the brief's shape: the BBS-door / play-by-mail
ritual without the BBS - turns passed as portable envelopes, tamper-evident
so a player cannot quietly rewrite history).

This is an original, from-scratch implementation for LEVI. A ``Relay``
manages a game played by turns: each ``Turn`` is a JSON envelope written to
a drop directory (any shared folder, USB stick, or synced dir works - the
transport is just files). Every envelope carries ``prev_hash`` - the SHA-256
of the previous turn's canonical bytes - forming a hash chain back to a
genesis envelope. ``verify()`` replays the chain and reports the first
broken link, so tampering (edited moves, dropped turns, reordered turns) is
detected, not prevented. ``GameState`` is a plain dict the players' move
functions transform; the relay itself is game-agnostic, with a tiny
"countdown" demo game included.

Honest limits: this gives tamper *evidence*, not tamper *proof* - a player
with write access can always fork a new chain from genesis (that's inherent
to file-drop play); identity is by claimed seat name, not cryptography
(no signatures - out of scope for the ritual).

Public surface:
- ``Relay(drop_dir, game)``: ``genesis(state, seats)`` / ``submit(seat, move)`` /
  ``read_turn(n)`` / ``verify()`` -> ``ChainReport`` / ``latest()``.
- ``Turn``: envelope dataclass with ``hash()``.
- ``demo_game()``: a countdown game (players subtract 1-3 from a pile; last move wins).

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/turn-relay"


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Turn:
    """One envelope in the chain."""

    n: int  # sequence number (0 = genesis)
    game: str  # game id
    seat: str  # who moved ("__genesis__" for turn 0)
    move: Dict[str, Any]  # the move that produced this state
    state: Dict[str, Any]  # full game state AFTER the move
    prev_hash: str  # sha256 of previous turn's canonical bytes
    note: str = ""

    def payload(self) -> Dict[str, Any]:
        return {
            "n": self.n,
            "game": self.game,
            "seat": self.seat,
            "move": self.move,
            "state": self.state,
            "prev_hash": self.prev_hash,
            "note": self.note,
        }

    def hash(self) -> str:
        return _sha256(_canonical(self.payload()))


@dataclass
class ChainReport:
    ok: bool
    turns_checked: int
    broken_at: Optional[int] = None
    detail: str = ""


@dataclass
class Relay:
    """File-drop turn relay for one game instance."""

    drop_dir: str
    game: str
    # move_fn(state, move) -> new_state ; legal_fn(state, seat, move) -> error|None
    move_fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]] = field(
        default=lambda s, m: dict(s)
    )
    legal_fn: Callable[[Dict[str, Any], str, Dict[str, Any]], Optional[str]] = field(
        default=lambda s, seat, m: None
    )

    def __post_init__(self) -> None:
        os.makedirs(self.drop_dir, exist_ok=True)
        self._cache: List[Turn] = []
        self._load()

    # -- paths ------------------------------------------------------------------
    def _path(self, n: int) -> str:
        return os.path.join(self.drop_dir, f"turn-{n:04d}.json")

    def _load(self) -> None:
        self._cache.clear()
        n = 0
        while os.path.exists(self._path(n)):
            with open(self._path(n), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._cache.append(Turn(**data))
            n += 1

    # -- game flow ----------------------------------------------------------------
    def genesis(self, state: Dict[str, Any], seats: List[str], note: str = "") -> Turn:
        if self._cache:
            raise ValueError("chain already started - genesis exists")
        if len(seats) < 1:
            raise ValueError("need at least one seat")
        turn = Turn(
            n=0,
            game=self.game,
            seat="__genesis__",
            move={"seats": seats},
            state=dict(state),
            prev_hash="0" * 64,
            note=note,
        )
        self._write(turn)
        return turn

    def submit(self, seat: str, move: Dict[str, Any], note: str = "") -> Turn:
        """Apply a move as the next turn. Raises ValueError if illegal."""
        if not self._cache:
            raise ValueError("no genesis yet - call genesis() first")
        last = self._cache[-1]
        seats = self._seats()
        if seat not in seats:
            raise ValueError(f"{seat!r} is not a seat in this game")
        # genesis is turn 0, so turn n is taken by seats[(n-1) % len(seats)]
        expected = seats[last.n % len(seats)]
        if seat != expected:
            raise ValueError(f"it's {expected}'s turn, not {seat}'s")
        move = dict(move)
        move.setdefault("seat", seat)  # every envelope records who moved
        err = self.legal_fn(last.state, seat, move)
        if err:
            raise ValueError(f"illegal move: {err}")
        new_state = self.move_fn(dict(last.state), dict(move))
        turn = Turn(
            n=last.n + 1,
            game=self.game,
            seat=seat,
            move=dict(move),
            state=new_state,
            prev_hash=last.hash(),
            note=note,
        )
        self._write(turn)
        return turn

    def _seats(self) -> List[str]:
        return list(self._cache[0].move.get("seats", []))

    def _write(self, turn: Turn) -> None:
        with open(self._path(turn.n), "w", encoding="utf-8") as fh:
            json.dump(turn.payload(), fh, indent=2, sort_keys=True)
            fh.write("\n")
        self._cache.append(turn)

    # -- reading --------------------------------------------------------------------
    def latest(self) -> Optional[Turn]:
        return self._cache[-1] if self._cache else None

    def read_turn(self, n: int) -> Turn:
        if not (0 <= n < len(self._cache)):
            raise IndexError(f"no turn {n}")
        return self._cache[n]

    def history(self) -> List[Turn]:
        return list(self._cache)

    # -- verification -------------------------------------------------------------------
    def verify(self) -> ChainReport:
        """Replay the hash chain; report the first broken link, if any."""
        if not self._cache:
            return ChainReport(ok=False, turns_checked=0, detail="empty chain")
        genesis = self._cache[0]
        if genesis.n != 0 or genesis.prev_hash != "0" * 64:
            return ChainReport(
                ok=False,
                turns_checked=0,
                broken_at=0,
                detail="genesis envelope malformed",
            )
        for i in range(1, len(self._cache)):
            prev, cur = self._cache[i - 1], self._cache[i]
            if cur.n != prev.n + 1:
                return ChainReport(
                    ok=False,
                    turns_checked=i,
                    broken_at=cur.n,
                    detail=f"sequence break: turn {prev.n} -> {cur.n}",
                )
            if cur.prev_hash != prev.hash():
                return ChainReport(
                    ok=False,
                    turns_checked=i,
                    broken_at=cur.n,
                    detail=(
                        f"hash mismatch at turn {cur.n}: "
                        f"prev_hash does not match turn {prev.n}"
                    ),
                )
        return ChainReport(
            ok=True,
            turns_checked=len(self._cache),
            detail=f"chain of {len(self._cache)} turns intact",
        )


# ---------------------------------------------------------------------------
# Demo game: countdown. Pile starts at 21; each move subtracts 1-3.
# The seat that takes the last token wins.
# ---------------------------------------------------------------------------


def _countdown_move(state: Dict[str, Any], move: Dict[str, Any]) -> Dict[str, Any]:
    state = dict(state)
    take = int(move["take"])
    state["pile"] -= take
    state["moves"] = state.get("moves", 0) + 1
    if state["pile"] <= 0:
        state["pile"] = 0
        state["winner"] = move.get("seat", "?")
    return state


def _countdown_legal(
    state: Dict[str, Any], seat: str, move: Dict[str, Any]
) -> Optional[str]:
    if state.get("winner"):
        return "game already over"
    try:
        take = int(move["take"])
    except (KeyError, TypeError, ValueError):
        return "move needs {'take': 1-3}"
    if take not in (1, 2, 3):
        return "take must be 1, 2, or 3"
    if take > state["pile"]:
        return f"only {state['pile']} left in the pile"
    return None


def demo_relay(drop_dir: str) -> Relay:
    """A relay pre-wired for the countdown demo game."""

    def move_fn(state: Dict[str, Any], move: Dict[str, Any]) -> Dict[str, Any]:
        return _countdown_move(state, move)

    def legal_fn(
        state: Dict[str, Any], seat: str, move: Dict[str, Any]
    ) -> Optional[str]:
        return _countdown_legal(state, seat, move)

    return Relay(
        drop_dir=drop_dir, game="countdown", move_fn=move_fn, legal_fn=legal_fn
    )
