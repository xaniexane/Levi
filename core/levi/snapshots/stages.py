"""Stage snapshots — versioned, sealed, restorable captures.

Different from the life-context snapshots in :mod:`levi.snapshots.store`
(suspend/resume for a person). A *stage* snapshot captures an artifact
tree — a boot camp at a named stage, a client's system, a project config —
so you can diff stages, restore, fork-and-refine (improve a copy without
touching the original), recreate, and implement.

Immutability by construction:
- content-addressed: the snapshot id is the SHA-256 of the canonical payload.
- hash-chained: every snapshot MACs the previous link with the keeper key.
- sealed at rest: Veil-lineage Encrypt-then-MAC (:mod:`levi.snapshots._seal`).

Tampering breaks the seal or the chain, loudly. Originals are never
mutated: fork creates a child, restore writes to a target you name.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from levi.snapshots import _seal

_CONTEXT = "snapshots/stage"
_GENESIS = "GENESIS"


class StageError(ValueError):
    """A stage snapshot invariant was violated."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_home(home: Optional[Path] = None) -> Path:
    raw = os.environ.get("LEVI_HOME")
    base = Path(home) if home is not None else (Path(raw).expanduser() if raw else Path.home() / ".levi")
    return base.expanduser()


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _snapshot_id(payload_hash: str, parent_id: str) -> str:
    # Identity = content + lineage. Same content with no parent dedupes to
    # one snapshot; a fork is a new lineage node even before refinement.
    preimage = (payload_hash + "\x00" + (parent_id or "")).encode("utf-8")
    return "stage_" + hashlib.sha256(preimage).hexdigest()[:16]


def _chain_mac(keeper: bytes, prev_mac: str, snapshot_id: str, payload_hash: str) -> str:
    msg = (prev_mac + snapshot_id + payload_hash).encode("utf-8")
    return hmac.new(keeper, msg, hashlib.sha256).hexdigest()


@dataclass
class StageSnapshot:
    """One immutable stage capture. The payload lives sealed in the blob."""

    id: str
    name: str
    stage_label: str
    created_at: str
    prev_id: str  # chain predecessor ("" for genesis)
    parent_id: str  # fork parent ("" when not a fork)
    payload_hash: str
    chain_mac: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StageSnapshot":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


