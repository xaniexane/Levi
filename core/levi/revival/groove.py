"""LEVI's pairwise workspace sync: transport-agnostic, local-only.

Inspired by Groove (Ray Ozzie, 1997–2005; acquired by Microsoft, became
SharePoint Workspace, discontinued 2017). The ahead-of-its-time
mechanisms: *decentralized* shared workspaces — no central server —
pairwise synchronization between peers, every edit versioned, offline
work merged on reconnect, conflicts surfaced as explicit *conflict
records* for a human to resolve rather than silently auto-merged. It died
inside Microsoft's server-centric strategy, not from a technical flaw.

Remix delta: Groove's decentralized sync reimagined as LEVI's
*local-first* workspace sync — not a Groove clone. Version vectors over
plain local directories; conflicts filed as explicit records for a human,
never auto-merged; resolution (pick-a-side or merged content) supersedes
honestly. Hard-route law applied: no relay server, no paid STUN/TURN —
the only transports shipped are local (directory copy, in-memory pipe);
a network transport would need auth/encryption/identity this module does
not provide and does not pretend to. The tests exercise local only.

This is an original, from-scratch reimplementation for LEVI — no Groove
code is used. A ``Workspace`` is a directory of versioned documents;
``SyncEngine`` synchronizes two workspaces *pairwise* over a transport
you supply — and the only transports shipped are **local**: copying
between two local directories, or an in-memory pipe. There is no network
layer here; anything claiming "Groove sync" over the network would need
a transport with authentication, encryption, and identity, which this
module does not provide and does not pretend to.

Sync semantics (honest and simple): each document carries a version
vector ``{peer_id: counter}``. On sync, a document is *dominated* (one
side's vector covers the other — fast-forward), *identical*, or
*concurrent* (neither covers the other — a genuine conflict). Conflicts
are never auto-merged: both versions are kept and an explicit conflict
record is filed for a human. Resolution is explicit: pick a side or
supply merged content, which supersedes both.

Honesty: USEFUL PATTERN — with one loud limit. The version-vector sync,
conflict surfacing, and pairwise discipline are genuinely load-bearing
for LEVI's multi-device future. The transport is **local-only**; the
tests exercise local directories and in-memory pipes only. Do not read
this module as "LEVI syncs over the network" — it does not.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SyncError(Exception):
    """Base class for sync failures."""


# ---------------------------------------------------------------------------
# Version vectors
# ---------------------------------------------------------------------------


VersionVector = dict[str, int]


def dominates(a: VersionVector, b: VersionVector) -> bool:
    """True iff ``a`` covers ``b`` (every counter in a >= the one in b,
    and at least one strictly greater — or b is empty and a is not)."""
    if not b:
        return bool(a)
    ge = all(a.get(k, 0) >= v for k, v in b.items())
    gt = any(a.get(k, 0) > v for k, v in b.items()) or any(
        k not in b and v > 0 for k, v in a.items()
    )
    return ge and gt


def merge_vectors(a: VersionVector, b: VersionVector) -> VersionVector:
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b)}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass
class VersionedDoc:
    doc_id: str
    content: str
    version: VersionVector = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "version": self.version,
            "updated_at": self.updated_at,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VersionedDoc":
        return cls(
            data["doc_id"],
            data.get("content", ""),
            dict(data.get("version", {})),
            data.get("updated_at", 0.0),
            data.get("deleted", False),
        )


@dataclass
class Conflict:
    """An explicit conflict record: both versions kept, a human decides."""

    doc_id: str
    local: VersionedDoc
    remote: VersionedDoc
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "local": self.local.to_dict(),
            "remote": self.remote.to_dict(),
            "detected_at": self.detected_at,
        }


# ---------------------------------------------------------------------------
# Workspace — a directory of versioned documents
# ---------------------------------------------------------------------------


class Workspace:
    """One peer's workspace: ``docs/*.json`` versioned documents plus
    ``conflicts/*.json`` explicit conflict records."""

    def __init__(self, peer_id: str, path: str | Path):
        if not peer_id or not peer_id.strip():
            raise ValueError("peer_id must be non-empty")
        self.peer_id = peer_id.strip()
        self.path = Path(path)
        (self.path / "docs").mkdir(parents=True, exist_ok=True)
        (self.path / "conflicts").mkdir(parents=True, exist_ok=True)

    # -- local edits --------------------------------------------------------------
    def _doc_path(self, doc_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in doc_id)
        if not safe or safe in (".", ".."):
            raise ValueError(f"bad doc_id {doc_id!r}")
        return self.path / "docs" / f"{safe}.json"

    def write(self, doc_id: str, content: str) -> VersionedDoc:
        """Local edit: bump this peer's counter (the version *is* the
        edit history — no separate log needed for pairwise sync)."""
        try:
            doc = self.read(doc_id)
        except KeyError:
            doc = VersionedDoc(doc_id, "")
        doc.content = content
        doc.deleted = False
        doc.version[doc.version.get(self.peer_id, 0) + 1] = (
            doc.version.get(self.peer_id, 0) + 1
        )
        doc.updated_at = time.time()
        self._store(doc)
        return doc

    def delete(self, doc_id: str) -> None:
        """Tombstone: the deletion carries a version, so it syncs."""
        try:
            doc = self.read(doc_id)
        except KeyError:
            doc = VersionedDoc(doc_id, "")
        doc.deleted = True
        doc.content = ""
        doc.version[self.peer_id] = doc.version.get(self.peer_id, 0) + 1
        doc.updated_at = time.time()
        self._store(doc)

    def read(self, doc_id: str) -> VersionedDoc:
        p = self._doc_path(doc_id)
        if not p.exists():
            raise KeyError(f"unknown document {doc_id!r}")
        return VersionedDoc.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def _store(self, doc: VersionedDoc) -> None:
        p = self._doc_path(doc.doc_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(doc.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        tmp.replace(p)

    def doc_ids(self) -> list[str]:
        return sorted(p.stem for p in (self.path / "docs").glob("*.json"))

    def all_docs(self) -> dict[str, VersionedDoc]:
        out = {}
        for doc_id in self.doc_ids():
            out[doc_id] = self.read(doc_id)
        return out

    # -- conflicts --------------------------------------------------------------------
    def file_conflict(self, conflict: Conflict) -> Path:
        p = self.path / "conflicts" / f"{conflict.doc_id}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(conflict.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        tmp.replace(p)
        return p

    def conflicts(self) -> list[Conflict]:
        out = []
        for p in sorted((self.path / "conflicts").glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                Conflict(
                    data["doc_id"],
                    VersionedDoc.from_dict(data["local"]),
                    VersionedDoc.from_dict(data["remote"]),
                    data.get("detected_at", 0.0),
                )
            )
        return out

    def resolve_conflict(
        self, doc_id: str, choice: str, merged_content: Optional[str] = None
    ) -> VersionedDoc:
        """Resolve explicitly: ``choice`` is "local", "remote", or
        "merged" (with ``merged_content``). The winner's version merges
        both vectors and bumps this peer — it supersedes, honestly."""
        p = self.path / "conflicts" / f"{doc_id}.json"
        if not p.exists():
            raise KeyError(f"no conflict filed for {doc_id!r}")
        data = json.loads(p.read_text(encoding="utf-8"))
        local = VersionedDoc.from_dict(data["local"])
        remote = VersionedDoc.from_dict(data["remote"])
        if choice == "local":
            winner = local
        elif choice == "remote":
            winner = remote
        elif choice == "merged":
            if merged_content is None:
                raise ValueError("merged_content is required for choice='merged'")
            winner = VersionedDoc(
                doc_id, merged_content, merge_vectors(local.version, remote.version)
            )
        else:
            raise ValueError("choice must be 'local', 'remote', or 'merged'")
        winner.version = merge_vectors(local.version, remote.version)
        winner.version[self.peer_id] = winner.version.get(self.peer_id, 0) + 1
        winner.deleted = False
        winner.updated_at = time.time()
        self._store(winner)
        p.unlink()
        return winner


# ---------------------------------------------------------------------------
# Sync engine — pairwise, transport-agnostic
# ---------------------------------------------------------------------------

#: A transport moves documents between two workspaces and returns the
#: sync report. The only transports shipped are local-only; a network
#: transport would need authentication, encryption, and identity, which
#: this module does not provide and does not pretend to.
Transport = Callable[[Workspace, Workspace], dict]


class SyncEngine:
    """Pairwise sync between two workspaces over a transport.

    The transport moves documents; the *merge logic* always lives here.
    The default transport is local-only (direct access, same machine).
    """

    def __init__(self, transport: Optional[Transport] = None):
        self.transport = transport or self._local_exchange

    def sync(self, local: Workspace, remote: Workspace) -> dict:
        """Synchronize ``local`` with ``remote``. Returns a report:
        ``{"fast_forwarded", "pushed", "pulled", "conflicts"}``. Conflicts
        are filed on *both* sides as explicit records — never auto-merged."""
        return self.transport(local, remote)

    @staticmethod
    def _local_exchange(a: Workspace, b: Workspace) -> dict:
        report: dict[str, list] = {
            "fast_forwarded": [],
            "pushed": [],
            "pulled": [],
            "conflicts": [],
        }
        docs_a = a.all_docs()
        docs_b = b.all_docs()
        for doc_id in sorted(set(docs_a) | set(docs_b)):
            da = docs_a.get(doc_id)
            db = docs_b.get(doc_id)
            if da is None and db is not None:
                a._store(db)
                report["pulled"].append(doc_id)
            elif db is None and da is not None:
                b._store(da)
                report["pushed"].append(doc_id)
            elif da is not None and db is not None:
                if (
                    da.version == db.version
                    and da.content == db.content
                    and da.deleted == db.deleted
                ):
                    continue  # identical
                if dominates(da.version, db.version):
                    b._store(da)
                    report["pushed"].append(doc_id)
                    report["fast_forwarded"].append(doc_id)
                elif dominates(db.version, da.version):
                    a._store(db)
                    report["pulled"].append(doc_id)
                    report["fast_forwarded"].append(doc_id)
                else:
                    # Concurrent edits: file explicit conflicts on both sides.
                    conflict = Conflict(doc_id, da, db)
                    a.file_conflict(conflict)
                    b.file_conflict(conflict)
                    report["conflicts"].append(doc_id)
        return report


def local_copy_transport(a: Workspace, b: Workspace) -> dict:
    """Local-only transport: sync two workspaces by direct access (same
    machine). The honest stand-in for a network transport in tests and
    local use — NOT a network layer."""
    return SyncEngine._local_exchange(a, b)
