"""
Encrypted sync dry-run (Phase B prep) — inventory ~/.levi, hash blobs, write manifest.

No plaintext upload path until Phase B transport is stood up.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os


DEFAULT_LEVI = Path.home() / ".levi"
MANIFEST_NAME = "sync_manifest_dryrun.json"


@dataclass
class BlobEntry:
    rel: str
    size: int
    sha256: str
    kind: str  # json | seal | other

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SyncManifest:
    root: str
    blobs: List[BlobEntry] = field(default_factory=list)
    total_bytes: int = 0
    note: str = "DRY-RUN — no plaintext uploaded; ciphertext-only path is Phase B"
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "blobs": [b.to_dict() for b in self.blobs],
            "total_bytes": self.total_bytes,
            "blob_count": len(self.blobs),
            "note": self.note,
            "at": self.at,
        }


class SyncDryRun:
    """Inventories local state; writes manifest under ~/.levi/ — never transmits."""

    SKIP_NAMES = {".DS_Store", "__pycache__", MANIFEST_NAME}
    _HASH_CHUNK = 1024 * 1024  # 1 MiB — bounded memory even on multi-GB blobs

    def __init__(self, root: Optional[Path] = None):
        if root is not None and not isinstance(root, (str, Path)):
            raise ValueError("root must be a str or pathlib.Path")
        self.root = Path(root) if root else DEFAULT_LEVI

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str] | None:
        """(size, sha256) reading in bounded chunks — never whole-file in RAM."""
        h = hashlib.sha256()
        size = 0
        try:
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(SyncDryRun._HASH_CHUNK)
                    if not chunk:
                        break
                    h.update(chunk)
                    size += len(chunk)
        except OSError:
            return None
        return size, h.hexdigest()

    def _kind(self, path: Path) -> str:
        if path.suffix == ".seal":
            return "seal"
        if path.suffix in (".json", ".jsonl"):
            return "json"
        return "other"

    def inventory(self) -> SyncManifest:
        manifest = SyncManifest(
            root=str(self.root),
            at=datetime.now(timezone.utc).isoformat(),
        )
        if not self.root.exists():
            manifest.note += " | ~/.levi not created yet (run levi init)"
            return manifest

        for dirpath, dirnames, filenames in os.walk(self.root):
            # prune
            dirnames[:] = [
                d
                for d in dirnames
                if d not in self.SKIP_NAMES and not d.startswith(".")
            ]
            for name in filenames:
                if name in self.SKIP_NAMES or name.startswith("."):
                    continue
                path = Path(dirpath) / name
                hashed = self._hash_file(path)
                if hashed is None:
                    continue
                size, h = hashed
                rel = str(path.relative_to(self.root))
                entry = BlobEntry(rel=rel, size=size, sha256=h, kind=self._kind(path))
                manifest.blobs.append(entry)
                manifest.total_bytes += entry.size

        manifest.blobs.sort(key=lambda b: b.rel)
        return manifest

    def write_manifest(self, manifest: Optional[SyncManifest] = None) -> Path:
        m = manifest or self.inventory()
        self.root.mkdir(parents=True, exist_ok=True)
        out = self.root / MANIFEST_NAME
        # Atomic + owner-only: the manifest inventories private local state.
        tmp = out.with_suffix(".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(m.to_dict(), fh, indent=2)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp, out)
        return out

    def report(self) -> str:
        m = self.inventory()
        path = self.write_manifest(m)
        lines = [
            "══ Encrypted sync dry-run (Phase B prep) ══",
            f"root: {m.root}",
            f"blobs: {len(m.blobs)}  ·  bytes: {m.total_bytes}",
            f"manifest: {path}",
            f"note: {m.note}",
            "",
        ]
        for b in m.blobs[:12]:
            lines.append(f"  {b.kind:5}  {b.size:8}  {b.sha256[:12]}…  {b.rel}")
        if len(m.blobs) > 12:
            lines.append(f"  … +{len(m.blobs) - 12} more")
        lines.append("")
        lines.append("No plaintext upload path until Phase B transport is live.")
        return "\n".join(lines)
