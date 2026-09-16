"""Portable communities — data model, export, and verifying import.

Export format ``levi-community-export/1`` (open, documented, no lock-in):

.. code-block:: json

    {
      "format": "levi-community-export",
      "format_version": 1,
      "exported_at": "...",
      "community": { "id": ..., "name": ..., "created_at": ... },
      "sections": {
        "channels":  [...],
        "members":   [...],
        "roles":     [...],
        "messages":  [...],
        "governance": {...}
      },
      "checksums": { "<section>": "<sha256 of canonical section JSON>" },
      "manifest": "<sha256 over the sorted checksums>"
    }

Import recomputes every section checksum and the manifest, and REFUSES
the file on any mismatch — integrity is verified, not assumed. A
community that can leave is a community the platform must serve.

Governance is a thin reference here: the full versioned governance
document lives in ``levi.charters`` (B9); the community stores a
``charter_ref`` plus a local rules snapshot so the export is
self-contained even without the charter package.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

EXPORT_FORMAT = "levi-community-export"
EXPORT_VERSION = 1
_SECTIONS = ("channels", "members", "roles", "messages", "governance")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def _home() -> Path:
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override)
    return Path.home() / ".levi"


def _community_dir(community_id: str) -> Path:
    return _home() / "communities" / community_id


def _check_id(value: str, what: str) -> str:
    value = value.strip()
    if not _ID_RE.match(value):
        raise CommunityError(
            f"{what} id must match [A-Za-z0-9_-]{{1,64}}, got {value!r}")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommunityError(ValueError):
    """Invalid community operation or corrupt export."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Channel:
    id: str
    name: str
    kind: str = "text"  # text | voice-note | forum | announcements
    topic: str = ""


@dataclass
class Member:
    id: str
    name: str
    joined_at: str = field(default_factory=_now)


@dataclass
class Role:
    id: str
    name: str
    permissions: List[str] = field(default_factory=list)  # e.g. post, moderate, manage-roles
    member_ids: List[str] = field(default_factory=list)


@dataclass
class Message:
    id: str
    channel_id: str
    author_id: str
    text: str
    timestamp: str = field(default_factory=_now)
    edited: bool = False


@dataclass
class Governance:
    rules: List[str] = field(default_factory=list)
    moderators: List[str] = field(default_factory=list)  # member ids
    charter_ref: Optional[Dict[str, str]] = None  # {id, version, checksum} — see levi.charters


@dataclass
class Community:
    id: str
    name: str
    created_at: str = field(default_factory=_now)
    channels: List[Channel] = field(default_factory=list)
    members: List[Member] = field(default_factory=list)
    roles: List[Role] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    governance: Governance = field(default_factory=Governance)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Community":
        gov = raw.get("governance") or {}
        return cls(
            id=raw["id"], name=raw["name"], created_at=raw.get("created_at", _now()),
            channels=[Channel(**c) for c in raw.get("channels", [])],
            members=[Member(**m) for m in raw.get("members", [])],
            roles=[Role(**r) for r in raw.get("roles", [])],
            messages=[Message(**m) for m in raw.get("messages", [])],
            governance=Governance(
                rules=list(gov.get("rules", [])),
                moderators=list(gov.get("moderators", [])),
                charter_ref=gov.get("charter_ref"),
            ),
        )


# ---------------------------------------------------------------------------
# Checksummed export / verifying import
# ---------------------------------------------------------------------------

def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_export(community: Community) -> Dict[str, Any]:
    """Build the export document with per-section checksums + manifest."""
    sections = {
        "channels": [asdict(c) for c in community.channels],
        "members": [asdict(m) for m in community.members],
        "roles": [asdict(r) for r in community.roles],
        "messages": [asdict(m) for m in community.messages],
        "governance": asdict(community.governance),
    }
    checksums = {name: _sha256(_canonical(sections[name])) for name in _SECTIONS}
    manifest = _sha256(_canonical(checksums))
    return {
        "format": EXPORT_FORMAT,
        "format_version": EXPORT_VERSION,
        "exported_at": _now(),
        "community": {"id": community.id, "name": community.name,
                      "created_at": community.created_at},
        "sections": sections,
        "checksums": checksums,
        "manifest": manifest,
    }


def verify_export(doc: Dict[str, Any]) -> Community:
    """Verify every checksum and the manifest; return the Community.

    Raises CommunityError on ANY mismatch — a tampered or corrupt export
    is refused, never silently accepted.
    """
    if doc.get("format") != EXPORT_FORMAT:
        raise CommunityError(
            f"not a LEVI community export (format={doc.get('format')!r})")
    if doc.get("format_version") != EXPORT_VERSION:
        raise CommunityError(
            f"unsupported export version {doc.get('format_version')!r}")
    sections = doc.get("sections")
    checksums = doc.get("checksums")
    if not isinstance(sections, dict) or not isinstance(checksums, dict):
        raise CommunityError("export is missing sections/checksums")
    for name in _SECTIONS:
        if name not in sections:
            raise CommunityError(f"export is missing section {name!r}")
        expected = checksums.get(name)
        actual = _sha256(_canonical(sections[name]))
        if expected != actual:
            raise CommunityError(
                f"checksum mismatch in section {name!r}: export is corrupt or tampered")
    if doc.get("manifest") != _sha256(_canonical(checksums)):
        raise CommunityError("manifest mismatch: checksum table was altered")
    meta = doc.get("community", {})
    raw = {"id": meta.get("id", ""), "name": meta.get("name", ""),
           "created_at": meta.get("created_at", _now()), **sections}
    community = Community.from_dict(raw)
    _check_id(community.id, "community")
    return community


# ---------------------------------------------------------------------------
# Local store
# ---------------------------------------------------------------------------

