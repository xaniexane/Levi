"""Path's hard cap: intimacy enforced by architecture, not policy.

Origin: Path (2010, Dave Morin) — a "personal network" that limited you to
50 friends (later 150, then 500), explicitly citing Robin Dunbar's work on
human social capacity. The friend cap was the product: with a bounded
audience you share the story of your life, not a performance. No follower
counts to grow, no public metrics to game — intimacy was enforced by
architecture, not promised by policy.

What it is in LEVI: ``BoundedSpace``. A room carries a hard membership cap;
``join`` on a full room raises — the cap cannot be exceeded by any code path.
There are deliberately no public counters: no member list, no headcount,
nothing to game. ``is_member`` and ``has_space`` answer per-caller booleans
only; counts stay private.

Honesty label: LOAD-BEARING — the cap is enforced at join time by the data
structure itself.

Deny-closed inputs: empty room names, caps below 1, joining with an empty
member name, joining twice, joining a full room, leaving when not a member,
and membership queries with an empty name are all rejected with ValueError.
"""

from __future__ import annotations

__all__ = ["BoundedSpace"]


class BoundedSpace:
    """A room with a hard membership cap and no public metrics."""

    def __init__(self, name: str, cap: int) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("room name must be a non-empty string")
        if isinstance(cap, bool) or not isinstance(cap, int):
            raise ValueError(f"cap must be an integer, got {cap!r}")
        if cap < 1:
            raise ValueError(f"cap must be at least 1, got {cap}")
        self._name = name.strip()
        self._cap = cap
        self._members: dict[str, None] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def cap(self) -> int:
        return self._cap

    def _check_member(self, member: str) -> str:
        if not isinstance(member, str) or not member.strip():
            raise ValueError("member name must be a non-empty string")
        return member.strip()

    def join(self, member: str) -> None:
        """Enter the room. A full room refuses — the cap is the product."""
        member = self._check_member(member)
        if member in self._members:
            raise ValueError(f"{member!r} is already in {self._name!r}")
        if len(self._members) >= self._cap:
            raise ValueError(
                f"{self._name!r} is full (cap {self._cap}): "
                "the cap is enforced by architecture, not policy"
            )
        self._members[member] = None

    def leave(self, member: str) -> None:
        member = self._check_member(member)
        if member not in self._members:
            raise ValueError(f"{member!r} is not in {self._name!r}")
        del self._members[member]

    def is_member(self, member: str) -> bool:
        """Per-caller membership check. No list, no count — nothing to game."""
        return self._check_member(member) in self._members

    def has_space(self) -> bool:
        """Whether one more member fits. A boolean, not a number."""
        return len(self._members) < self._cap

    def is_full(self) -> bool:
        return len(self._members) >= self._cap
