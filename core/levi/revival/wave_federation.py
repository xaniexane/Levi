"""revival/wave_federation.py — operational transformation for co-editing.

Studied from: dead-networks-20260916 (report.md [Google Wave]).

Revival of: the Wave federation protocol's two load-bearing ideas —
Operational Transformation (OT) for real-time co-editing over slow,
unreliable links, and the document-as-conversation object (blips threaded
into a wave).

Why it matters: when two people type at the same time on a bad link, their
edits collide. OT resolves the collision mathematically: each site
transforms the remote operation against its own concurrent operations so
both replicas converge to the same text without a lock server. And treating
the document and the conversation as one object means discussion lives
where the work lives.

LEVI adaptation:
- ``Op``: insert / delete with (position, site id); serializes to a plain
  dict for the wire.
- ``transform(a, b)``: rewrite ``a`` so it applies cleanly after ``b``
  (the classic insert/insert, insert/delete, delete/delete cases).
- ``WaveDoc``: text plus an operation log with versions; ``apply_local()``
  records an op; ``integrate()`` transforms a remote op against every
  concurrent local op since the remote's base version, so replicas
  converge.
- ``Blip`` / ``Wave``: a blip is a document node; replies are child blips.
  The wave is one tree — document and conversation together.

Honest limits:
- OT here covers plain-text insert/delete only: no retain/attributes, no
  tombstone GC, no undo. Concurrent overlapping deletes resolve by
  position with a documented tie-break, not by user intent.
- ``integrate()`` assumes the remote op's base version is known and the
  log is complete; there is no catch-up or missing-op recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Op:
    """One edit: insert text at pos, or delete length chars at pos."""

    kind: str  # "insert" | "delete"
    pos: int
    text: str = ""  # for insert
    length: int = 0  # for delete
    site: str = ""
    base_version: int = 0

    def __post_init__(self) -> None:
        if self.kind not in ("insert", "delete"):
            raise ValueError(f"unknown op kind: {self.kind!r}")
        if self.pos < 0:
            raise ValueError("pos must be >= 0")
        if self.kind == "insert" and not self.text:
            raise ValueError("insert needs text")
        if self.kind == "delete" and self.length <= 0:
            raise ValueError("delete needs a positive length")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "pos": self.pos,
            "text": self.text,
            "length": self.length,
            "site": self.site,
            "base_version": self.base_version,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Op":
        return Op(
            kind=data["kind"],
            pos=data["pos"],
            text=data.get("text", ""),
            length=data.get("length", 0),
            site=data.get("site", ""),
            base_version=data.get("base_version", 0),
        )


def transform(a: Op, b: Op) -> Op:
    """Rewrite ``a`` so it applies correctly after ``b`` already applied.

    ``a`` is the operation being transformed; ``b`` is the concurrent
    operation it must be reconciled against. Returns a new Op.
    """
    pos = a.pos
    if a.kind == "insert" and b.kind == "insert":
        if b.pos < pos or (b.pos == pos and b.site < a.site):
            pos += len(b.text)
    elif a.kind == "insert" and b.kind == "delete":
        if b.pos < pos:
            pos -= min(b.length, pos - b.pos)
    elif a.kind == "delete" and b.kind == "insert":
        if b.pos <= pos:
            pos += len(b.text)
        elif b.pos < pos + a.length:
            # Insertion landed inside our delete range: the range grows.
            return Op(
                kind="delete",
                pos=pos,
                length=a.length + len(b.text),
                site=a.site,
                base_version=a.base_version,
            )
    elif a.kind == "delete" and b.kind == "delete":
        if b.pos < pos:
            pos -= min(b.length, pos - b.pos)
        elif b.pos < pos + a.length:
            # Overlapping deletes: shrink by the overlap.
            overlap = min(b.length, pos + a.length - b.pos)
            return Op(
                kind="delete",
                pos=pos,
                length=a.length - overlap,
                site=a.site,
                base_version=a.base_version,
            )
    return Op(
        kind=a.kind,
        pos=pos,
        text=a.text,
        length=a.length,
        site=a.site,
        base_version=a.base_version,
    )


class WaveDoc:
    """A convergent text document with an operation log."""

    def __init__(self, site: str, text: str = "") -> None:
        self.site = site
        self.text = text
        self.log: List[Op] = []
        self.version = 0

    def _apply(self, op: Op) -> None:
        if op.kind == "insert":
            pos = min(op.pos, len(self.text))
            self.text = self.text[:pos] + op.text + self.text[pos:]
        else:
            pos = min(op.pos, len(self.text))
            end = min(pos + op.length, len(self.text))
            self.text = self.text[:pos] + self.text[end:]

    def apply_local(self, op: Op) -> Op:
        """Apply a locally-authored op and log it."""
        op = Op(
            kind=op.kind,
            pos=op.pos,
            text=op.text,
            length=op.length,
            site=self.site,
            base_version=self.version,
        )
        self._apply(op)
        self.log.append(op)
        self.version += 1
        return op

    def integrate(self, remote: Op) -> Op:
        """Integrate a remote op: transform against concurrent local ops."""
        op = remote
        for local in self.log[remote.base_version :]:
            op = transform(op, local)
        self._apply(op)
        logged = Op(
            kind=op.kind,
            pos=op.pos,
            text=op.text,
            length=op.length,
            site=op.site,
            base_version=self.version,
        )
        self.log.append(logged)
        self.version += 1
        return logged


@dataclass
class Blip:
    """One document node in the conversation tree."""

    blip_id: str
    author: str
    doc: WaveDoc
    replies: List["Blip"] = field(default_factory=list)
    parent: Optional["Blip"] = field(default=None, repr=False)

    def reply(self, blip_id: str, author: str, text: str = "") -> "Blip":
        child = Blip(
            blip_id=blip_id,
            author=author,
            doc=WaveDoc(site=author, text=text),
            parent=self,
        )
        self.replies.append(child)
        return child


class Wave:
    """Document and conversation as one object: a tree of blips."""

    def __init__(self, wave_id: str) -> None:
        self.wave_id = wave_id
        self._blips: Dict[str, Blip] = {}
        self.root: Optional[Blip] = None

    def add_root(self, blip_id: str, author: str, text: str = "") -> Blip:
        if self.root is not None:
            raise ValueError("wave already has a root blip")
        blip = Blip(blip_id=blip_id, author=author, doc=WaveDoc(site=author, text=text))
        self.root = blip
        self._blips[blip_id] = blip
        return blip

    def add_reply(
        self, parent_id: str, blip_id: str, author: str, text: str = ""
    ) -> Blip:
        parent = self._blips[parent_id]
        if blip_id in self._blips:
            raise ValueError(f"duplicate blip id: {blip_id!r}")
        child = parent.reply(blip_id, author, text)
        self._blips[blip_id] = child
        return child

    def get(self, blip_id: str) -> Blip:
        return self._blips[blip_id]

    def thread(self, blip_id: str) -> List[str]:
        """Blip ids from the root down to the given blip."""
        blip = self._blips[blip_id]
        chain = []
        while blip is not None:
            chain.append(blip.blip_id)
            blip = blip.parent
        return list(reversed(chain))


ORIGIN = "levi-revival/wave-federation"
