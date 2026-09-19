"""Audience circles: granular per-post sharing grammar.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #2] (circles-style audience control: granular per-post/per-circle
sharing grammar across everything emitted; the default question is "who is
this for?").

This is an original, from-scratch implementation for LEVI. People are
organized into named ``Circle``s (family, collaborators, reading-club, ...).
Every emitted item carries an explicit ``Audience`` — the module refuses to
emit without one, because the default-first question is always "who is this
for?".

The grammar (all local, all inspectable):
- ``to(circle)`` — visible to members of that circle.
- ``to(c1) + to(c2)`` — union of circles (``Audience.combine``).
- ``to(c) - person`` — everyone in the circle except that person
  (``Audience.exclude``).
- ``to_all()`` — public to everyone known to the circles graph.
- ``only(person)`` — exactly one person.
- default audience: ``Audience.default_for(owner)`` resolves to the owner's
  configured default circle, or the built-in private ``me`` circle when none
  is set.

Resolution is pure set math over membership lists — no inference, no
"suggested audiences", no silent widening. ``visible_to(viewer)`` tells the
truth about who can see what, and ``explain()`` renders the audience back
into the human grammar so the owner can audit it.

Honest limits:
- This is an authorization *description*, not enforcement: it computes who
  *should* see an item. A storage/rendering layer must consult it.
- Membership lists are explicit; there is no group-discovery and circles do
  not nest (keeps resolution trivially auditable).

Public surface:
- ``Circles``: ``add_circle``, ``add_member``, ``remove_member``,
  ``members``, ``everyone``, ``set_default_circle``, ``default_circle``.
- ``Audience``: ``to``, ``to_all``, ``only``, ``me``, ``default_for``,
  ``combine``, ``exclude``, ``resolve``, ``visible_to``, ``explain``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Set

ORIGIN = "levi-revival/audience-circles"

_PRIVATE_CIRCLE = "me"


class CirclesError(ValueError):
    """Raised when a circle or member reference is invalid."""


class Circles:
    """Named, explicit membership lists. Circles never nest."""

    def __init__(self, owner: str = "me") -> None:
        self.owner = owner
        self._circles: Dict[str, Set[str]] = {_PRIVATE_CIRCLE: {owner}}
        self._default: str = _PRIVATE_CIRCLE

    # -- membership --------------------------------------------------------

    def add_circle(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise CirclesError("circle name cannot be empty")
        if name in self._circles:
            raise CirclesError(f"circle {name!r} already exists")
        self._circles[name] = set()

    def add_member(self, circle: str, person: str) -> None:
        circle = circle.strip()
        person = person.strip()
        if circle not in self._circles:
            raise CirclesError(f"unknown circle {circle!r}")
        if not person:
            raise CirclesError("member name cannot be empty")
        self._circles[circle].add(person)

    def remove_member(self, circle: str, person: str) -> None:
        circle = circle.strip()
        if circle == _PRIVATE_CIRCLE:
            raise CirclesError("the private circle always contains only the owner")
        try:
            self._circles[circle].remove(person.strip())
        except KeyError:
            raise CirclesError(f"{person!r} is not a member of {circle!r}") from None

    def members(self, circle: str) -> FrozenSet[str]:
        circle = circle.strip()
        if circle not in self._circles:
            raise CirclesError(f"unknown circle {circle!r}")
        return frozenset(self._circles[circle])

    def circles(self) -> List[str]:
        return sorted(self._circles)

    def everyone(self) -> FrozenSet[str]:
        """Every person known across all circles."""
        known: Set[str] = set()
        for members in self._circles.values():
            known.update(members)
        return frozenset(known)

    # -- the default-first question ----------------------------------------

    def set_default_circle(self, name: str) -> None:
        name = name.strip()
        if name not in self._circles:
            raise CirclesError(f"unknown circle {name!r}")
        self._default = name

    def default_circle(self) -> str:
        return self._default


class Audience:
    """Immutable audience description for one emitted item.

    Build via the grammar helpers; resolution is pure set math.
    """

    __slots__ = ("_circles", "_people", "_excludes", "_all", "_label")

    def __init__(
        self,
        circles: Iterable[str] = (),
        people: Iterable[str] = (),
        excludes: Iterable[str] = (),
        all_: bool = False,
        label: str = "",
    ) -> None:
        self._circles = frozenset(circles)
        self._people = frozenset(people)
        self._excludes = frozenset(excludes)
        self._all = all_
        self._label = label

    # -- grammar -----------------------------------------------------------

    @classmethod
    def to(cls, *circle_names: str) -> "Audience":
        """Visible to the members of the named circle(s)."""
        names = [c.strip() for c in circle_names if c.strip()]
        if not names:
            raise CirclesError("Audience.to needs at least one circle name")
        return cls(circles=names, label="to " + ", ".join(names))

    @classmethod
    def only(cls, person: str) -> "Audience":
        """Visible to exactly one person."""
        person = person.strip()
        if not person:
            raise CirclesError("Audience.only needs a person")
        return cls(people=[person], label=f"only {person}")

    @classmethod
    def to_all(cls) -> "Audience":
        """Visible to everyone known to the circles graph."""
        return cls(all_=True, label="to everyone")

    @classmethod
    def me(cls) -> "Audience":
        """Private to the owner."""
        return cls(circles=[_PRIVATE_CIRCLE], label="just me")

    @classmethod
    def default_for(cls, graph: Circles) -> "Audience":
        """The default-first question answered: who is this for, by default."""
        return cls(circles=[graph.default_circle()], label="default")

    def combine(self, other: "Audience") -> "Audience":
        """Union of two audiences: to(c1) + to(c2)."""
        return Audience(
            circles=self._circles | other._circles,
            people=self._people | other._people,
            excludes=self._excludes | other._excludes,
            all_=self._all or other._all,
            label=f"({self._label}) + ({other._label})",
        )

    def exclude(self, *people: str) -> "Audience":
        """Everyone in the audience except these people: to(c) - person."""
        dropped = [p.strip() for p in people if p.strip()]
        if not dropped:
            raise CirclesError("Audience.exclude needs at least one person")
        return Audience(
            circles=self._circles,
            people=self._people,
            excludes=self._excludes | frozenset(dropped),
            all_=self._all,
            label=f"({self._label}) except {', '.join(dropped)}",
        )

    # -- resolution --------------------------------------------------------

    def resolve(self, graph: Circles) -> FrozenSet[str]:
        """The exact set of people who should see the item. Pure set math."""
        if self._all:
            viewers = set(graph.everyone())
        else:
            viewers = set(self._people)
            for name in self._circles:
                viewers.update(graph.members(name))
        viewers -= self._excludes
        return frozenset(viewers)

    def visible_to(self, viewer: str, graph: Circles) -> bool:
        return viewer.strip() in self.resolve(graph)

    def explain(self, graph: Circles) -> str:
        """Render the audience back into human grammar for audit."""
        viewers = sorted(self.resolve(graph))
        base = self._label or "custom"
        if not viewers:
            return f"{base} -> nobody"
        return f"{base} -> {', '.join(viewers)}"

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Audience({self._label!r})"
