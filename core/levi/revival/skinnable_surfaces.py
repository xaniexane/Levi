"""Skinnable surfaces and user-owned broadcasting.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #13)

Two mechanisms in one module:

1. **Skinnable surfaces.** A surface is a named UI region described by a
   *skin manifest*: colors, glyphs, and per-component overrides. Surfaces
   accept *plugins* — small handlers registered against named hooks
   (e.g. ``on_tick``, ``on_select``) — so the user extends behavior
   without forking the surface.

2. **User as station.** A *broadcast channel* is the user's own station:
   a playlist queue they program, a schedule note, and a listener count
   they can see. It is metadata about a broadcast the user runs —
   this module does not touch the network, encode audio, or stream.

Honest limit: plugins are plain Python callables invoked synchronously
by the surface; skins are data. No audio, no sockets, no rendering.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/skinnable-surfaces"


# ------------------------------------------------------------------
# Part 1: skinnable surfaces
# ------------------------------------------------------------------


@dataclass
class SkinManifest:
    """Declarative look for a surface: colors, glyphs, component overrides."""

    name: str
    colors: Dict[str, str] = field(default_factory=dict)
    glyphs: Dict[str, str] = field(default_factory=dict)
    components: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def color(self, key: str, default: str = "") -> str:
        return self.colors.get(key, default)

    def glyph(self, key: str, default: str = "?") -> str:
        return self.glyphs.get(key, default)

    def component(self, name: str) -> Dict[str, str]:
        return dict(self.components.get(name, {}))


@dataclass
class Plugin:
    """A user-supplied handler for one hook on a surface."""

    name: str
    hook: str
    handler: Callable[["Surface", Dict[str, Any]], Optional[str]]


@dataclass
class Surface:
    """A skinnable, plugin-extensible surface."""

    name: str
    skin: SkinManifest = field(default_factory=lambda: SkinManifest(name="default"))
    plugins: List[Plugin] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)

    def reskin(self, skin: SkinManifest) -> None:
        if not skin.name:
            raise ValueError("skin must be named")
        self.skin = skin

    def install(
        self,
        name: str,
        hook: str,
        handler: Callable[["Surface", Dict[str, Any]], Optional[str]],
    ) -> Plugin:
        """Register a plugin handler against a hook."""
        name = (name or "").strip()
        hook = (hook or "").strip()
        if not name or not hook:
            raise ValueError("plugin name and hook must be non-empty")
        if not callable(handler):
            raise ValueError("handler must be callable")
        if any(p.name == name for p in self.plugins):
            raise ValueError(f"plugin already installed: {name!r}")
        plugin = Plugin(name=name, hook=hook, handler=handler)
        self.plugins.append(plugin)
        return plugin

    def uninstall(self, name: str) -> Plugin:
        for i, p in enumerate(self.plugins):
            if p.name == name:
                return self.plugins.pop(i)
        raise KeyError(f"no such plugin: {name!r}")

    def fire(self, hook: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Run every plugin registered for ``hook``; collect their outputs."""
        outputs: List[str] = []
        for plugin in self.plugins:
            if plugin.hook == hook:
                result = plugin.handler(self, dict(context or {}))
                if result is not None:
                    outputs.append(str(result))
        return outputs


def make_surface(name: str) -> Surface:
    """Create a bare surface ready to be skinned and extended."""
    if not name or not name.strip():
        raise ValueError("surface name must be non-empty")
    return Surface(name=name.strip())


# ------------------------------------------------------------------
# Part 2: the user as station
# ------------------------------------------------------------------


@dataclass
class BroadcastChannel:
    """The user's own station: they program the queue, own the schedule."""

    owner: str
    station_name: str
    queue: List[str] = field(default_factory=list)  # track titles
    now_playing: Optional[str] = None
    listeners: int = 0
    schedule_note: str = ""

    def enqueue(self, track: str) -> int:
        track = (track or "").strip()
        if not track:
            raise ValueError("track must be non-empty")
        self.queue.append(track)
        return len(self.queue)

    def dequeue(self, track: str) -> None:
        if track not in self.queue:
            raise KeyError(f"not in queue: {track!r}")
        self.queue.remove(track)

    def go_live(self) -> str:
        """Advance the queue: the next track starts playing."""
        if not self.queue:
            raise ValueError("queue is empty — nothing to play")
        self.now_playing = self.queue.pop(0)
        return self.now_playing

    def tune_in(self) -> int:
        self.listeners += 1
        return self.listeners

    def tune_out(self) -> int:
        self.listeners = max(0, self.listeners - 1)
        return self.listeners

    def set_schedule(self, note: str) -> None:
        self.schedule_note = (note or "").strip()

    def status_line(self) -> str:
        playing = self.now_playing or "(off air)"
        return (
            f"{self.station_name} by {self.owner} — {playing}, "
            f"{self.listeners} listener(s), {len(self.queue)} queued"
        )


def open_station(owner: str, station_name: str) -> BroadcastChannel:
    """Open a broadcast channel: the user becomes a station."""
    if not owner or not owner.strip():
        raise ValueError("owner must be non-empty")
    if not station_name or not station_name.strip():
        raise ValueError("station name must be non-empty")
    return BroadcastChannel(owner=owner.strip(), station_name=station_name.strip())
