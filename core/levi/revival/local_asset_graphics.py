"""Graphics from local disks combined client-side: the wire never carries pixels.

Studied from: dead-networks-20260916/report.md [PlayNET]

The studied shape: game graphics were templates shipped on the
user's own disks — sprites, boards, tiles — and the network carried
only *thin state*: whose turn, which piece moved where. The client
combined its local assets with the thin state into the full picture.
Multiplayer turn-based games ran on a trickle of bytes.

LEVI-native re-expression: local-first scene composition. A
**TemplateStore** loads JSON scene templates from a local directory
(sprites referenced by content hash against a local **AssetVault**);
the **Composer** builds a frame from ``template + thin state``;
**diff/apply** produce minimal state updates; the **TurnProtocol**
wraps them in length-prefixed messages with sequence numbers for
turn-based play.

Operations:

* ``AssetVault.put_file/add_bytes`` — local assets keyed by hash
* ``TemplateStore.load_dir(path)`` — JSON templates from local disk
* ``compose(template, state, vault)`` → resolved frame (sprites
  inlined as hashes; missing assets flagged)
* ``diff(old_state, new_state)`` → list of ``(path, value)`` ops;
  ``apply(state, ops)`` → new state
* ``TurnProtocol.pack(seq, kind, payload)`` / ``unpack`` — wire messages

Honest limits: templates are declarative JSON the host defines —
this module ships no sprites and draws nothing. ``diff`` works on
flat ``path → value`` state; nested structure is the host's
convention. The protocol has no authentication or reliability of
its own; sequence numbers detect loss, they don't repair it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/local-asset-graphics"


def _hash(blob: bytes) -> str:
    return sha256(blob).hexdigest()[:16]


@dataclass
class AssetVault:
    """Local assets, keyed by content hash. Nothing here ever leaves the disk."""

    _store: Dict[str, bytes] = field(default_factory=dict)

    def add_bytes(self, blob: bytes) -> str:
        h = _hash(blob)
        self._store.setdefault(h, blob)
        return h

    def put_file(self, path: str) -> str:
        with open(path, "rb") as f:
            return self.add_bytes(f.read())

    def get(self, h: str) -> Optional[bytes]:
        return self._store.get(h)

    def has(self, h: str) -> bool:
        return h in self._store


@dataclass
class TemplateStore:
    """Scene templates loaded from the user's own disk.

    Template JSON shape::

        {"name": "...", "sprites": {"hero": "<hash>", ...},
         "layers": [{"sprite": "hero", "at": [x, y], "when": "state.flag"}, ...]}
    """

    templates: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def load_dir(self, path: str) -> List[str]:
        loaded: List[str] = []
        for name in sorted(os.listdir(path)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(path, name), encoding="utf-8") as f:
                tpl = json.load(f)
            self.templates[tpl.get("name", name[:-5])] = tpl
            loaded.append(tpl.get("name", name[:-5]))
        return loaded

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self.templates.get(name)


def compose(
    template: Dict[str, Any], state: Dict[str, Any], vault: AssetVault
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Build a frame: ``template + thin state`` → sprite placements.

    Returns (placements, missing_hashes). A placement is
    ``{"sprite": name, "hash": h, "at": [x, y]}``; layers whose
    ``when`` condition names a falsy/absent state key are skipped.
    """
    placements: List[Dict[str, Any]] = []
    missing: List[str] = []
    sprites: Dict[str, str] = template.get("sprites", {})
    for layer in template.get("layers", []):
        cond = layer.get("when")
        if cond and not state.get(cond):
            continue
        sprite = layer["sprite"]
        h = sprites.get(sprite, "")
        if h and not vault.has(h):
            missing.append(h)
            continue
        placements.append(
            {"sprite": sprite, "hash": h, "at": list(layer.get("at", [0, 0]))}
        )
    return placements, missing


def diff(old: Dict[str, Any], new: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Minimal update ops turning ``old`` state into ``new``.

    Each op is ``("set", "key", value-json)`` or ``("del", "key")``,
    with keys sorted for deterministic wire output.
    """
    ops: List[Tuple[str, str]] = []
    for key in sorted(set(old) | set(new)):
        if key not in new:
            ops.append(("del", key))
        elif key not in old or old[key] != new[key]:
            ops.append(("set", key, json.dumps(new[key], sort_keys=True)))
        # identical keys produce no op — the thin-state economy
    return ops


def apply(state: Dict[str, Any], ops: List[Tuple[str, str]]) -> Dict[str, Any]:
    """Apply ``diff`` ops to a copy of ``state``."""
    out = dict(state)
    for op in ops:
        if op[0] == "set":
            out[op[1]] = json.loads(op[2])
        elif op[0] == "del":
            out.pop(op[1], None)
    return out


class TurnProtocol:
    """Length-prefixed turn messages: ``SEQ|KIND|LEN|PAYLOAD``."""

    @staticmethod
    def pack(seq: int, kind: str, payload: str) -> bytes:
        body = payload.encode("utf-8")
        header = f"{seq}|{kind}|{len(body)}|".encode("utf-8")
        return header + body

    @staticmethod
    def unpack(msg: bytes) -> Tuple[int, str, str]:
        try:
            head, _, body = msg.partition(b"|")
            seq = int(head)
            kind_b, _, rest = body.partition(b"|")
            kind = kind_b.decode("utf-8")
            ln_b, _, payload_b = rest.partition(b"|")
            length = int(ln_b)
            payload = payload_b[:length].decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"malformed turn message: {e}") from e
        if len(payload_b) < length:
            raise ValueError("malformed turn message: truncated payload")
        return seq, kind, payload
