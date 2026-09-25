"""Split-screen local multiplayer: N viewports on one shared state.

Origin: GoldenEye 007, Halo, Mario Kart — the 1990s-2000s console standard.
Multiple players, one screen, separate viewports, shared couch: the scene is
rendered N times from N cameras, with screen-space division. No accounts, no
servers, no latency — the cost was GPU budget per viewport, and the shared
physical presence was the social glue.

What it is in LEVI: ``SharedSession``. One shared state; N viewers, each with
a camera — a focus over the state (``None`` sees the whole scene). Each
viewport ``render``s its own slice of the SAME state object, so a mutation is
instantly visible in every viewport. There is no central coordinator beyond
the shared state itself.

Honesty label: USEFUL PATTERN — shared-state multi-view rendering is real;
the camera here is a key-focus filter, a deliberately small model of a
camera.

Deny-closed inputs: fewer than two viewers, empty viewer ids, duplicate
viewer ids, unknown viewer ids, empty state keys, mutating an unknown key,
and dropping below two viewers are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

__all__ = ["MIN_VIEWERS", "Viewer", "SharedSession"]

MIN_VIEWERS = 2


@dataclass
class Viewer:
    """One viewport: an id and a camera. ``focus=None`` sees the whole scene;
    otherwise the camera shows only the focused keys."""

    id: str
    focus: Optional[frozenset] = field(default=None)


class SharedSession:
    """N viewports, one shared state. No coordinator but the state itself."""

    def __init__(
        self, viewers: list[Viewer], initial_state: Optional[dict[str, Any]] = None
    ) -> None:
        if not isinstance(viewers, list) or len(viewers) < MIN_VIEWERS:
            raise ValueError(
                f"a split-screen session needs at least {MIN_VIEWERS} viewers"
            )
        self._viewers: dict[str, Viewer] = {}
        for viewer in viewers:
            self._add_viewer(viewer)
        self._state: dict[str, Any] = {}
        for key, value in (initial_state or {}).items():
            self.set(key, value)

    def _add_viewer(self, viewer: Viewer) -> None:
        if not isinstance(viewer, Viewer):
            raise ValueError(f"viewers must be Viewer instances, got {viewer!r}")
        if not isinstance(viewer.id, str) or not viewer.id.strip():
            raise ValueError("viewer id must be a non-empty string")
        vid = viewer.id.strip()
        if vid in self._viewers:
            raise ValueError(f"duplicate viewer id: {vid!r}")
        focus = viewer.focus
        if focus is not None:
            if isinstance(focus, (str, bytes)) or not isinstance(focus, Iterable):
                raise ValueError("viewer focus must be None or an iterable of keys")
            cleaned = set()
            for key in focus:
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("viewer focus keys must be non-empty strings")
                cleaned.add(key.strip())
            focus = frozenset(cleaned)
        self._viewers[vid] = Viewer(id=vid, focus=focus)

    def _require_viewer(self, viewer_id: str) -> Viewer:
        if not isinstance(viewer_id, str) or not viewer_id.strip():
            raise ValueError("viewer id must be a non-empty string")
        viewer = self._viewers.get(viewer_id.strip())
        if viewer is None:
            raise ValueError(f"unknown viewer: {viewer_id!r}")
        return viewer

    # -- the shared state -----------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Mutate the shared state. Every viewport sees it on next render."""
        if not isinstance(key, str) or not key.strip():
            raise ValueError("state key must be a non-empty string")
        self._state[key.strip()] = value

    def delete(self, key: str) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("state key must be a non-empty string")
        try:
            del self._state[key.strip()]
        except KeyError:
            raise ValueError(f"unknown state key: {key!r}") from None

    def snapshot(self) -> dict[str, Any]:
        """The whole shared state, as one dict."""
        return dict(self._state)

    # -- viewports ---------------------------------------------------------------
    def render(self, viewer_id: str) -> dict[str, Any]:
        """Render this viewport's slice of the shared state."""
        viewer = self._require_viewer(viewer_id)
        if viewer.focus is None:
            return dict(self._state)
        return {k: self._state[k] for k in viewer.focus if k in self._state}

    def add_viewer(self, viewer: Viewer) -> None:
        self._add_viewer(viewer)

    def remove_viewer(self, viewer_id: str) -> None:
        viewer = self._require_viewer(viewer_id)
        if len(self._viewers) - 1 < MIN_VIEWERS:
            raise ValueError(f"cannot drop below {MIN_VIEWERS} viewers in a session")
        del self._viewers[viewer.id]

    def viewer_ids(self) -> list[str]:
        return list(self._viewers)
