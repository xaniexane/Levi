"""Restore snapshots: download, verify hashes, stage. Never touches live
state unless ``--apply`` is given with explicit confirmation — and even
then a safety snapshot of the current state is taken first.
"""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from .config import backup_root, levi_home, staging_root
from .snapshot import SNAPSHOT_PREFIX, create_snapshot, list_snapshots, verify_snapshot
from .sync import REMOTE_DIR, configured_remote, rclone_available, run_rclone


def _local_pair(snapshot_id: str) -> tuple[Path, Path]:
    root = backup_root()
    return (
        root / f"{SNAPSHOT_PREFIX}{snapshot_id}.tar.gz",
        root / f"{SNAPSHOT_PREFIX}{snapshot_id}.manifest.json",
    )


def fetch_from_remote(snapshot_id: str, dest_dir: Path) -> tuple[Path, Path]:
    """Download a snapshot pair from the crypt remote into dest_dir."""
    if not rclone_available():
        raise FileNotFoundError("rclone is not installed")
    remote = configured_remote()
    if not remote:
        raise ValueError("no remote configured")
    dest_dir.mkdir(parents=True, exist_ok=True)
    tar_name = f"{SNAPSHOT_PREFIX}{snapshot_id}.tar.gz"
    mf_name = f"{SNAPSHOT_PREFIX}{snapshot_id}.manifest.json"
    for name in (tar_name, mf_name):
        proc = run_rclone("copy", f"{remote}:{REMOTE_DIR}/{name}", str(dest_dir))
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()[:200]
            raise RuntimeError(f"download of {name} failed: {err}")
    return dest_dir / tar_name, dest_dir / mf_name


def restore_snapshot(
    snapshot_id: str,
    *,
    from_remote: bool = False,
    apply: bool = False,
    yes: bool = False,
) -> dict:
    """Stage a snapshot for inspection; optionally apply it to live state."""
    home = levi_home()
    staging = staging_root() / snapshot_id
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    if from_remote:
        tarball, manifest = fetch_from_remote(snapshot_id, staging)
        # verify against the downloaded manifest (same format as local)
        ok, problems = _verify_pair(tarball, manifest)
    else:
        tarball, manifest = _local_pair(snapshot_id)
        if not tarball.exists():
            known = [s["snapshot_id"] for s in list_snapshots()]
            raise FileNotFoundError(
                f"snapshot '{snapshot_id}' not found locally"
                + (
                    f" (have: {', '.join(known[:5])})"
                    if known
                    else " (no local snapshots)"
                )
            )
        ok, problems = verify_snapshot(snapshot_id)
    if not ok:
        raise ValueError(
            "snapshot FAILED verification — refusing to restore: "
            + "; ".join(problems[:5])
        )

    extracted = staging / "extracted"
    extracted.mkdir(exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(extracted, filter="data")

    result: dict = {
        "snapshot_id": snapshot_id,
        "staged_at": str(staging),
        "extracted_at": str(extracted),
        "applied": False,
    }
    if not apply:
        result["message"] = (
            f"snapshot verified and staged at {extracted} — "
            "inspect it there; re-run with --apply to write it into live state"
        )
        return result

    if not yes:
        answer = input(
            f"Apply snapshot {snapshot_id} over {home}? "
            "This overwrites current state. Type RESTORE to confirm: "
        ).strip()
        if answer != "RESTORE":
            result["message"] = "aborted: confirmation not given"
            return result

    # Safety net: snapshot the CURRENT state before overwriting it.
    safety = create_snapshot(label="pre-restore")
    _apply_tree(extracted, home)
    result["applied"] = True
    result["safety_snapshot"] = safety["snapshot_id"]
    result["message"] = (
        f"snapshot {snapshot_id} applied to {home}; "
        f"pre-restore safety snapshot: {safety['snapshot_id']}"
    )
    return result


def _verify_pair(tarball: Path, manifest: Path) -> tuple[bool, list[str]]:
    """Hash-verify a downloaded (non-local-dir) snapshot pair."""
    import hashlib
    import json

    problems: list[str] = []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, [f"manifest unreadable: {exc}"]
    expected = {e["path"]: e["sha256"] for e in data.get("files", [])}
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            for rel, want in expected.items():
                try:
                    m = tf.getmember(rel)
                except KeyError:
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
        problems.append(f"tarball unreadable: {exc}")
    return (len(problems) == 0), problems


def _apply_tree(src: Path, home: Path) -> None:
    """Copy the extracted tree over the live state dir.

    Skips the backups/ and restore-staging/ dirs themselves — snapshots
    must never overwrite the snapshot store.
    """
    skip = {"backups", "restore-staging"}
    for entry in src.iterdir():
        if entry.name in skip:
            continue
        dest = home / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, dest)