class StageStore:
    """Owner-only store of stage snapshots."""

    def __init__(self, home: Optional[Path] = None):
        self.root = _resolve_home(home) / "stage-snapshots"
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)
        os.chmod(self.blobs, 0o700)
        self.index_path = self.root / "index.jsonl"
        if not self.index_path.exists():
            fd = os.open(str(self.index_path), os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(fd)
        else:
            os.chmod(self.index_path, 0o600)
        self._keeper = _seal.keeper_key(self.root)

    # -- index ---------------------------------------------------------
    def _read_index(self) -> List[StageSnapshot]:
        out: List[StageSnapshot] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(StageSnapshot.from_dict(json.loads(line)))
            except Exception:
                continue
        return out

    def _append_index(self, snap: StageSnapshot) -> None:
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(snap.to_dict(), sort_keys=True) + "\n")
        os.chmod(self.index_path, 0o600)

    def _blob_path(self, payload_hash: str) -> Path:
        # Blobs are keyed by pure content hash: identical payloads share
        # one sealed blob; index entries (lineage nodes) stay distinct.
        return self.blobs / (payload_hash + ".json")

    # -- capture -------------------------------------------------------
    def capture_stage(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        stage_label: str = "",
        note: str = "",
        parent_id: str = "",
    ) -> StageSnapshot:
        if not name or not name.strip():
            raise StageError("name must be non-empty")
        if not isinstance(payload, Mapping):
            raise StageError("payload must be a mapping")
        payload_hash = _payload_hash(payload)
        parent_id = parent_id or ""
        snapshot_id = _snapshot_id(payload_hash, parent_id)
        for existing in self._read_index():
            if existing.id == snapshot_id:
                # Identical content + lineage: already captured. Dedupe.
                return existing
        entries = self._read_index()
        prev_id = entries[-1].id if entries else ""
        prev_mac = entries[-1].chain_mac if entries else _GENESIS
        chain_mac = _chain_mac(self._keeper, prev_mac, snapshot_id, payload_hash)
        snap = StageSnapshot(
            id=snapshot_id,
            name=name.strip(),
            stage_label=stage_label,
            created_at=_utcnow(),
            prev_id=prev_id,
            parent_id=parent_id,
            payload_hash=payload_hash,
            chain_mac=chain_mac,
            note=note,
        )
        blob = self._blob_path(payload_hash)
        if not blob.exists():
            envelope = _seal.seal_bytes(_canonical(payload), self._keeper, _CONTEXT)
            fd = os.open(str(blob), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(envelope, fh, sort_keys=True)
            except BaseException:
                try:
                    blob.unlink()
                except OSError:
                    pass
                raise
            os.chmod(blob, 0o600)
        self._append_index(snap)
        return snap

    # -- read ----------------------------------------------------------
    def get_stage(self, snapshot_id: str) -> Optional[StageSnapshot]:
        for s in self._read_index():
            if s.id == snapshot_id:
                return s
        return None

    def list_stages(self) -> List[StageSnapshot]:
        return self._read_index()

    def materialize(self, snapshot_id: str) -> Dict[str, Any]:
        """Return the unsealed payload. Raises StageError on tampering."""
        snap = self.get_stage(snapshot_id)
        if snap is None:
            raise StageError(f"unknown snapshot {snapshot_id!r}")
        blob = self._blob_path(snap.payload_hash)
        if not blob.exists():
            raise StageError(f"blob missing for {snapshot_id!r} — store is damaged")
        try:
            envelope = json.loads(blob.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StageError(f"blob for {snapshot_id!r} is not valid JSON: {exc}") from exc
        try:
            raw = _seal.open_bytes(envelope, self._keeper, _CONTEXT)
        except _seal.SealError as exc:
            raise StageError(f"snapshot {snapshot_id!r} failed seal verification: {exc}") from exc
        payload = json.loads(raw.decode("utf-8"))
        if _payload_hash(payload) != snap.payload_hash:
            raise StageError(f"snapshot {snapshot_id!r} payload hash mismatch — tampered")
        return payload

    # -- verify --------------------------------------------------------
    def verify_stage(self, snapshot_id: str) -> StageSnapshot:
        """Unseal, re-hash, and check the chain link. Raises on any break."""
        snap = self.get_stage(snapshot_id)
        if snap is None:
            raise StageError(f"unknown snapshot {snapshot_id!r}")
        self.materialize(snapshot_id)  # seal + payload hash checks
        entries = self._read_index()
        idx = next(i for i, s in enumerate(entries) if s.id == snapshot_id)
        prev_mac = entries[idx - 1].chain_mac if idx > 0 else _GENESIS
        expect = _chain_mac(self._keeper, prev_mac, snap.id, snap.payload_hash)
        if not hmac.compare_digest(expect, snap.chain_mac):
            raise StageError(f"snapshot {snapshot_id!r} chain link broken — tampered index")
        if idx > 0 and snap.prev_id != entries[idx - 1].id:
            raise StageError(f"snapshot {snapshot_id!r} prev_id does not match chain order")
        return snap

    def verify_chain(self) -> int:
        """Verify every snapshot. Returns the count verified. Raises on first break."""
        count = 0
        for snap in self._read_index():
            self.verify_stage(snap.id)
            count += 1
        return count

    # -- fork / restore / recreate / implement -------------------------
    def fork_stage(
        self,
        snapshot_id: str,
        name: str,
        *,
        stage_label: str = "",
        note: str = "",
    ) -> StageSnapshot:
        """Fork-and-refine: capture a child copy. The original is untouched."""
        payload = self.materialize(snapshot_id)
        return self.capture_stage(
            name,
            copy.deepcopy(payload),
            stage_label=stage_label or f"fork-of-{snapshot_id}",
            note=note,
            parent_id=snapshot_id,
        )

    def restore_stage(self, snapshot_id: str, target_dir: Path) -> Path:
        """Write the payload to a target directory. The snapshot is untouched."""
        payload = self.materialize(snapshot_id)
        snap = self.get_stage(snapshot_id)
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "payload.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "snapshot_id": snap.id,
            "name": snap.name,
            "stage_label": snap.stage_label,
            "created_at": snap.created_at,
            "payload_hash": snap.payload_hash,
            "restored_at": _utcnow(),
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return target

    def recreate_stage(self, snapshot_id: str, dest_dir: Optional[Path] = None) -> Path:
        """Recreate a snapshot into a fresh directory. Returns the directory."""
        dest = Path(dest_dir) if dest_dir is not None else Path.cwd() / f"stage_{snapshot_id}"
        if dest.exists() and any(dest.iterdir()):
            raise StageError(f"recreate target {dest} exists and is not empty")
        return self.restore_stage(snapshot_id, dest)

    def implement_stage(
        self, snapshot_id: str, handler: Callable[[Dict[str, Any]], Any]
    ) -> Any:
        """Implement: hand the payload to a caller-supplied handler.

        The engine never guesses what "implement" means for your payload —
        the handler decides. The snapshot itself is never mutated.
        """
        if not callable(handler):
            raise StageError("handler must be callable")
        return handler(self.materialize(snapshot_id))


# -- diff ---------------------------------------------------------------


def _diff_walk(a: Any, b: Any, path: str, out: List[Dict[str, Any]]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            p = f"{path}.{key}" if path else str(key)
            if key not in a:
                out.append({"path": p, "kind": "added", "a": None, "b": b[key]})
            elif key not in b:
                out.append({"path": p, "kind": "removed", "a": a[key], "b": None})
            else:
                _diff_walk(a[key], b[key], p, out)
    elif isinstance(a, list) and isinstance(b, list):
        if a != b:
            out.append({"path": path or "<root>", "kind": "changed", "a": a, "b": b})
    else:
        if a != b:
            out.append({"path": path or "<root>", "kind": "changed", "a": a, "b": b})


def diff_stages(store: StageStore, a_id: str, b_id: str) -> List[Dict[str, Any]]:
    """Diff two snapshots: added / removed / changed paths, a -> b."""
    a = store.materialize(a_id)
    b = store.materialize(b_id)
    out: List[Dict[str, Any]] = []
    _diff_walk(a, b, "", out)
    return out


# -- module-level conveniences -------------------------------------------

_default_store: Optional[StageStore] = None


def _store(home: Optional[Path] = None) -> StageStore:
    global _default_store
    if home is None and _default_store is not None:
        return _default_store
    s = StageStore(home=home)
    if home is None:
        _default_store = s
    return s


def capture(name: str, payload: Mapping[str, Any], **kwargs: Any) -> StageSnapshot:
    return _store(kwargs.pop("home", None)).capture_stage(name, payload, **kwargs)


def diff_snapshots(a_id: str, b_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    return diff_stages(_store(home), a_id, b_id)


def fork_snapshot(snapshot_id: str, name: str, home: Optional[Path] = None, **kwargs: Any) -> StageSnapshot:
    return _store(home).fork_stage(snapshot_id, name, **kwargs)


def restore_snapshot(snapshot_id: str, target_dir: Path, home: Optional[Path] = None) -> Path:
    return _store(home).restore_stage(snapshot_id, target_dir)


def recreate_snapshot(snapshot_id: str, dest_dir: Optional[Path] = None, home: Optional[Path] = None) -> Path:
    return _store(home).recreate_stage(snapshot_id, dest_dir)


def implement_snapshot(snapshot_id: str, handler: Callable[[Dict[str, Any]], Any], home: Optional[Path] = None) -> Any:
    return _store(home).implement_stage(snapshot_id, handler)


def materialize(snapshot_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    return _store(home).materialize(snapshot_id)


def verify_chain(home: Optional[Path] = None) -> int:
    return _store(home).verify_chain()
