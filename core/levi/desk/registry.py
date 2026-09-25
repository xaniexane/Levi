"""The tile protocol: a small self-describing card the user arranges.

A tile is:

    name           1-40 chars, [A-Za-z0-9_-], unique in the registry
    title          human label
    description    what it shows, one line
    render(ctx)    (dict prefs) -> list of text lines
    refresh        advisory only: 'on-render' | 'manual' (no daemons here)

Deny-closed: duplicate names refused, bad names refused, non-callable
render refused. Nothing is half-registered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class TileError(ValueError):
    """A tile or registry operation was refused."""


@dataclass
class Tile:
    name: str
    title: str
    description: str
    render: Callable[[Dict], List[str]]
    refresh: str = "on-render"
    default_prefs: Dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise TileError("bad tile name: %r" % (self.name,))
        if not self.title or not self.title.strip():
            raise TileError("tile %r: title is required" % (self.name,))
        if not callable(self.render):
            raise TileError("tile %r: render must be callable" % (self.name,))
        if self.refresh not in ("on-render", "manual"):
            raise TileError("tile %r: unknown refresh %r" % (self.name, self.refresh))


class TileRegistry:
    """Name -> Tile. Modules register their tiles here; the user arranges."""

    def __init__(self) -> None:
        self._tiles: Dict[str, Tile] = {}

    def register(self, tile: Tile) -> None:
        if tile.name in self._tiles:
            raise TileError("tile already registered: %r" % (tile.name,))
        self._tiles[tile.name] = tile

    def deregister(self, name: str) -> None:
        if name not in self._tiles:
            raise TileError("no such tile: %r" % (name,))
        del self._tiles[name]

    def get(self, name: str) -> Optional[Tile]:
        return self._tiles.get(name)

    def names(self) -> List[str]:
        return sorted(self._tiles)

    def describe(self) -> List[Dict]:
        return [
            {"name": t.name, "title": t.title, "description": t.description,
             "refresh": t.refresh}
            for t in (self._tiles[n] for n in self.names())
        ]


def register_builtin_tiles(registry: TileRegistry) -> None:
    """Ship three honest tiles over LEVI's own local stores."""
    import datetime
    from pathlib import Path

    def _home() -> Path:
        return Path.home() / ".levi"

    def _render_clock(prefs: Dict) -> List[str]:
        now = datetime.datetime.now().astimezone()
        fmt = prefs.get("format", "%a %Y-%m-%d %H:%M %Z")
        try:
            return [now.strftime(fmt)]
        except Exception:
            return [now.isoformat(timespec="minutes")]

    def _render_archive(prefs: Dict) -> List[str]:
        try:
            from levi.archive.store import ArchiveStore
        except Exception:
            return ["unavailable (archive store not importable)"]
        try:
            store = ArchiveStore(home=_home() / "archive")
            return ["%d records archived" % store.count()]
        except Exception as exc:
            return ["unavailable (%s)" % exc.__class__.__name__]

    def _render_growth(prefs: Dict) -> List[str]:
        journal = _home() / "growth" / "journal.jsonl"
        if not journal.exists():
            return ["not-initialized (no growth journal yet)"]
        try:
            with open(journal, "r", encoding="utf-8") as fh:
                n = sum(1 for line in fh if line.strip())
            return ["%d journal entries" % n]
        except Exception as exc:
            return ["unavailable (%s)" % exc.__class__.__name__]

    registry.register(Tile(
        name="clock", title="Clock",
        description="Local time, in your own format.",
        render=_render_clock, default_prefs={"format": "%a %Y-%m-%d %H:%M %Z"},
    ))
    registry.register(Tile(
        name="archive", title="Archive",
        description="How many records the Archive holds.",
        render=_render_archive,
    ))
    registry.register(Tile(
        name="growth", title="Growth journal",
        description="How many entries baby Levi has journaled.",
        render=_render_growth,
    ))
