"""Sentinel integrity — host file-integrity baselines (SHA-256 manifests).

Create a baseline manifest of a directory tree, then verify it later:
any added/removed/changed file is reported. Purely defensive, local-only.

This is host integrity monitoring, distinct from
:mod:`levi.security.integrity` (FNV-1a pack-manifest tamper-refuse):
this module fingerprints *files on the operator's own host* with
SHA-256; it never refuses to load anything and never phones home.

Stdlib-only: ``hashlib``, ``json``, ``os``, ``time``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "IntegrityDiff",
    "create_baseline",
    "verify_baseline",
    "MANIFEST_VERSION",
    "MAX_FILES",
]

MANIFEST_VERSION = 1

#: Bounded: manifests cover at most this many files (sorted traversal).
MAX_FILES = 5000


@dataclass
class IntegrityDiff:
    """Outcome of a baseline verification."""

    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    changed: List[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.added or self.removed or self.changed)


def _sha256_file(path: Path) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def create_baseline(root: str, manifest_path: str) -> Dict[str, object]:
    """Hash up to ``MAX_FILES`` files under ``root`` into ``manifest_path``.

    Returns a summary dict. The manifest stores relative paths → sha256,
    plus creation metadata. Parent directories of ``manifest_path`` are
    created.
    """
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        raise ValueError(f"not a directory: {root}")
    entries: Dict[str, str] = {}
    skipped = 0
    for dirpath, _dirnames, filenames in os.walk(root_p):
        for name in sorted(filenames):
            if len(entries) + skipped >= MAX_FILES:
                skipped += 1
                continue
            full = Path(dirpath) / name
            rel = str(full.relative_to(root_p))
            digest = _sha256_file(full)
            if digest is None:
                skipped += 1
                continue
            entries[rel] = digest
    manifest = {
        "version": MANIFEST_VERSION,
        "root": str(root_p),
        "created": time.time(),
        "files": entries,
    }
    out = Path(manifest_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "manifest": str(out),
        "root": str(root_p),
        "files": len(entries),
        "skipped": skipped,
    }


def _load_manifest(manifest_path: str) -> Dict[str, str]:
    raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported or corrupt manifest: {manifest_path}")
    files = raw.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"corrupt manifest files table: {manifest_path}")
    return {str(k): str(v) for k, v in files.items()}


def verify_baseline(root: str, manifest_path: str) -> IntegrityDiff:
    """Compare ``root`` against the manifest; report added/removed/changed.

    Purely read-only — it reports differences, it never "heals" anything.
    Healing (restoring files) is a human decision, not an automated one.
    """
    root_p = Path(root).resolve()
    expected = _load_manifest(manifest_path)
    current: Dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root_p):
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = str(full.relative_to(root_p))
            digest = _sha256_file(full)
            if digest is not None:
                current[rel] = digest
    diff = IntegrityDiff()
    for rel, digest in current.items():
        if rel not in expected:
            diff.added.append(rel)
        elif expected[rel] != digest:
            diff.changed.append(rel)
    for rel in expected:
        if rel not in current:
            diff.removed.append(rel)
    diff.added.sort()
    diff.removed.sort()
    diff.changed.sort()
    return diff
