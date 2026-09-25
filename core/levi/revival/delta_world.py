"""Delta-sync virtual world: heavy assets live locally, the link carries deltas.

Studied from: dead-networks-20260916 / report.md [Quantum Link / Q-Link]
(first large-scale graphical virtual world: all graphics stored locally, the
network carries only state deltas — positions, object IDs — a graphical MMO
at 300 baud).

This is an original, from-scratch implementation for LEVI. The world is split
into two halves the way the historical design split them:

- ``AssetCatalog`` — the bulky, unchanging part (sprites, room art, sounds).
  It lives entirely on the client; nothing here ever crosses the link.
- ``WorldState`` + ``DeltaLink`` — the small, ever-changing part (who is
  where, which object is held, flag values). The link carries only compact
  ``DeltaOp`` records: (entity, field, value) triples, plus tombstones for
  despawns. Each client has a baseline snapshot; ``diff()`` emits only what
  changed since that client's baseline, so the wire stays tiny.

Public surface:
- ``AssetCatalog``: ``add(asset_id, blob)``, ``get(asset_id)``,
  ``has(asset_id)``, ``ids()``.
- ``WorldState``: ``spawn(entity_id, asset_id, **fields)``,
  ``set(entity_id, field, value)``, ``despawn(entity_id)``,
  ``state_of(entity_id)``, ``entities()``.
- ``DeltaLink``: ``new_client()`` -> client id, ``diff(client_id)``,
  ``apply(ops)`` to a *remote-side* WorldState, ``baseline_bytes()``.
- ``DeltaOp``: frozen dataclass ``(entity, field, value)``; ``field=None``
  is a despawn tombstone.
- ``WorldError`` for violations (unknown asset, unknown entity, ...).

Honest limits: assets are opaque byte blobs — there is no renderer; "local
graphics" is modeled as local bytes. The link is simulated in-process: no
sockets, no real 300-baud timing, and delivery is assumed reliable and
ordered. Delta diffing is per-client baseline compare; conflicts between two
writers are last-write-wins with no merge.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


ORIGIN = "levi-revival/delta_world"


class WorldError(ValueError):
    """Raised when world rules are violated."""


@dataclass(frozen=True)
class DeltaOp:
    """One state change for the wire: entity, field, new value.

    ``field=None`` is a tombstone: the entity was despawned.
    """

    entity: str
    field: Optional[str]
    value: Any


class AssetCatalog:
    """Local-only asset store. Nothing here ever crosses the link."""

    def __init__(self) -> None:
        self._assets: Dict[str, bytes] = {}

    def add(self, asset_id: str, blob: bytes) -> None:
        """Store a local asset blob under ``asset_id``."""
        if not asset_id:
            raise WorldError("asset_id must be non-empty")
        if not isinstance(blob, (bytes, bytearray)):
            raise WorldError("asset blob must be bytes")
        self._assets[asset_id] = bytes(blob)

    def get(self, asset_id: str) -> bytes:
        """Fetch a local asset; KeyError-free — raises WorldError if missing."""
        try:
            return self._assets[asset_id]
        except KeyError:
            raise WorldError(f"unknown asset: {asset_id!r}") from None

    def has(self, asset_id: str) -> bool:
        return asset_id in self._assets

    def ids(self) -> List[str]:
        return sorted(self._assets)

    def total_bytes(self) -> int:
        """Local storage footprint — never sent over the link."""
        return sum(len(b) for b in self._assets.values())


class WorldState:
    """The shared mutable part of the world: entities with field bags.

    Entities reference assets by id, so state records stay small while the
    bulky art lives in the ``AssetCatalog``.
    """

    def __init__(self, catalog: AssetCatalog) -> None:
        self._catalog = catalog
        self._entities: Dict[str, Dict[str, Any]] = {}

    def spawn(self, entity_id: str, asset_id: str, **fields: Any) -> None:
        """Introduce an entity rendered with a catalog asset."""
        if entity_id in self._entities:
            raise WorldError(f"entity already exists: {entity_id!r}")
        if not self._catalog.has(asset_id):
            raise WorldError(f"unknown asset: {asset_id!r}")
        self._entities[entity_id] = {"_asset": asset_id, **fields}

    def set(self, entity_id: str, field: str, value: Any) -> None:
        """Change one field of one entity."""
        if entity_id not in self._entities:
            raise WorldError(f"unknown entity: {entity_id!r}")
        if field == "_asset":
            raise WorldError("use respawn to change an entity's asset")
        self._entities[entity_id][field] = value

    def despawn(self, entity_id: str) -> None:
        """Remove an entity from the world."""
        if entity_id not in self._entities:
            raise WorldError(f"unknown entity: {entity_id!r}")
        del self._entities[entity_id]

    def state_of(self, entity_id: str) -> Dict[str, Any]:
        """A copy of one entity's full state."""
        try:
            return dict(self._entities[entity_id])
        except KeyError:
            raise WorldError(f"unknown entity: {entity_id!r}") from None

    def entities(self) -> List[str]:
        return sorted(self._entities)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Deep-enough copy of the whole world for baseline diffing."""
        return {eid: dict(fields) for eid, fields in self._entities.items()}


class DeltaLink:
    """Per-client delta encoder over a ``WorldState``.

    Each client id gets a baseline snapshot. ``diff(client_id)`` compares the
    live world against that baseline and returns only the changed ops, then
    advances the baseline. A client that never changes receives an empty
    diff — the whole bandwidth trick.
    """

    def __init__(self, world: WorldState) -> None:
        self._world = world
        self._baselines: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._next_client = 0

    def new_client(self) -> str:
        """Register a client; its baseline starts at the current world."""
        client_id = f"client-{self._next_client}"
        self._next_client += 1
        self._baselines[client_id] = self._world.snapshot()
        return client_id

    def diff(self, client_id: str) -> List[DeltaOp]:
        """Compact ops for everything changed since this client's baseline."""
        if client_id not in self._baselines:
            raise WorldError(f"unknown client: {client_id!r}")
        baseline = self._baselines[client_id]
        current = self._world.snapshot()
        ops: List[DeltaOp] = []
        for eid, fields in current.items():
            old = baseline.get(eid)
            if old is None:
                # New entity: one op per field so clients can rebuild it.
                ops.extend(DeltaOp(eid, f, v) for f, v in fields.items())
            else:
                for f, v in fields.items():
                    if old.get(f, _MISSING) != v:
                        ops.append(DeltaOp(eid, f, v))
        for eid in baseline:
            if eid not in current:
                ops.append(DeltaOp(eid, None, None))  # tombstone
        self._baselines[client_id] = current
        return ops

    def diff_bytes(self, ops: List[DeltaOp]) -> int:
        """Honest wire-size estimate of a diff, in bytes."""
        return sum(len(repr(op).encode("utf-8")) for op in ops)

    @staticmethod
    def apply(world: WorldState, ops: List[DeltaOp]) -> None:
        """Apply received ops to a *remote-side* WorldState, in order.

        New entities are spawned from field ops (``_asset`` arrives as a
        regular field); tombstones despawn. Missing entities for plain field
        sets are created field-by-field so out-of-order first contact still
        converges on the next diff.
        """
        pending: Dict[str, Dict[str, Any]] = {}
        for op in ops:
            if op.field is None:
                if op.entity in world.entities():
                    world.despawn(op.entity)
                pending.pop(op.entity, None)
                continue
            if op.entity not in world.entities():
                if op.field == "_asset":
                    world.spawn(op.entity, op.value)
                    for f, v in pending.pop(op.entity, {}).items():
                        world.set(op.entity, f, v)
                else:
                    # Asset identity not seen yet: hold the field until it
                    # arrives so first contact converges regardless of order.
                    pending.setdefault(op.entity, {})[op.field] = op.value
                continue
            if op.field == "_asset":
                continue  # asset is fixed at spawn; ignore re-assertions
            world.set(op.entity, op.field, op.value)


_MISSING = object()
