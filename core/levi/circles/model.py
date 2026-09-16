"""Circle store: Dunbar layers, hard caps, share receipts.

All state lives in one JSON document under ``~/.levi/circles/``.
Directory 0700, file 0600 — the circles are the keeper's private map,
never published.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import LAYERS, CircleError

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_CAPS = dict(LAYERS)

__all__ = [
    "LAYERS",
    "CircleError",
    "Member",
    "ShareReceipt",
    "CircleStore",
    "layer_names",
    "cap_for",
]


def layer_names() -> List[str]:
    return [name for name, _ in LAYERS]


def cap_for(layer: str) -> int:
    if layer not in _CAPS:
        raise CircleError(
            "unknown layer %r (layers: %s)" % (layer, ", ".join(layer_names()))
        )
    return _CAPS[layer]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Member:
    id: str
    name: str = ""
    layer: str = "friends"
    added_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Member":
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            layer=str(d.get("layer", "friends")),
            added_at=str(d.get("added_at", "")),
        )


@dataclass
class ShareReceipt:
    id: str
    title: str
    body: str
    layer: str
    member_ids: List[str]
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict:
        return asdict(self)


class CircleStore:
    """Owner-only Dunbar circle store with hard caps."""

    def __init__(self, home: Optional[Path] = None) -> None:
        base = Path(home) if home is not None else Path.home() / ".levi"
        self._dir = base / "circles"
        self._file = self._dir / "circles.json"
        self._members: Dict[str, Member] = {}
        self._shares: List[ShareReceipt] = []
        self._seq = 0
        self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self._file.is_file():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise CircleError("circles store unreadable: %s" % exc) from exc
        members = raw.get("members", {})
        if not isinstance(members, dict):
            raise CircleError("circles store corrupt: 'members' not an object")
        for md in members.values():
            if not isinstance(md, dict):
                continue
            try:
                m = Member.from_dict(md)
                if m.layer not in _CAPS:
                    continue
                self._members[m.id] = m
            except Exception:
                continue
        shares = raw.get("shares", [])
        if isinstance(shares, list):
            for sd in shares:
                if isinstance(sd, dict) and sd.get("id"):
                    self._shares.append(
                        ShareReceipt(
                            id=str(sd["id"]),
                            title=str(sd.get("title", "")),
                            body=str(sd.get("body", "")),
                            layer=str(sd.get("layer", "")),
                            member_ids=[str(x) for x in sd.get("member_ids", [])],
                            created_at=str(sd.get("created_at", "")),
                        )
                    )
        self._seq = int(raw.get("seq", 0) or 0)

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, 0o700)
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                {
                    "members": {m.id: m.to_dict() for m in self._members.values()},
                    "shares": [s.to_dict() for s in self._shares],
                    "seq": self._seq,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._file)
        os.chmod(self._file, 0o600)

    # -- membership ------------------------------------------------------
    def _check_id(self, member_id: str) -> None:
        if not _ID_RE.match(member_id or ""):
            raise CircleError(
                "bad member id %r (alphanumeric, dash/underscore, max 64)"
                % (member_id,)
            )

    def layer_count(self, layer: str) -> int:
        cap_for(layer)
        return sum(1 for m in self._members.values() if m.layer == layer)

    def add(self, member_id: str, name: str = "", layer: str = "friends") -> Member:
        self._check_id(member_id)
        cap = cap_for(layer)
        if member_id in self._members:
            raise CircleError("member %r already in circles" % member_id)
        used = self.layer_count(layer)
        if used >= cap:
            raise CircleError(
                "layer %r is FULL (%d/%d): the cap is the product — "
                "remove someone or choose another layer" % (layer, used, cap)
            )
        m = Member(id=member_id, name=name or member_id, layer=layer)
        self._members[member_id] = m
        self._save()
        return m

    def remove(self, member_id: str) -> None:
        if member_id not in self._members:
            raise CircleError("no such member %r" % member_id)
        del self._members[member_id]
        self._save()

    def move(self, member_id: str, layer: str) -> Member:
        cap = cap_for(layer)
        m = self._members.get(member_id)
        if m is None:
            raise CircleError("no such member %r" % member_id)
        if m.layer == layer:
            return m
        if self.layer_count(layer) >= cap:
            raise CircleError(
                "layer %r is FULL (%d/%d): move refused" % (layer, cap, cap)
            )
        m.layer = layer
        self._save()
        return m

    def members(self, layer: Optional[str] = None) -> List[Member]:
        if layer is not None:
            cap_for(layer)
            return sorted(
                (m for m in self._members.values() if m.layer == layer),
                key=lambda m: m.id,
            )
        return sorted(self._members.values(), key=lambda m: m.id)

    # -- audit: owner-only headroom --------------------------------------
    def audit(self) -> List[Dict]:
        """Per-layer cap headroom. Owner-only view; never published."""
        rows = []
        for name, cap in LAYERS:
            used = self.layer_count(name)
            rows.append(
                {
                    "layer": name,
                    "used": used,
                    "cap": cap,
                    "headroom": cap - used,
                    "full": used >= cap,
                }
            )
        return rows

    # -- sharing: circle-scoped receipts ---------------------------------
    def share(self, title: str, body: str, layer: str) -> ShareReceipt:
        cap_for(layer)
        title = (title or "").strip()
        if not title:
            raise CircleError("share needs a title")
        members = [m.id for m in self.members(layer)]
        self._seq += 1
        receipt = ShareReceipt(
            id="shr-%06d" % self._seq,
            title=title,
            body=body or "",
            layer=layer,
            member_ids=members,
        )
        self._shares.append(receipt)
        self._save()
        return receipt

    def shares(self, layer: Optional[str] = None) -> List[ShareReceipt]:
        if layer is not None:
            cap_for(layer)
            return [s for s in self._shares if s.layer == layer]
        return list(self._shares)
