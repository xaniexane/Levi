"""LEVI's spatial memory palace: a route of ordered loci that hold facts as images.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #1)

The load-bearing mechanism of the old mnemonic art: bind what you want to
remember to places you already know. A ``Route`` is an ordered sequence of
loci (familiar waypoints — door, window, hearth, and so on). ``deposit``
binds a vivid image plus the plain fact to one locus. ``recall`` re-walks
the route in order and returns each fact. ``revisit`` refreshes a locus so
its contents don't decay.

Decay is honest: memories here are not eternal. Every deposited image has
a ``strength`` that falls with each walk it goes unrevisited; once it falls
below the threshold the locus reads as empty (``Forgotten``) until someone
deposits again. This makes the palace a working instrument — what you stop
walking, you lose.

Plain stdlib, no persistence magic: a ``Route`` serializes to a dict and
comes back via ``Route.from_dict``. LEVI's rules engine is the default,
and that's fine — the mechanism is the point, not the substrate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival/loci"

DECAY_PER_WALK = 0.85  # multiplicative decay each walk the locus is skipped
FORGET_THRESHOLD = 0.25  # below this the locus reads as empty


class Forgotten(Exception):
    """A locus whose image has decayed below the recall threshold."""


@dataclass
class Deposition:
    """One image+fact bound to one locus."""

    image: str
    fact: Any
    strength: float = 1.0
    deposited_at: float = field(default_factory=time.time)


@dataclass
class Locus:
    """A single waypoint on the route, optionally holding a deposition."""

    name: str
    description: str = ""
    contents: Optional[Deposition] = None

    def is_holding(self) -> bool:
        return self.contents is not None and self.contents.strength >= FORGET_THRESHOLD


class Route:
    """An ordered memory route: loci, deposition, re-traversal recall."""

    def __init__(self, name: str, loci: Optional[List[Locus]] = None):
        self.name = name
        self.loci: List[Locus] = loci if loci is not None else []
        self.walks = 0

    # -- route construction -------------------------------------------------
    def add_locus(self, name: str, description: str = "") -> Locus:
        locus = Locus(name=name, description=description)
        self.loci.append(locus)
        return locus

    # -- deposit ------------------------------------------------------------
    def deposit(self, locus_name: str, image: str, fact: Any) -> Deposition:
        locus = self._find(locus_name)
        deposition = Deposition(image=image, fact=fact)
        locus.contents = deposition
        return deposition

    # -- recall -------------------------------------------------------------
    def recall(self) -> List[tuple]:
        """Walk the route in order; return [(locus_name, fact), ...].

        Every locus NOT explicitly revisited decays one step this walk.
        Raises Forgotten nowhere — decayed loci are simply skipped; use
        ``recall_vivid`` for the strict variant.
        """
        self.walks += 1
        results = []
        for locus in self.loci:
            if locus.contents is None:
                continue
            locus.contents.strength *= DECAY_PER_WALK
            if locus.is_holding():
                results.append((locus.name, locus.contents.fact))
        return results

    def recall_vivid(self, locus_name: str) -> tuple:
        """Recall one locus strictly; raises Forgotten if it has decayed."""
        locus = self._find(locus_name)
        if not locus.is_holding():
            raise Forgotten(f"locus {locus_name!r}: image decayed below threshold")
        return locus.contents.image, locus.contents.fact

    def revisit(self, locus_name: str) -> None:
        """Refresh a locus: restore full strength (the anti-decay move)."""
        locus = self._find(locus_name)
        if locus.contents is not None:
            locus.contents.strength = 1.0

    def forgetting_loci(self) -> List[str]:
        """Names of loci whose strength has slipped below a healthy level."""
        return [
            locus.name
            for locus in self.loci
            if locus.contents is not None and not locus.is_holding()
        ]

    def strength(self, locus_name: str) -> Optional[float]:
        locus = self._find(locus_name)
        if locus.contents is None:
            return None
        return locus.contents.strength

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "walks": self.walks,
            "loci": [
                {
                    "name": locus.name,
                    "description": locus.description,
                    "contents": (
                        {
                            "image": locus.contents.image,
                            "fact": locus.contents.fact,
                            "strength": locus.contents.strength,
                            "deposited_at": locus.contents.deposited_at,
                        }
                        if locus.contents is not None
                        else None
                    ),
                }
                for locus in self.loci
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Route":
        route = cls(data["name"])
        route.walks = data.get("walks", 0)
        for entry in data["loci"]:
            locus = Locus(name=entry["name"], description=entry.get("description", ""))
            if entry.get("contents"):
                c = entry["contents"]
                locus.contents = Deposition(
                    image=c["image"],
                    fact=c["fact"],
                    strength=c.get("strength", 1.0),
                    deposited_at=c.get("deposited_at", time.time()),
                )
            route.loci.append(locus)
        return route

    # -- internals ----------------------------------------------------------
    def _find(self, locus_name: str) -> Locus:
        for locus in self.loci:
            if locus.name == locus_name:
                return locus
        raise KeyError(f"no locus named {locus_name!r} on route {self.name!r}")

    def __len__(self) -> int:
        return len(self.loci)
