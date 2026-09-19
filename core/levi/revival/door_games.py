"""LEVI's door arcade: appointment-dynamic games on a shared persistent world.

Studied from: dead-networks-20260916/report.md [BBS door games].

The load-bearing shape of a BBS door game: an *external program* attaches
to a live session by reading a small identity file (the "drop file") the
host writes when the player enters; the player gets a *fixed number of
turns per day* (the appointment dynamic — you come back tomorrow); the
world is *persistent and shared* across every visitor; and player-vs-player
happens *asynchronously* — you leave an attack behind, your rival resolves
it on their next visit.

``door_games`` rebuilds that shape from scratch, LEVI-native:

- ``DropFile`` — the session identity card (user, node, time left),
  serialized to a tiny line-based text format.
- ``TurnLedger`` — turns per player per day, resetting on the local date.
- ``SharedWorld`` — a persistent key/value world with an append-only event
  journal (honest play: every mutation is attributable).
- ``Challenge`` — async PvP: an attack recorded now, resolved later with a
  seeded roll so the outcome is reproducible, not re-rolled in secret.
- ``DoorServer`` — hosts named doors and hands out turn-limited visits.

Local-first, stdlib only, no network. Persistence here is in-memory with
an explicit ``snapshot()``/``restore()`` pair — wiring it to disk is the
host's job, not hidden I/O. Outcomes are deterministic given their seed;
nothing here pretends to be chance it isn't.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/door-games"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DoorError(Exception):
    """Base class for door-game failures."""


class NoTurnsLeft(DoorError):
    """The player has spent today's turn allowance on this door."""


class UnknownDoor(DoorError):
    """No door with that name is hosted."""


class BadDropFile(DoorError):
    """A drop file could not be parsed."""


class ChallengeError(DoorError):
    """An async PvP challenge was misused (e.g. resolved twice)."""


# ---------------------------------------------------------------------------
# DropFile — the session identity card
# ---------------------------------------------------------------------------


@dataclass
class DropFile:
    """Who just walked in: user name, node number, session id, minutes left.

    The host writes this when the player enters the door; the door reads
    it to know who it's talking to. Plain ``key=value`` lines — trivially
    auditable, no binary formats.
    """

    user: str
    node: int = 1
    session_id: str = ""
    time_left_minutes: int = 30

    def to_text(self) -> str:
        lines = [
            f"user={self.user}",
            f"node={self.node}",
            f"session_id={self.session_id}",
            f"time_left_minutes={self.time_left_minutes}",
        ]
        return "\n".join(lines) + "\n"

    @classmethod
    def from_text(cls, text: str) -> "DropFile":
        data: Dict[str, str] = {}
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise BadDropFile(f"line {lineno}: no '=' in {raw!r}")
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()
        if "user" not in data:
            raise BadDropFile("drop file has no 'user' field")
        try:
            return cls(
                user=data["user"],
                node=int(data.get("node", "1")),
                session_id=data.get("session_id", ""),
                time_left_minutes=int(data.get("time_left_minutes", "30")),
            )
        except ValueError as exc:
            raise BadDropFile(f"bad numeric field: {exc}") from exc


# ---------------------------------------------------------------------------
# TurnLedger — the appointment dynamic
# ---------------------------------------------------------------------------


def _day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


