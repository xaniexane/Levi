"""Timestamped tarball snapshots of the LEVI state dir with sha256 manifests.

What gets backed up: everything under ``~/.levi`` EXCEPT the heavies —
model weights, caches, and the snapshots themselves. The corpus, growth
journal, memory, findings, scopes, and config are all small text/JSON and
are always included.
"""

from __future__ import annotations

import hashlib
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DEFAULT_KEEP_LOCAL,
    backup_root,
    levi_home,
    load_state,
    save_state,
)

SNAPSHOT_PREFIX = "levi-backup-"
MANIFEST_SUFFIX = ".manifest.json"

# Directories never packed (weights, caches, and ourselves).
EXCLUDE_DIRS = frozenset(
    {
        "models",
        "cache",
        "__pycache__",
        ".cache",
        "node_modules",
        "tmp",
        "backups",  # snapshots of snapshots would recurse
        "restore-staging",
        ".git",
    }
)

# Heavy/binary file types never packed.
EXCLUDE_SUFFIXES = frozenset(
    {
        ".pt",
        ".bin",
        ".gguf",
        ".safetensors",
        ".onnx",
        ".ckpt",
        ".pyc",
        ".pyo",
        ".zip",
        ".log",  # diagnostics; journal/memory/corpus are .json/.jsonl/.md
    }
)


def _iter_files(home: Path):
    """Yield (relative_posix_path, absolute_path) for everything packable."""
    results = []
    for path in home.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            rel = path.relative_to(home)
        except ValueError:
            continue
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        results.append((rel.as_posix(), path))
    results.sort(key=lambda t: t[0])
    return results


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_id(label: str | None = None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if label:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)[:32]
        return f"{ts}-{safe}" if safe else ts
    return ts


def create_snapshot(label: str | None = None, home: Path | None = None) -> dict:
    """Pack the state dir into a timestamped tarball + manifest. Returns info."""
    home = home or levi_home()
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)

    sid = _snapshot_id(label)
    tar_path = root / f"{SNAPSHOT_PREFIX}{sid}.tar.gz"
    manifest_path = root / f"{SNAPSHOT_PREFIX}{sid}{MANIFEST_SUFFIX}"
    if tar_path.exists():  # same-second collision: bump with microseconds
        sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        tar_path = root / f"{SNAPSHOT_PREFIX}{sid}.tar.gz"
        manifest_path = root / f"{SNAPSHOT_PREFIX}{sid}{MANIFEST_SUFFIX}"

    entries = []
    total = 0
    with tarfile.open(tar_path, "w:gz") as tf:
        for rel, abs_path in _iter_files(home):
            digest = _sha256(abs_path)
            size = abs_path.stat().st_size
            entries.append({"path": rel, "sha256": digest, "size": size})
            total += size
            tf.add(abs_path, arcname=rel)

    import json

    manifest = {
        "snapshot_id": sid,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": entries,
        "total_bytes": total,
        "excluded_dirs": sorted(EXCLUDE_DIRS),
        "excluded_suffixes": sorted(EXCLUDE_SUFFIXES),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    state = load_state()
    state["last_snapshot"] = {
        "snapshot_id": sid,
        "tarball": str(tar_path),
        "manifest": str(manifest_path),
        "files": len(entries),
        "total_bytes": total,
    }
    save_state(state)

    return {
        "snapshot_id": sid,
        "tarball": str(tar_path),
        "manifest": str(manifest_path),
        "files": len(entries),
        "total_bytes": total,
    }


def list_snapshots() -> list[dict]:
    """Newest-first list of local snapshots (from manifests)."""
    import json

    root = backup_root()
    out = []
    if not root.exists():
        return out
    for mf in sorted(root.glob(f"{SNAPSHOT_PREFIX}*{MANIFEST_SUFFIX}")):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sid = data.get("snapshot_id", mf.name)
        tar = root / f"{SNAPSHOT_PREFIX}{sid}.tar.gz"
        out.append(
            {
                "snapshot_id": sid,
                "tarball": str(tar),
                "manifest": str(mf),
                "files": len(data.get("files", [])),
                "total_bytes": data.get("total_bytes", 0),
                "created_at_utc": data.get("created_at_utc"),
                "complete": tar.exists(),
            }
        )
    out.sort(key=lambda s: s["snapshot_id"], reverse=True)
    return out


def prune_local(keep: int = DEFAULT_KEEP_LOCAL) -> list[str]:
    """Delete oldest snapshot pairs beyond `keep`. Returns removed ids."""
    snaps = list_snapshots()
    removed = []
    for snap in snaps[keep:]:
        for key in ("tarball", "manifest"):
            try:
                Path(snap[key]).unlink(missing_ok=True)
            except OSError:
                pass
        removed.append(snap["snapshot_id"])
    return removed


def verify_snapshot(snapshot_id: str) -> tuple[bool, list[str]]:
    """Recompute sha256 of every tarball member against the manifest.

    Returns (ok, problems). Catches tampering or corruption.
    """
    import json

    manifest_path = backup_root() / f"{SNAPSHOT_PREFIX}{snapshot_id}{MANIFEST_SUFFIX}"
    tar_path = backup_root() / f"{SNAPSHOT_PREFIX}{snapshot_id}.tar.gz"
    problems: list[str] = []
    if not manifest_path.exists():
        return False, [f"manifest missing: {manifest_path.name}"]
    if not tar_path.exists():
        return False, [f"tarball missing: {tar_path.name}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, [f"manifest unreadable: {exc}"]

    expected = {e["path"]: e["sha256"] for e in manifest.get("files", [])}
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            members = {m.name: m for m in tf.getmembers() if m.isfile()}
    except (tarfile.TarError, OSError) as exc:
        return False, [f"tarball unreadable: {exc}"]

    if set(members) != set(expected):
        problems.append(
            f"member set mismatch: manifest={len(expected)} tarball={len(members)}"
        )
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            for rel, want in expected.items():
                m = members.get(rel)
                if m is None:
                    problems.append(f"missing member: {rel}")
                    continue
                fh = tf.extractfile(m)
                if fh is None:
                    problems.append(f"unreadable member: {rel}")
                    continue
                h = hashlib.sha256()
                for chunk in iter(lambda fh=fh: fh.read(1024 * 1024), b""):
                    h.update(chunk)
                if h.hexdigest() != want:
                    problems.append(f"hash mismatch: {rel}")
    except (tarfile.TarError, OSError) as exc:
        problems.append(f"read error during verify: {exc}")
    return (len(problems) == 0), problems
