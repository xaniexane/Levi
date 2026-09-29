"""Hicomb IDE: snapshot at EVERY stage.

Chauncey's law (2026-09-23): SNAPSHOT AT EVERY STAGE. Before testing or
editing at each stage — not just before the final write — all code
involved is snapshotted. The pipeline shape is:

    snapshot -> stage acts -> snapshot -> next stage

Every snapshot is receipted (stage name, timestamp, content hash) and
restorable; any stage can roll back to any earlier snapshot. This makes
every transformation reversible and gives a complete stage-by-stage
audit trail.

Stages wired (each captures pre + post):
  nlir-plan        NL->IR plan execution (ide_nl.plan_intent)
  nlir-apply       NL->IR apply under tier gates (ide_nl.apply_job)
  pollen-format    Pollen formats text (forge.forge_text,
                   pipeline.save_pipeline)
  surgeon-edit     Elite Surgeon repair (forge.forge_text)
  quetta-remix     Quetta Pan recombines denied paths
                   (self_upgrade.recombine)
  upgrade-propose  a new upgrade path is proposed (self_upgrade)
  upgrade-decide   per-path HITL decision (self_upgrade.decide)
  upgrade-apply    an approved path applies (self_upgrade.apply_projection)
  final-write      the guarded write to disk (pipeline.save_pipeline)
  sandbox-test     RESERVED contract: the upgrade-path sandbox test
                   runner (pending) wraps its run in this stage —
                   snapshot before the sandbox test runs, snapshot the
                   tested outcome after.

LAWS (declared up front, machine-checked in tests/test_hicomb_snapshots.py):
  S1 EVERY-STAGE   every acting stage captures a pre-snapshot before it
                   touches anything, and a post-snapshot after it acts.
                   An exception mid-stage still leaves the pre-snapshot
                   for rollback.
  S2 RECEIPTED     every snapshot is receipted: stage name, timestamp,
                   content hash, restorable location, and the id of the
                   previous snapshot (audit chain).
  S3 RESTORABLE    restore() returns byte-identical content to what was
                   captured; the content hash is re-verified on restore
                   and tampering raises SnapshotTampered.
  S4 VIOLATION     a stage that acts without its pre-snapshot is a
                   build-breaking violation: StageViolation. The guard
                   raises; it never degrades to a warning.
  S5 OFFLINE       stdlib only. No network imports, no model, no egress.

Store (default ``~/.levi/hicomb/ide/.snapshots/``): ``<id>.json`` payload
files plus append-only ``receipts.jsonl``. Tests pass an isolated
store_dir.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ------------------------------------------------------------------ errors
class StageViolation(Exception):
    """Build-breaking: a stage acted without its pre-snapshot."""


class SnapshotTampered(Exception):
    """A stored snapshot's content no longer matches its receipted hash."""


class SnapshotMissing(Exception):
    """No snapshot with that id exists in the store."""


# ------------------------------------------------------------------ helpers
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canon(payload: Dict[str, Any]) -> bytes:
    """Canonical bytes for hashing: deterministic across runs."""
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str,
    ).encode("utf-8")


def content_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canon(payload)).hexdigest()


@dataclass
class Snapshot:
    id: str
    stage: str
    kind: str  # "pre" | "post"
    ts: str
    hash: str
    size_bytes: int
    path: str  # restorable location
    prev: str  # previous snapshot id in the audit chain ("" for first)
    payload: Dict[str, Any]

    def as_receipt(self) -> Dict[str, Any]:
        return {
            "id": self.id, "stage": self.stage, "kind": self.kind,
            "ts": self.ts, "hash": self.hash,
            "size_bytes": self.size_bytes, "path": self.path,
            "prev": self.prev,
        }


