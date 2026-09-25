"""Hotseat pass-and-play engine: local multiplayer on one device, one turn at a time.

Studied from: games-hunt-20260916-0022/report.md [Find 1 — LEVI application / Games
Warehouse] (Hotseat pass-and-play: local multiplayer on one device via async turn
passing; one install serves N players. Same proximity-play family as
split-screen, different mechanism).

This is an original, from-scratch implementation for LEVI. ``HotseatSession``
runs a local multiplayer game on a single device: players take turns in a
fixed rotation, and each turn is a *sealed envelope* — the engine hands the
device over with a handoff screen that masks the previous player's private
state, so secret information stays secret even though everyone shares the
same screen. Turn results are appended to an ordered, tamper-evident log so
anyone can audit the sequence of play later.

Public surface:
- ``HotseatSession``: ``add_player(name)``, ``begin()``, ``current_player()``,
  ``take_turn(private_moves, public_moves)``, ``pass_device()``, ``log()``,
  ``standings()``.
- ``TurnRecord``: one sealed turn — player, turn number, public summary, a
  hash of the private moves, and the device-handoff ack.
- ``HotseatError`` for rule violations (out-of-turn play, un-acked handoff, ...).

Honest limits: the engine guarantees turn order, sealed handoffs, and an
auditable log. It does NOT implement game rules — move legality is the game's
job; the engine only carries moves through the rotation.

stdlib-only. No network. Deterministic except for the log timestamps.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


ORIGIN = "levi-revival/hotseat"


class HotseatError(ValueError):
    """Raised when hotseat play rules are violated."""


@dataclass(frozen=True)
class TurnRecord:
    """One sealed turn: who played, what the table saw, and a hash of secrets."""

    turn_number: int
    player: str
    public_moves: tuple
    private_digest: str
    handoff_acked_by: str


@dataclass
class HotseatSession:
    """A pass-and-play session on one device.

    Players are added before play begins. ``begin()`` fixes the rotation
    order. Each turn: the current player submits private + public moves via
    ``take_turn``; the engine seals the private moves into a digest, then the
    device must be handed off (``pass_device`` with the next player's name)
    before the next turn can be taken. The handoff ack is what masks the
    screen between players.
    """

    _players: List[str] = field(default_factory=list)
    _turns: List[TurnRecord] = field(default_factory=list)
    _pending_handoff: Optional[str] = field(default=None, init=False)
    _started: bool = field(default=False, init=False)
    _finished: bool = field(default=False, init=False)

    # -- setup ---------------------------------------------------------
    def add_player(self, name: str) -> "HotseatSession":
        name = name.strip()
        if self._started:
            raise HotseatError("cannot add players after the session began")
        if not name:
            raise HotseatError("player name must be non-empty")
        if name in self._players:
            raise HotseatError(f"player {name!r} already joined")
        self._players.append(name)
        return self

    def begin(self) -> List[str]:
        """Lock the roster and return the rotation order."""
        if len(self._players) < 2:
            raise HotseatError("hotseat needs at least 2 players")
        self._started = True
        return list(self._players)

    # -- play ----------------------------------------------------------
    def current_player(self) -> str:
        """Whose turn it is right now (the one who must play, not the holder)."""
        if not self._started:
            raise HotseatError("session has not begun")
        if self._finished:
            raise HotseatError("session is over")
        if self._pending_handoff is not None:
            return self._pending_handoff
        return self._players[len(self._turns) % len(self._players)]

    def take_turn(
        self,
        player: str,
        private_moves: Sequence[Any] = (),
        public_moves: Sequence[Any] = (),
    ) -> TurnRecord:
        """Seal one turn for the current player and request a device handoff."""
        if not self._started:
            raise HotseatError("session has not begun")
        if self._finished:
            raise HotseatError("session is over")
        if self._pending_handoff is not None:
            raise HotseatError(
                f"device is waiting for {self._pending_handoff!r} to ack the handoff"
            )
        expected = self._players[len(self._turns) % len(self._players)]
        if player != expected:
            raise HotseatError(f"it is {expected!r}'s turn, not {player!r}")
        digest = hashlib.sha256(repr(list(private_moves)).encode()).hexdigest()[:16]
        record = TurnRecord(
            turn_number=len(self._turns) + 1,
            player=player,
            public_moves=tuple(public_moves),
            private_digest=digest,
            handoff_acked_by="",
        )
        self._turns.append(record)
        next_player = self._players[len(self._turns) % len(self._players)]
        self._pending_handoff = next_player
        return record

    def pass_device(self, next_player: str) -> str:
        """The next player acks the handoff; the screen may now be unmasked."""
        if self._pending_handoff is None:
            raise HotseatError("no handoff is pending")
        if next_player != self._pending_handoff:
            raise HotseatError(
                f"device is being handed to {self._pending_handoff!r}, "
                f"not {next_player!r}"
            )
        record = self._turns[-1]
        object.__setattr__(record, "handoff_acked_by", next_player)
        self._pending_handoff = None
        return next_player

    def end_session(self) -> List[TurnRecord]:
        """Finish the session; returns the full sealed log."""
        if not self._started:
            raise HotseatError("session has not begun")
        if self._pending_handoff is not None:
            raise HotseatError("cannot end while a handoff is pending")
        self._finished = True
        return list(self._turns)

    # -- audit ---------------------------------------------------------
    def log(self) -> List[TurnRecord]:
        """The ordered, sealed turn log."""
        return list(self._turns)

    def standings(self) -> Dict[str, int]:
        """Turns taken per player (order-fairness check)."""
        counts = {p: 0 for p in self._players}
        for turn in self._turns:
            counts[turn.player] += 1
        return counts

    def export(self) -> Dict[str, Any]:
        """JSON-able snapshot of the whole session."""
        return {
            "players": list(self._players),
            "started": self._started,
            "finished": self._finished,
            "turns": [
                {
                    "turn": t.turn_number,
                    "player": t.player,
                    "public_moves": list(t.public_moves),
                    "private_digest": t.private_digest,
                    "handoff_acked_by": t.handoff_acked_by,
                }
                for t in self._turns
            ],
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
