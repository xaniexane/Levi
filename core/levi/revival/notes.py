"""LEVI's local-first memory sync: offline-first bidirectional replica sync
with explicit conflicts.

Inspired by Lotus Notes (Iris Associates / Ray Ozzie et al., developed
from 1984, shipped 1989; still ships as HCL Domino). The ahead-of-its-time
mechanism: *bidirectional replication of document databases* — every user
holds a local replica, works fully offline, and syncs both directions on
connect; conflicts are surfaced, never silently merged; networks are
treated as intermittent by default. Notes never died — its lineage runs
Notes → Groove → CRDT research → Automerge/Yjs and the local-first
movement.

Remix delta: Notes' replication discipline reimagined as LEVI's own
memory sync — not a Notes clone. Replicas are plain local directories
(not .nsf databases), sync is a method call between two Replica objects
(not a server protocol), and conflict records are LEVI's own JSON format
(both versions preserved, flagged for a human). No mail client, no
formula engine, no access-control model — the load-bearing mechanism is
the replication discipline, improved by making the transport the caller's
business entirely.

This is an original, from-scratch reimplementation for LEVI — no Notes
code is used. A ``Replica`` is a local directory holding a document
database (one JSON file per document plus tombstones). Every document
carries a revision vector (``replica_id -> sequence``). ``sync_with``
reconciles two local replicas bidirectionally: the dominating revision
wins; concurrent edits that differ become explicit ``Conflict`` records —
both versions preserved, flagged for a human, never auto-merged.

Transport-agnostic: ``sync_with`` takes another ``Replica`` object. How
the bytes move (USB stick, rsync, sneakernet, a future LEVI transport) is
the caller's business — the protocol only needs the two directories.
Honest about it: there is no network code here, and conflict resolution
is a human decision the module stages but never makes.

Honesty: LOAD-BEARING — offline-first bidirectional sync with explicit
conflicts, the discipline Notes got right in 1989.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReplicationError(Exception):
    """Base class for replication failures."""


class DeletedDocument(ReplicationError):
    """The document exists only as a tombstone."""

    def __init__(self, doc_id: str):
        super().__init__(f"document {doc_id!r} was deleted")
        self.doc_id = doc_id


# ---------------------------------------------------------------------------
# Revision vectors
# ---------------------------------------------------------------------------


def dominates(a: dict[str, int], b: dict[str, int]) -> bool:
    """True iff revision vector ``a`` dominates ``b`` (a >= b everywhere
    and a > b somewhere, or a simply knows more replicas)."""
    if not b:
        return True
    if not a:
        return False
    ge = all(a.get(k, 0) >= v for k, v in b.items())
    gt = any(a.get(k, 0) > v for k, v in b.items()) or any(
        k not in b for k in a)
    return ge and gt


def merge_revs(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b)}


# ---------------------------------------------------------------------------
# Documents and conflicts
# ---------------------------------------------------------------------------


@dataclass
class Conflict:
    """An explicit, surfaced conflict — both versions preserved."""

    doc_id: str
    versions: dict[str, dict]  # replica_id -> {"content", "rev", "updated_at"}
    detected_at: float

    def to_dict(self) -> dict:
        return {"doc_id": self.doc_id, "versions": self.versions,
                "detected_at": self.detected_at}

    @classmethod
    def from_dict(cls, data: dict) -> "Conflict":
        return cls(data["doc_id"], data["versions"], data["detected_at"])


def _doc_record(doc_id: str, content: Any, rev: dict[str, int],
                deleted: bool = False) -> dict:
    return {"doc_id": doc_id, "content": content, "rev": rev,
            "updated_at": time.time(), "deleted": deleted}


# ---------------------------------------------------------------------------
# Replica
# ---------------------------------------------------------------------------


class Replica:
    """One offline-first replica: a directory with a document database.

    Layout: ``<path>/docs/<safe-doc-id>.json`` plus ``conflicts.json``.
    All operations are local; sync happens on contact via
    :meth:`sync_with`.
    """

    def __init__(self, path: str | Path, replica_id: str):
        if not replica_id or not replica_id.strip():
            raise ValueError("replica_id must be non-empty")
        self.path = Path(path)
        self.replica_id = replica_id.strip()
        self.docs_dir = self.path / "docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self._conflicts_path = self.path / "conflicts.json"

    # -- local document operations (fully offline) -----------------------------
    def _doc_path(self, doc_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in doc_id)
        if not safe or safe in (".", ".."):
            raise ValueError(f"unsafe doc_id {doc_id!r}")
        return self.docs_dir / f"{safe}.json"

    def _read_record(self, doc_id: str) -> Optional[dict]:
        p = self._doc_path(doc_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def _write_record(self, record: dict) -> None:
        p = self._doc_path(record["doc_id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)

    def put(self, doc_id: str, content: Any) -> dict[str, int]:
        """Create or update a document; bumps this replica's sequence."""
        _require_jsonable(content)
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        old = self._read_record(doc_id)
        rev = dict(old["rev"]) if old else {}
        rev[self.replica_id] = rev.get(self.replica_id, 0) + 1
        self._write_record(_doc_record(doc_id, content, rev))
        return rev

    def get(self, doc_id: str) -> Any:
        rec = self._read_record(doc_id)
        if rec is None:
            raise KeyError(f"notes: unknown document {doc_id!r}")
        if rec.get("deleted"):
            raise DeletedDocument(doc_id)
        return rec["content"]

    def delete(self, doc_id: str) -> None:
        """Tombstone a document (deletion replicates like an edit)."""
        old = self._read_record(doc_id)
        if old is None:
            raise KeyError(f"notes: unknown document {doc_id!r}")
        rev = dict(old["rev"])
        rev[self.replica_id] = rev.get(self.replica_id, 0) + 1
        self._write_record(_doc_record(doc_id, None, rev, deleted=True))

    def list_docs(self, include_deleted: bool = False) -> list[str]:
        out = []
        for p in sorted(self.docs_dir.glob("*.json")):
            rec = json.loads(p.read_text(encoding="utf-8"))
            if rec.get("deleted") and not include_deleted:
                continue
            out.append(rec["doc_id"])
        return out

    def rev_of(self, doc_id: str) -> Optional[dict[str, int]]:
        rec = self._read_record(doc_id)
        return dict(rec["rev"]) if rec else None

    # -- conflicts --------------------------------------------------------------
    def conflicts(self) -> list[Conflict]:
        if not self._conflicts_path.exists():
            return []
        data = json.loads(self._conflicts_path.read_text(encoding="utf-8"))
        return [Conflict.from_dict(c) for c in data]

    def _save_conflicts(self, conflicts: list[Conflict]) -> None:
        tmp = self._conflicts_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([c.to_dict() for c in conflicts],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._conflicts_path)

    def resolve_conflict(self, doc_id: str, winner_replica_id: str) -> None:
        """Resolve explicitly: the chosen version becomes the new revision
        (merged rev vector, bumped sequence). The human decides; the module
        only stages the decision."""
        conflicts = self.conflicts()
        target = next((c for c in conflicts if c.doc_id == doc_id), None)
        if target is None:
            raise KeyError(f"notes: no conflict on {doc_id!r}")
        if winner_replica_id not in target.versions:
            raise ValueError(
                f"winner must be one of {sorted(target.versions)}")
        winner = target.versions[winner_replica_id]
        merged = merge_revs(*(v["rev"] for v in target.versions.values()))
        merged[self.replica_id] = merged.get(self.replica_id, 0) + 1
        self._write_record(_doc_record(doc_id, winner["content"], merged))
        self._save_conflicts([c for c in conflicts if c.doc_id != doc_id])

    # -- bidirectional sync -------------------------------------------------------
    def sync_with(self, other: "Replica") -> dict:
        """Bidirectional sync with another replica. Returns a report
        ``{"sent": [...], "received": [...], "conflicts": [...]}``.

        For each document: the dominating revision wins and is copied;
        equal content with concurrent revs converges silently (same words,
        no conflict); concurrent *differing* edits become explicit
        conflicts on both replicas. Tombstones replicate like edits.
        """
        if other.replica_id == self.replica_id:
            raise ValueError("cannot sync a replica with itself")
        sent, received, new_conflicts = [], [], []
        for doc_id in sorted(set(self.list_docs(include_deleted=True))
                             | set(other.list_docs(include_deleted=True))):
            mine = self._read_record(doc_id)
            theirs = other._read_record(doc_id)
            if mine is None:
                self._write_record(theirs)
                received.append(doc_id)
            elif theirs is None:
                other._write_record(mine)
                sent.append(doc_id)
            elif dominates(mine["rev"], theirs["rev"]):
                if mine["rev"] != theirs["rev"]:
                    other._write_record(mine)
                    sent.append(doc_id)
            elif dominates(theirs["rev"], mine["rev"]):
                self._write_record(theirs)
                received.append(doc_id)
            else:
                # Concurrent. Same content (incl. both-deleted) converges;
                # differing content is an explicit conflict on both sides.
                if mine["content"] == theirs["content"] and \
                        mine.get("deleted") == theirs.get("deleted"):
                    merged = _doc_record(doc_id, mine["content"],
                                         merge_revs(mine["rev"], theirs["rev"]),
                                         deleted=bool(mine.get("deleted")))
                    self._write_record(merged)
                    other._write_record(merged)
                else:
                    for replica, rec_a, rec_b in (
                            (self, mine, theirs), (other, theirs, mine)):
                        conflicts = replica.conflicts()
                        if not any(c.doc_id == doc_id for c in conflicts):
                            conflicts.append(Conflict(
                                doc_id=doc_id,
                                versions={
                                    self.replica_id: {
                                        "content": mine["content"],
                                        "rev": mine["rev"],
                                        "updated_at": mine["updated_at"]},
                                    other.replica_id: {
                                        "content": theirs["content"],
                                        "rev": theirs["rev"],
                                        "updated_at": theirs["updated_at"]},
                                },
                                detected_at=time.time(),
                            ))
                            replica._save_conflicts(conflicts)
                    new_conflicts.append(doc_id)
        return {"sent": sent, "received": received, "conflicts": new_conflicts}


def _require_jsonable(value: Any) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"notes: document content must be JSON-serializable: {exc}") from exc


__all__ = [
    "ReplicationError",
    "DeletedDocument",
    "dominates",
    "merge_revs",
    "Conflict",
    "Replica",
]