# ------------------------------------------------------------------ store
class SnapshotStore:
    """Receipted, hash-verified, restorable per-stage snapshots."""

    def __init__(self, store_dir: Optional[Path | str] = None):
        self.root = Path(store_dir) if store_dir else (
            Path.home() / ".levi" / "hicomb" / "ide" / ".snapshots")
        self.root.mkdir(parents=True, exist_ok=True)
        self.receipts_path = self.root / "receipts.jsonl"
        self._prev = self._last_id()

    # ---- internals ---------------------------------------------------
    def _target_for(self, snapshot_id: str) -> Path:
        """Resolve an id to its payload file, contained in the store root.

        Snapshot ids are generated by capture(); a hostile or corrupted id
        must never escape the store directory (path traversal).
        """
        if (
            not snapshot_id
            or ".." in snapshot_id
            or "/" in snapshot_id
            or "\\" in snapshot_id
        ):
            raise SnapshotMissing(f"no snapshot {snapshot_id!r}")
        return self.root / f"{snapshot_id}.json"
    def _last_id(self) -> str:
        if not self.receipts_path.exists():
            return ""
        last = ""
        for line in self.receipts_path.read_text(
                encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    last = json.loads(line).get("id", last)
                except json.JSONDecodeError:
                    continue
        return last

    def _write_receipt(self, snap: Snapshot) -> None:
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(snap.as_receipt(), ensure_ascii=False)
                     + "\n")

    # ---- capture ------------------------------------------------------
    def capture(
        self,
        stage: str,
        payload: Dict[str, Any],
        kind: str = "pre",
    ) -> Snapshot:
        """Snapshot one stage moment. Always receipted (S2)."""
        if kind not in ("pre", "post"):
            raise ValueError(f"kind must be 'pre' or 'post', got {kind!r}")
        if not stage or ".." in stage or "/" in stage or "\\" in stage:
            raise ValueError(f"bad stage name {stage!r}: no path separators")
        payload = dict(payload)
        blob = _canon(payload)
        digest = hashlib.sha256(blob).hexdigest()
        sid = f"{_now().replace(':', '').replace('-', '')}" \
              f"-{stage}-{digest[:8]}-{uuid.uuid4().hex[:4]}"
        target = self.root / f"{sid}.json"
        target.write_text(
            json.dumps(
                {"id": sid, "stage": stage, "kind": kind, "ts": _now(),
                 "hash": digest, "payload": payload},
                ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        snap = Snapshot(
            id=sid, stage=stage, kind=kind, ts=_now(), hash=digest,
            size_bytes=len(blob), path=str(target), prev=self._prev,
            payload=payload,
        )
        self._write_receipt(snap)
        self._prev = sid
        return snap

    # ---- read ---------------------------------------------------------
    def receipts(self, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.receipts_path.exists():
            return []
        out = []
        for line in self.receipts_path.read_text(
                encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if stage is None or r.get("stage") == stage:
                out.append(r)
        return out

    def restore(self, snapshot_id: str) -> Dict[str, Any]:
        """Return the snapshot's payload, hash-verified (S3).

        Raises SnapshotMissing when the id is unknown, SnapshotTampered
        when the stored bytes no longer match the receipted hash — or when
        the stored file is corrupt/unreadable (corruption is tampering).
        """
        target = self._target_for(snapshot_id)
        if not target.exists():
            raise SnapshotMissing(f"no snapshot {snapshot_id!r}")
        try:
            doc = json.loads(target.read_text(encoding="utf-8"))
            payload = doc["payload"]
            stored_hash = doc["hash"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SnapshotTampered(
                f"snapshot {snapshot_id!r} is corrupt or unreadable: {exc}"
            ) from exc
        if content_hash(payload) != stored_hash:
            raise SnapshotTampered(
                f"snapshot {snapshot_id!r} content does not match its "
                f"receipted hash — the audit trail was altered")
        return payload

    def rollback_to(self, snapshot_id: str) -> Dict[str, Any]:
        """Roll back to any earlier snapshot: verified restore (S3)."""
        return self.restore(snapshot_id)

    def stages_seen(self) -> List[str]:
        seen: List[str] = []
        for r in self.receipts():
            if r.get("stage") not in seen:
                seen.append(r["stage"])
        return seen


# ------------------------------------------------------------------ guard
class StageRun:
    """One guarded stage execution: pre-snapshot exists before any act."""

    def __init__(self, guard: "StageGuard", stage: str,
                 pre: Optional[Snapshot]):
        self.guard = guard
        self.stage = stage
        self.pre = pre
        self.post: Optional[Snapshot] = None
        self._closed = False

    def act(self) -> None:
        """Declare the mutating act. Raises StageViolation when no
        pre-snapshot backs this run (S4) — a stage acting without its
        pre-snapshot is build-breaking, never a warning."""
        if self.pre is None or self._closed:
            raise StageViolation(
                f"stage {self.stage!r} acted without a pre-snapshot — "
                f"build-breaking violation of the snapshot-every-stage law")
        # The stage acts here; the caller performs its mutation after
        # this call returns.

    def end(self, post_payload: Dict[str, Any]) -> Snapshot:
        """Capture the post-snapshot and close the run."""
        if self._closed:
            raise StageViolation(
                f"stage {self.stage!r} ended twice — run already closed")
        self.post = self.guard.store.capture(
            self.stage, post_payload, kind="post")
        self._closed = True
        self.guard._close(self)
        return self.post

    def abort(self) -> None:
        """Close without a post-snapshot. The pre-snapshot stays for
        rollback (S1)."""
        self._closed = True
        self.guard._close(self)


class StageGuard:
    """Enforces the snapshot-every-stage law around acting stages."""

    def __init__(self, store: SnapshotStore):
        self.store = store
        self._open: Dict[str, StageRun] = {}

    def begin(self, stage: str, pre_payload: Dict[str, Any]) -> StageRun:
        """Capture the pre-snapshot and open the run. The stage may only
        act through the returned run (S1)."""
        pre = self.store.capture(stage, pre_payload, kind="pre")
        run = StageRun(self, stage, pre)
        self._open[stage] = run
        return run

    def check(self, stage: str) -> StageRun:
        """Return the open run for a stage, or raise StageViolation (S4)."""
        run = self._open.get(stage)
        if run is None or run.pre is None:
            raise StageViolation(
                f"stage {stage!r} acted without a pre-snapshot — "
                f"build-breaking violation of the snapshot-every-stage law")
        return run

    def _close(self, run: StageRun) -> None:
        if self._open.get(run.stage) is run:
            del self._open[run.stage]

    # context-manager form:  with guard.stage("x", pre) as run: ...
    def stage(self, stage: str,
              pre_payload: Dict[str, Any]) -> "_StageContext":
        return _StageContext(self, stage, pre_payload)


class _StageContext:
    def __init__(self, guard: StageGuard, stage: str,
                 pre_payload: Dict[str, Any]):
        self.guard = guard
        self.stage = stage
        self.pre_payload = pre_payload
        self.run: Optional[StageRun] = None
        self.post_payload: Dict[str, Any] = {"acted": True}

    def __enter__(self) -> StageRun:
        self.run = self.guard.begin(self.stage, self.pre_payload)
        return self.run

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert self.run is not None
        if exc_type is None:
            self.run.end(self.post_payload)
        else:
            # Exception mid-stage: the pre-snapshot stays for rollback (S1).
            self.run.abort()
        return False  # never swallow the exception


def snapshotted(
    store: SnapshotStore,
    stage: str,
    pre_payload: Dict[str, Any],
    fn: Callable[..., Any],
    *args: Any,
    post: Optional[Callable[[Any], Dict[str, Any]]] = None,
    **kwargs: Any,
) -> "tuple[Any, Snapshot, Snapshot]":
    """Run ``fn`` under snapshot discipline: pre -> act -> post.

    Returns (result, pre_snapshot, post_snapshot). Any exception from
    ``fn`` still leaves the pre-snapshot for rollback (S1); the exception
    itself is re-raised, never swallowed.
    """
    guard = StageGuard(store)
    run = guard.begin(stage, pre_payload)
    try:
        result = fn(*args, **kwargs)
    except Exception:
        run.abort()
        raise
    post_payload = (post(result) if callable(post)
                    else {"stage": stage, "acted": True})
    post_snap = run.end(post_payload)
    return result, run.pre, post_snap


__all__ = [
    "Snapshot",
    "SnapshotMissing",
    "SnapshotStore",
    "SnapshotTampered",
    "StageGuard",
    "StageRun",
    "StageViolation",
    "content_hash",
    "snapshotted",
]
