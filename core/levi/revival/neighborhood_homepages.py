"""Neighborhood homepages: themed personal pages with webring discovery.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #12)

The mechanism: every user owns a *homepage* — a small themed page
(theme = a named look; sections = owned content blocks). Homepages live
inside *neighborhoods* (themed districts, e.g. "harbor" or "nocturne"),
and discovery happens through *webrings*: ordered rings of pages you
walk with ``next`` / ``prev`` links, like the old web. Rings are owned
by their members, not by an algorithm.

Honest limit: a homepage is data — theme name, sections, and ring
links. This module does not serve HTTP or render pages; it keeps the
registry, neighborhoods, and rings consistent.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/neighborhood-homepages"


@dataclass
class Homepage:
    """A user-owned personal page."""

    owner: str
    theme: str
    tagline: str = ""
    sections: Dict[str, str] = field(default_factory=dict)

    def add_section(self, name: str, body: str) -> None:
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("section name must be non-empty")
        self.sections[name] = body

    def remove_section(self, name: str) -> None:
        if name not in self.sections:
            raise KeyError(f"no such section: {name!r}")
        del self.sections[name]

    def retheme(self, theme: str) -> None:
        theme = (theme or "").strip()
        if not theme:
            raise ValueError("theme must be non-empty")
        self.theme = theme


@dataclass
class Neighborhood:
    """A themed district holding a set of homepages."""

    name: str
    motto: str = ""
    pages: Dict[str, Homepage] = field(default_factory=dict)

    def raise_page(self, owner: str, theme: str, tagline: str = "") -> Homepage:
        owner = (owner or "").strip()
        if not owner:
            raise ValueError("owner must be non-empty")
        if owner in self.pages:
            raise ValueError(f"{owner!r} already has a page here")
        page = Homepage(owner=owner, theme=theme, tagline=tagline)
        self.pages[owner] = page
        return page

    def tear_down(self, owner: str) -> Homepage:
        if owner not in self.pages:
            raise KeyError(f"no page for {owner!r}")
        return self.pages.pop(owner)

    def census(self) -> List[str]:
        return sorted(self.pages)


@dataclass
class Webring:
    """An ordered ring of homepages; walk it with next/prev."""

    name: str
    members: List[str] = field(default_factory=list)  # owner names, in ring order

    def join(self, owner: str) -> None:
        if owner in self.members:
            raise ValueError(f"already in ring: {owner!r}")
        self.members.append(owner)

    def leave(self, owner: str) -> None:
        if owner not in self.members:
            raise KeyError(f"not in ring: {owner!r}")
        self.members.remove(owner)

    def next(self, owner: str) -> str:
        """The page after ``owner`` in the ring (wraps around)."""
        idx = self._index(owner)
        return self.members[(idx + 1) % len(self.members)]

    def prev(self, owner: str) -> str:
        """The page before ``owner`` in the ring (wraps around)."""
        idx = self._index(owner)
        return self.members[(idx - 1) % len(self.members)]

    def _index(self, owner: str) -> int:
        if owner not in self.members:
            raise KeyError(f"not in ring: {owner!r}")
        if len(self.members) == 1:
            raise ValueError("a ring of one has no next or prev")
        return self.members.index(owner)


@dataclass
class Homestead:
    """The whole settled web: neighborhoods, pages, and rings."""

    neighborhoods: Dict[str, Neighborhood] = field(default_factory=dict)
    rings: Dict[str, Webring] = field(default_factory=dict)

    def found_neighborhood(self, name: str, motto: str = "") -> Neighborhood:
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("neighborhood name must be non-empty")
        if name in self.neighborhoods:
            raise ValueError(f"neighborhood already exists: {name!r}")
        hood = Neighborhood(name=name, motto=motto)
        self.neighborhoods[name] = hood
        return hood

    def start_ring(self, name: str) -> Webring:
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("ring name must be non-empty")
        if name in self.rings:
            raise ValueError(f"ring already exists: {name!r}")
        ring = Webring(name=name)
        self.rings[name] = ring
        return ring

    def find_page(self, owner: str) -> Optional[Homepage]:
        for hood in self.neighborhoods.values():
            if owner in hood.pages:
                return hood.pages[owner]
        return None


def settle() -> Homestead:
    """Create an empty homestead ready for neighborhoods and rings."""
    return Homestead()
