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

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DEFAULT_LEVI

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
                try:
                    data = path.read_bytes()
                except Exception:
                    continue
                rel = str(path.relative_to(self.root))
                h = hashlib.sha256(data).hexdigest()
                entry = BlobEntry(
                    rel=rel, size=len(data), sha256=h, kind=self._kind(path)
                )
                manifest.blobs.append(entry)
                manifest.total_bytes += entry.size

        manifest.blobs.sort(key=lambda b: b.rel)
        return manifest

    def write_manifest(self, manifest: Optional[SyncManifest] = None) -> Path:
        m = manifest or self.inventory()
        self.root.mkdir(parents=True, exist_ok=True)
        out = self.root / MANIFEST_NAME
        out.write_text(json.dumps(m.to_dict(), indent=2), encoding="utf-8")
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
