"""Sysop stewardship: small human-stewarded rooms.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #11)

The mechanism: a room has a *named caretaker* (the sysop), a small
code of conduct, and *shared toys* — tiny turn-based game states the
members play together (door-game style: one shared state, members take
turns acting on it). The sysop judges disputes; stewardship can be
handed to another member, and every handoff is logged.

Honest limit: the toys are abstract state machines (scores, inventories,
a simple quest ledger) — playful shared objects, not full game engines.
Judgment is recorded, not automated: the sysop's rulings are entries,
not algorithms.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/sysop-stewardship"


@dataclass
class Toy:
    """A shared toy: named state plus a move function.

    ``move(state, player, action)`` returns the new state, or raises
    ValueError for an illegal action. Registered by the room's owner.
    """

    name: str
    state: Dict
    move: Callable[[Dict, str, str], Dict]


@dataclass
class Ruling:
    """A recorded judgment by the sysop."""

    sysop: str
    subject: str
    decision: str
    reason: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class StewardLog:
    """One entry in the room's stewardship history."""

    kind: str  # "founded", "handoff", "rule-added", "ruling"
    detail: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Room:
    """A small room with a named caretaker and shared toys."""

    name: str
    sysop: str
    code: List[str] = field(default_factory=list)
    members: List[str] = field(default_factory=list)
    toys: Dict[str, Toy] = field(default_factory=dict)
    log: List[StewardLog] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValueError("room name must be non-empty")
        self.sysop = (self.sysop or "").strip()
        if not self.sysop:
            raise ValueError("sysop must be named")
        if self.sysop not in self.members:
            self.members.append(self.sysop)
        self.log.append(
            StewardLog(kind="founded", detail=f"founded by sysop {self.sysop}")
        )

    # -- membership ------------------------------------------------------
    def admit(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            raise ValueError("member name must be non-empty")
        if name in self.members:
            raise ValueError(f"already a member: {name!r}")
        self.members.append(name)

    def expel(self, actor: str, name: str, reason: str = "") -> None:
        self._require_sysop(actor)
        if name == self.sysop:
            raise ValueError("sysop cannot expel themselves")
        if name not in self.members:
            raise KeyError(f"not a member: {name!r}")
        self.members.remove(name)
        self.log.append(
            StewardLog(kind="ruling", detail=f"{name} expelled by {actor}: {reason}")
        )

    # -- stewardship -----------------------------------------------------
    def add_rule(self, actor: str, rule: str) -> None:
        self._require_sysop(actor)
        rule = (rule or "").strip()
        if not rule:
            raise ValueError("rule must be non-empty")
        self.code.append(rule)
        self.log.append(
            StewardLog(kind="rule-added", detail=f"{actor} added rule: {rule}")
        )

    def hand_off(self, new_sysop: str) -> None:
        """The caretaker passes the keys to another member."""
        new_sysop = (new_sysop or "").strip()
        if new_sysop not in self.members:
            raise KeyError(f"not a member: {new_sysop!r}")
        old = self.sysop
        self.sysop = new_sysop
        self.log.append(StewardLog(kind="handoff", detail=f"{old} -> {new_sysop}"))

    def rule_on(self, subject: str, decision: str, reason: str = "") -> Ruling:
        """Record the sysop's judgment on a dispute."""
        ruling = Ruling(
            sysop=self.sysop, subject=subject, decision=decision, reason=reason
        )
        self.log.append(
            StewardLog(
                kind="ruling", detail=f"{self.sysop} ruled on {subject!r}: {decision}"
            )
        )
        return ruling

    # -- shared toys ------------------------------------------------------
    def install_toy(
        self, name: str, initial_state: Dict, move: Callable[[Dict, str, str], Dict]
    ) -> Toy:
        """Register a door-game-style shared toy with its move function."""
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("toy name must be non-empty")
        if name in self.toys:
            raise ValueError(f"toy already installed: {name!r}")
        toy = Toy(name=name, state=dict(initial_state), move=move)
        self.toys[name] = toy
        return toy

    def play(self, toy_name: str, player: str, action: str) -> Dict:
        """Take one turn on a shared toy."""
        if toy_name not in self.toys:
            raise KeyError(f"no such toy: {toy_name!r}")
        if player not in self.members:
            raise PermissionError("only members may play")
        toy = self.toys[toy_name]
        toy.state = toy.move(dict(toy.state), player, action)
        return dict(toy.state)

    def _require_sysop(self, actor: str) -> None:
        if actor != self.sysop:
            raise PermissionError(f"only sysop {self.sysop!r} may do this")


def open_room(name: str, sysop: str, code: Optional[List[str]] = None) -> Room:
    """Open a new stewarded room with its named caretaker."""
    return Room(name=name, sysop=sysop, code=list(code or []))
