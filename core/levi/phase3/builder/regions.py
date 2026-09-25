"""Regions, deltas, and schema+rung validation.

A Region is a world partition: ``{id, kind, schema, state, assets,
version, parent, builders}``. Assets are heavy local content
referenced by content hash — never pushed speculatively. A Delta is
``{region_id, base_version, ops, author}``: the only thing that
syncs.

``validate_addition()`` rejects schema-violating or rung-denied ops
*before* anything is applied. ``RungStub`` is the stand-in for the
middle team's rung protocol: deny-by-default — an op is approved only
when it carries an explicit ``rung: 0`` mark; anything unknown or
higher is denied.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ranks import Builder, has_capability

__all__ = [
    "Region",
    "Delta",
    "RungStub",
    "new_region",
    "validate_addition",
    "attempt_build",
    "make_delta",
    "apply_delta",
    "payload_bytes",
]


@dataclass
class Region:
    """A world partition owned by builders."""

    id: str
    kind: str
    schema: Dict[str, Any]
    state: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    assets: Dict[str, str] = field(default_factory=dict)  # asset_id -> content hash
    version: int = 0
    parent: Optional[str] = None
    builders: List[str] = field(default_factory=list)

    def canonical_state(self) -> bytes:
        return json.dumps(self.state, sort_keys=True, separators=(",", ":")).encode()

    def state_bytes(self) -> int:
        return len(self.canonical_state())


@dataclass(frozen=True)
class Delta:
    """The only thing that syncs: ops since ``base_version``."""

    region_id: str
    base_version: int
    ops: tuple
    author: str

    def canonical(self) -> bytes:
        payload = {
            "region_id": self.region_id,
            "base_version": self.base_version,
            "ops": [dict(op) for op in self.ops],
            "author": self.author,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class RungStub:
    """Stand-in for the middle team's rung protocol.

    Deny-by-default: approve ONLY ops explicitly marked ``rung: 0``
    (the scan-mind's rung-0 safety semantics). Unknown or higher
    rungs are denied until the real protocol is pinned.
    """

    def check(self, op: Dict[str, Any]) -> bool:
        return op.get("rung") == 0


def new_region(
    region_id: str,
    kind: str,
    parent: Optional[str] = None,
) -> Region:
    schema = {
        "kind": kind,
        "entity_types": ("room", "door", "item", "npc"),
        "ops": ("add", "modify", "remove"),
        "max_prop_bytes": 512,
    }
    return Region(id=region_id, kind=kind, schema=schema, parent=parent)


def validate_addition(
    region: Region,
    op: Dict[str, Any],
    rung: RungStub,
) -> List[str]:
    """Validate an addition; returns a list of violations (empty = valid).

    Checks, in order: legal op kind, legal entity type, prop size
    budget, rung approval. Nothing is applied here.
    """
    violations: List[str] = []
    if op.get("kind") not in region.schema["ops"]:
        violations.append(f"illegal op kind: {op.get('kind')!r}")
    if op.get("entity_type") not in region.schema["entity_types"]:
        violations.append(f"illegal entity type: {op.get('entity_type')!r}")
    props = op.get("props", {})
    prop_bytes = len(json.dumps(props, sort_keys=True, separators=(",", ":")).encode())
    if prop_bytes > region.schema["max_prop_bytes"]:
        violations.append(f"props exceed budget: {prop_bytes} bytes")
    if not rung.check(op):
        violations.append("rung denied (deny-by-default)")
    return violations


def _apply_op(region: Region, op: Dict[str, Any]) -> None:
    eid = str(op["entity_id"])
    kind = op["kind"]
    if kind == "add":
        region.state[eid] = {
            "type": op["entity_type"],
            "props": dict(op.get("props", {})),
        }
    elif kind == "modify":
        if eid in region.state:
            region.state[eid]["props"].update(op.get("props", {}))
    elif kind == "remove":
        region.state.pop(eid, None)
    for asset_id, content_hash in op.get("asset_refs", {}).items():
        region.assets[asset_id] = content_hash


def make_delta(
    region: Region, ops: List[Dict[str, Any]], author: str, rung: RungStub
) -> Delta:
    """Validate every op pre-apply; raise on the first violation."""
    for op in ops:
        violations = validate_addition(region, op, rung)
        if violations:
            raise ValueError(f"delta rejected pre-apply: {violations}")
    return Delta(
        region_id=region.id,
        base_version=region.version,
        ops=tuple(dict(op) for op in ops),
        author=author,
    )


def apply_delta(region: Region, delta: Delta) -> None:
    """Apply a delta in order; base_version must match."""
    if delta.region_id != region.id:
        raise ValueError("delta for another region")
    if delta.base_version != region.version:
        raise ValueError(
            f"stale delta: base {delta.base_version} != region {region.version}"
        )
    for op in delta.ops:
        _apply_op(region, op)
    region.version += 1


def payload_bytes(delta: Delta) -> int:
    """Sync payload size: ops only, never the world."""
    return len(delta.canonical())


def attempt_build(
    builder: Builder,
    region: Region,
    ops: List[Dict[str, Any]],
    rung: RungStub,
) -> Dict[str, Any]:
    """Try to build: rank gate first, then schema+rung validation.

    Returns ``{"ok": True}`` when the delta was created and applied,
    ``{"ok": False, "reason": ...}`` on refusal — never a partial
    apply.
    """
    if not has_capability(builder, "build"):
        return {
            "ok": False,
            "reason": f"rank {builder.rank.name} lacks build capability",
        }
    if builder.agent_id not in region.builders and region.builders:
        return {"ok": False, "reason": "not a builder of this region"}
    try:
        delta = make_delta(region, ops, builder.agent_id, rung)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}
    apply_delta(region, delta)
    builder.contributions += len(ops)
    return {"ok": True, "delta_bytes": payload_bytes(delta)}