class TurnLedger:
    """Fixed turns per player per day. The day rolls over on local date.

    Usage is keyed ``(player, day)`` so yesterday's spending never leaks
    into today. The clock is injectable (``now`` parameter) so tests and
    hosts can simulate the appointment boundary honestly.
    """

    def __init__(self, turns_per_day: int):
        if turns_per_day < 1:
            raise DoorError("turns_per_day must be >= 1")
        self.turns_per_day = turns_per_day
        self._used: Dict[str, int] = {}

    def _slot(self, player: str, now: float) -> str:
        return f"{player}\x00{_day_key(now)}"

    def turns_left(self, player: str, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        used = self._used.get(self._slot(player, now), 0)
        return max(0, self.turns_per_day - used)

    def use_turn(self, player: str, now: Optional[float] = None) -> int:
        """Spend one turn; returns turns remaining. Raises NoTurnsLeft."""
        now = time.time() if now is None else now
        slot = self._slot(player, now)
        used = self._used.get(slot, 0)
        if used >= self.turns_per_day:
            raise NoTurnsLeft(f"{player} has no turns left today")
        self._used[slot] = used + 1
        return self.turns_per_day - used - 1


# ---------------------------------------------------------------------------
# SharedWorld — persistent world + honest-play journal
# ---------------------------------------------------------------------------


@dataclass
class WorldEvent:
    seq: int
    timestamp: float
    actor: str
    kind: str
    detail: str


class SharedWorld:
    """The persistent shared world every visitor mutates together.

    ``store`` is the world state; ``journal`` is the append-only event log
    that makes play honest — every mutation records who did what and when.
    ``version`` bumps on every mutation so visitors can detect that the
    world moved under them.
    """

    def __init__(self):
        self.store: Dict[str, Any] = {}
        self.journal: List[WorldEvent] = []
        self.version: int = 0

    def apply(
        self,
        actor: str,
        kind: str,
        detail: str,
        mutator: Callable[[Dict[str, Any]], None],
        now: Optional[float] = None,
    ) -> int:
        """Run ``mutator(store)``, journal it, bump version. Returns version."""
        mutator(self.store)
        self.version += 1
        self.journal.append(
            WorldEvent(
                seq=len(self.journal),
                timestamp=time.time() if now is None else now,
                actor=actor,
                kind=kind,
                detail=detail,
            )
        )
        return self.version

    def read(self, key: str, default: Any = None) -> Any:
        return self.store.get(key, default)

    def history(self, actor: Optional[str] = None) -> List[WorldEvent]:
        if actor is None:
            return list(self.journal)
        return [e for e in self.journal if e.actor == actor]

    def snapshot(self) -> Dict[str, Any]:
        return {"store": dict(self.store), "version": self.version}

    def restore(self, snap: Dict[str, Any]) -> None:
        self.store = dict(snap["store"])
        self.version = int(snap["version"])


# ---------------------------------------------------------------------------
# Challenge — asynchronous PvP
# ---------------------------------------------------------------------------


@dataclass
class Challenge:
    """An attack left behind for a rival to resolve on their next visit.

    The attacker commits ``attack_power`` and a ``seed`` now; when the
    defender (or the host on their behalf) resolves it, the outcome is
    computed deterministically from that seed — the attacker can't
    re-roll, and the defender can audit the roll. Resolving twice is an
    error, not a second fight.
    """

    attacker: str
    defender: str
    attack_power: int
    seed: int
    note: str = ""
    resolved: bool = False
    outcome: str = ""
    margin: int = 0

    def resolve(self, defender_power: int) -> "Challenge":
        if self.resolved:
            raise ChallengeError("challenge already resolved")
        # Deterministic roll from the committed seed: a tiny LCG so the
        # result is reproducible and auditable without any hidden state.
        state = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
        attack_roll = (state >> 16) % 100
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        defend_roll = (state >> 16) % 100
        attack_total = self.attack_power + attack_roll
        defend_total = defender_power + defend_roll
        self.margin = attack_total - defend_total
        if self.margin > 0:
            self.outcome = f"{self.attacker} wins ({attack_total} vs {defend_total})"
        elif self.margin < 0:
            self.outcome = f"{self.defender} holds ({defend_total} vs {attack_total})"
        else:
            self.outcome = f"draw ({attack_total} vs {defend_total})"
        self.resolved = True
        return self


# ---------------------------------------------------------------------------
# Door / DoorServer — hosting
# ---------------------------------------------------------------------------


@dataclass
class Visit:
    """One player's turn-limited stay inside a door."""

    door_name: str
    player: str
    turns_left: int
    world: SharedWorld


class Door:
    """A named game with its own turn allowance and shared world."""

    def __init__(self, name: str, turns_per_day: int = 5):
        self.name = name
        self.ledger = TurnLedger(turns_per_day)
        self.world = SharedWorld()
        self.pending_challenges: List[Challenge] = []

    def enter(self, drop: DropFile, now: Optional[float] = None) -> Visit:
        left = self.ledger.use_turn(drop.user, now)
        return Visit(
            door_name=self.name,
            player=drop.user,
            turns_left=left,
            world=self.world,
        )

    def issue_challenge(
        self, attacker: str, defender: str, attack_power: int, seed: int, note: str = ""
    ) -> Challenge:
        chal = Challenge(
            attacker=attacker,
            defender=defender,
            attack_power=attack_power,
            seed=seed,
            note=note,
        )
        self.pending_challenges.append(chal)
        self.world.apply(
            attacker,
            "challenge",
            f"{attacker} challenges {defender} (power {attack_power}) {note}".strip(),
            lambda s: None,
        )
        return chal

    def challenges_for(self, defender: str) -> List[Challenge]:
        return [
            c
            for c in self.pending_challenges
            if c.defender == defender and not c.resolved
        ]


class DoorServer:
    """Hosts several doors; routes drop files to the right one."""

    def __init__(self):
        self.doors: Dict[str, Door] = {}

    def host(self, door: Door) -> None:
        if door.name in self.doors:
            raise DoorError(f"door {door.name!r} already hosted")
        self.doors[door.name] = door

    def enter(
        self, door_name: str, drop: DropFile, now: Optional[float] = None
    ) -> Visit:
        try:
            door = self.doors[door_name]
        except KeyError:
            raise UnknownDoor(f"no door named {door_name!r}") from None
        return door.enter(drop, now)
