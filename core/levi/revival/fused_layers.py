"""Layered annotation fused into one immutable pane.

Studied from: lost-crafts-20260916/report.md [Batch 4] (Grisaille)

The studied shape: grisaille is monochrome painting built as layered
glazes — the raw pane stays visible through everything laid over it,
and once a layer fuses it is never edited in place.

LEVI-native re-expression: an append-only layered document. A base pane
(the raw harvest, kept exactly as found) carries stacked annotation
layers. Each new layer is *fused* by hashing its content together with
the hash of the layer beneath it, so the whole stack is a tamper-evident
chain. Nothing is ever edited in place: correcting a layer means
adding a new layer on top that supersedes it.

Operations:

* ``seal(base)`` — freeze the raw pane
* ``add_layer(note, author)`` — fuse a new annotation layer on top
* ``render(depth=None)`` — the pane with all layers (or up to depth)
  flattened, raw first, newest last
* ``supersede(layer, note, author)`` — explicitly mark an older layer
  as replaced, without touching it
* ``verify()`` — recompute the hash chain; True means no layer was
  altered since fusion

Honest limits: hash-chaining detects later tampering of the stored
layer objects; it cannot prove the original harvest was truthful.
Uses SHA-256 from the standard library.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


ORIGIN = "levi-revival/fused-layers"

_GENESIS = "GENESIS::grisaille-pane"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Layer:
    """One fused annotation layer. Immutable by convention: never edited."""

    index: int
    note: str
    author: str
    fused_at: str
    prev_hash: str
    self_hash: str = ""
    superseded_by: Optional[int] = None

    def __post_init__(self) -> None:
        payload = (
            f"{self.index}|{self.note}|{self.author}|{self.fused_at}|{self.prev_hash}"
        )
        object.__setattr__(self, "self_hash", _hash(payload))

    def fingerprint(self) -> str:
        return self.self_hash[:12]


@dataclass
class Pane:
    """The sealed pane: raw base + fused layers, newest on top."""

    base: str
    base_hash: str = ""
    layers: List[Layer] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_hash", _hash(_GENESIS + "|" + self.base))

    @classmethod
    def seal(cls, base: str) -> "Pane":
        """Freeze the raw harvest as clear glass."""
        if not isinstance(base, str):
            raise ValueError("base must be a string")
        return cls(base=base)

    def _tip_hash(self) -> str:
        return self.layers[-1].self_hash if self.layers else self.base_hash

    # -- fusing -----------------------------------------------------------------
    def add_layer(self, note: str, author: str = "levi") -> Layer:
        """Fuse a new annotation layer. Never edits anything beneath."""
        if not note or not note.strip():
            raise ValueError("layer note must be non-empty")
        layer = Layer(
            index=len(self.layers),
            note=note,
            author=author,
            fused_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            prev_hash=self._tip_hash(),
        )
        self.layers.append(layer)
        return layer

    def supersede(self, index: int, note: str, author: str = "levi") -> Layer:
        """Replace the *effect* of a layer by fusing a correction on top.

        The old layer is marked superseded but its bytes are untouched —
        the history stays, the meaning moves forward.
        """
        if not (0 <= index < len(self.layers)):
            raise ValueError(f"no layer at index {index}")
        if self.layers[index].superseded_by is not None:
            raise ValueError(f"layer {index} already superseded")
        new_layer = self.add_layer(f"[supersedes L{index}] {note}", author)
        # record the link without rewriting the old layer object:
        self.layers[index].superseded_by = new_layer.index
        return new_layer

    # -- reading ------------------------------------------------------------------
    def render(self, depth: Optional[int] = None) -> str:
        """Flatten the pane: raw base first, then active layers in order.

        Superseded layers still render (history is honest) but are
        marked as such.
        """
        layers = self.layers if depth is None else self.layers[:depth]
        parts = [self.base]
        for lay in layers:
            tag = (
                f" [superseded by L{lay.superseded_by}]"
                if lay.superseded_by is not None
                else ""
            )
            parts.append(f"--- L{lay.index} ({lay.author}){tag} ---\n{lay.note}")
        return "\n".join(parts)

    def active_layers(self) -> List[Layer]:
        """Layers whose meaning is current (not superseded)."""
        return [lay for lay in self.layers if lay.superseded_by is None]

    # -- integrity ----------------------------------------------------------------
    def verify(self) -> bool:
        """Recompute the whole chain. True => nothing was altered in place."""
        prev = _hash(_GENESIS + "|" + self.base)
        for lay in self.layers:
            if lay.prev_hash != prev:
                return False
            expected = Layer(
                index=lay.index,
                note=lay.note,
                author=lay.author,
                fused_at=lay.fused_at,
                prev_hash=lay.prev_hash,
            ).self_hash
            if lay.self_hash != expected:
                return False
            prev = lay.self_hash
        return True