class CommunityStore:
    """Own your communities locally. One directory per community."""

    def __init__(self, base: Optional[Path] = None) -> None:
        self._base = base or (_home() / "communities")
        self._cache: Dict[str, Community] = {}

    def _path(self, community_id: str) -> Path:
        return self._base / _check_id(community_id, "community") / "community.json"

    def _write(self, community: Community) -> None:
        p = self._path(community.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(community.to_dict(), indent=2, sort_keys=True))
        tmp.replace(p)
        self._cache[community.id] = community

    def create(self, community_id: str, name: str) -> Community:
        community_id = _check_id(community_id, "community")
        name = name.strip()
        if not name:
            raise CommunityError("community name must be non-empty")
        if self._path(community_id).exists():
            raise CommunityError(f"community {community_id!r} already exists")
        community = Community(id=community_id, name=name)
        self._write(community)
        return community

    def get(self, community_id: str) -> Community:
        community_id = _check_id(community_id, "community")
        if community_id in self._cache:
            return self._cache[community_id]
        p = self._path(community_id)
        if not p.exists():
            raise CommunityError(f"unknown community {community_id!r}")
        community = Community.from_dict(json.loads(p.read_text()))
        self._cache[community_id] = community
        return community

    def list(self) -> List[Community]:
        if not self._base.exists():
            return []
        return [self.get(d.name) for d in sorted(self._base.iterdir()) if d.is_dir()]

    # -- mutation helpers -------------------------------------------------
    def add_channel(self, community_id: str, channel_id: str, name: str,
                    kind: str = "text", topic: str = "") -> Channel:
        c = self.get(community_id)
        channel_id = _check_id(channel_id, "channel")
        if any(ch.id == channel_id for ch in c.channels):
            raise CommunityError(f"channel {channel_id!r} already exists")
        ch = Channel(id=channel_id, name=name.strip() or channel_id, kind=kind, topic=topic)
        c.channels.append(ch)
        self._write(c)
        return ch

    def add_member(self, community_id: str, member_id: str, name: str) -> Member:
        c = self.get(community_id)
        member_id = _check_id(member_id, "member")
        if any(m.id == member_id for m in c.members):
            raise CommunityError(f"member {member_id!r} already exists")
        m = Member(id=member_id, name=name.strip() or member_id)
        c.members.append(m)
        self._write(c)
        return m

    def add_role(self, community_id: str, role_id: str, name: str,
                 permissions: Optional[List[str]] = None) -> Role:
        c = self.get(community_id)
        role_id = _check_id(role_id, "role")
        if any(r.id == role_id for r in c.roles):
            raise CommunityError(f"role {role_id!r} already exists")
        r = Role(id=role_id, name=name.strip() or role_id,
                 permissions=list(permissions or []))
        c.roles.append(r)
        self._write(c)
        return r

    def grant_role(self, community_id: str, role_id: str, member_id: str) -> None:
        c = self.get(community_id)
        role = next((r for r in c.roles if r.id == role_id), None)
        if role is None:
            raise CommunityError(f"unknown role {role_id!r}")
        if not any(m.id == member_id for m in c.members):
            raise CommunityError(f"unknown member {member_id!r}")
        if member_id not in role.member_ids:
            role.member_ids.append(member_id)
            self._write(c)

    def post(self, community_id: str, channel_id: str, author_id: str,
             text: str) -> Message:
        c = self.get(community_id)
        if not any(ch.id == channel_id for ch in c.channels):
            raise CommunityError(f"unknown channel {channel_id!r}")
        if not any(m.id == author_id for m in c.members):
            raise CommunityError(f"unknown member {author_id!r}")
        text = text.strip()
        if not text:
            raise CommunityError("message text must be non-empty")
        mid = _sha256(f"{community_id}|{channel_id}|{author_id}|{text}|{_now()}".encode())[:12]
        msg = Message(id=mid, channel_id=channel_id, author_id=author_id, text=text)
        c.messages.append(msg)
        self._write(c)
        return msg

    def set_rules(self, community_id: str, rules: List[str]) -> None:
        c = self.get(community_id)
        c.governance.rules = [r.strip() for r in rules if r.strip()]
        self._write(c)

    # -- portability ------------------------------------------------------
    def export(self, community_id: str, out_path: Path) -> Path:
        doc = build_export(self.get(community_id))
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True))
        tmp.replace(out_path)
        return out_path

    def import_community(self, in_path: Path, as_id: Optional[str] = None) -> Community:
        """Import a verified export. Fails closed on checksum mismatch."""
        try:
            doc = json.loads(Path(in_path).read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise CommunityError(f"cannot read export: {exc}")
        community = verify_export(doc)  # raises on any tampering
        if as_id:
            community.id = _check_id(as_id, "community")
        if self._path(community.id).exists():
            raise CommunityError(
                f"community {community.id!r} already exists locally; "
                "import refused rather than overwrite")
        self._write(community)
        return community

    def format_status(self, community_id: str) -> str:
        c = self.get(community_id)
        lines = [f"=== {c.name} [{c.id}] ===",
                 f"channels={len(c.channels)} members={len(c.members)} "
                 f"roles={len(c.roles)} messages={len(c.messages)}",
                 f"governance rules={len(c.governance.rules)} "
                 f"moderators={len(c.governance.moderators)}"]
        if c.governance.charter_ref:
            ref = c.governance.charter_ref
            lines.append(f"charter: {ref.get('id')} v{ref.get('version')} "
                         f"(checksum {str(ref.get('checksum'))[:12]}…)")
        lines.append("channels: " + (", ".join(f"#{ch.name}" for ch in c.channels) or "(none)"))
        return "\n".join(lines)
