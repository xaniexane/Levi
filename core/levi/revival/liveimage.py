"""LEVI's live image — the organism that survives its own shutdown.

Studied from: systems-internals survey (Smalltalk, live-image section).

The mechanism, functionally: every object LEVI creates *lives* in one
registry, keyed by identity. The registry can be frozen to bytes
(``snapshot``) and thawed back (``restore``) — the whole living state
round-trips, so a running system can be paused, stored, and resumed
whole. Objects stay inspectable while the image "runs": attribute
listing, identity, and liveness checks are first-class.

Honesty: single-process simulation of the image idea. There is no real
VM suspension here — "running" means the registry is active in this
process, and snapshot/restore is pickle of the registry. What transfers
is the discipline: identity-keyed live state with whole-image
persistence.
"""

from __future__ import annotations

import pickle
from typing import Any, Dict, Iterator, List, Optional

ORIGIN = "levi-revival/liveimage"


class ImageError(Exception):
    """Base failure for live-image operations."""


class LiveObject:
    """One living object in the image: an identity plus a bag of state."""

    def __init__(self, obj_id: int, kind: str, attrs: Optional[Dict[str, Any]] = None):
        object.__setattr__(self, "_id", obj_id)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_attrs", dict(attrs or {}))

    @property
    def obj_id(self) -> int:
        return self._id

    @property
    def kind(self) -> str:
        return self._kind

    def get(self, name: str, default: Any = None) -> Any:
        return self._attrs.get(name, default)

    def set(self, name: str, value: Any) -> None:
        self._attrs[name] = value

    def attributes(self) -> Dict[str, Any]:
        """Attribute listing — inspection while the image runs."""
        return dict(self._attrs)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"LiveObject(id={self._id}, kind={self._kind!r})"

    def __getstate__(self) -> Dict[str, Any]:
        return {"id": self._id, "kind": self._kind, "attrs": self._attrs}

    def __setstate__(self, state: Dict[str, Any]) -> None:
        object.__setattr__(self, "_id", state["id"])
        object.__setattr__(self, "_kind", state["kind"])
        object.__setattr__(self, "_attrs", state["attrs"])


class Image:
    """The live image: registry of every live object, freezable to bytes."""

    def __init__(self) -> None:
        self._registry: Dict[int, LiveObject] = {}
        self._next_id = 1
        self._running = True

    # -- creation ------------------------------------------------------
    def spawn(self, kind: str, **attrs: Any) -> LiveObject:
        """Create a live object; it is registered by id at birth."""
        obj = LiveObject(self._next_id, kind, attrs)
        self._registry[self._next_id] = obj
        self._next_id += 1
        return obj

    # -- inspection ----------------------------------------------------
    def lookup(self, obj_id: int) -> LiveObject:
        try:
            return self._registry[obj_id]
        except KeyError:
            raise ImageError(f"no live object with id {obj_id}") from None

    def __iter__(self) -> Iterator[LiveObject]:
        return iter(self._registry.values())

    def __len__(self) -> int:
        return len(self._registry)

    def kinds(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for obj in self._registry.values():
            counts[obj.kind] = counts.get(obj.kind, 0) + 1
        return counts

    def inspect(self, obj_id: int) -> Dict[str, Any]:
        """Full inspection of a live object while the image runs."""
        obj = self.lookup(obj_id)
        return {"id": obj.obj_id, "kind": obj.kind, "attributes": obj.attributes()}

    def is_running(self) -> bool:
        return self._running

    # -- persistence ---------------------------------------------------
    def snapshot(self) -> bytes:
        """Freeze the whole registry to bytes."""
        if not self._running:
            raise ImageError("cannot snapshot a halted image")
        payload = {
            "next_id": self._next_id,
            "objects": [obj.__getstate__() for obj in self._registry.values()],
        }
        return pickle.dumps(payload, protocol=4)

    @classmethod
    def restore(cls, data: bytes) -> "Image":
        """Thaw a snapshot back into a live registry."""
        try:
            payload = pickle.loads(data)  # noqa: S301 - our own snapshots
        except Exception as exc:
            raise ImageError(f"corrupt snapshot: {exc}") from exc
        if not isinstance(payload, dict) or "objects" not in payload:
            raise ImageError("not a live-image snapshot")
        image = cls()
        image._next_id = int(payload.get("next_id", 1))
        for state in payload["objects"]:
            obj = LiveObject.__new__(LiveObject)
            obj.__setstate__(state)
            image._registry[obj.obj_id] = obj
        return image

    def halt(self) -> List[int]:
        """Stop the image; returns the ids that were alive."""
        self._running = False
        return sorted(self._registry.keys())
