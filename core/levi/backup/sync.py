"""Ship snapshots off-machine with rclone — always behind a crypt overlay.

Privacy design: the configured remote MUST be an rclone ``crypt`` remote
wrapping the real backend (GCS or archive.org S3). Plaintext never touches
the wire or the bucket: even a misconfigured-public bucket only holds
client-side-encrypted blobs. ``verify_remote()`` enforces this before any
sync; sync refuses to run against a non-crypt remote.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config, load_state, rclone_available, rclone_path, save_state

REMOTE_DIR = "levi-backups"
SYNC_TIMEOUT_S = 300


def run_rclone(*args: str, timeout: int = SYNC_TIMEOUT_S) -> subprocess.CompletedProcess:
    exe = rclone_path()
    if exe is None:
        raise FileNotFoundError("rclone is not installed")
    return subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def configured_remote() -> str | None:
    """The crypt remote name from config, e.g. 'levi-crypt'."""
    return load_config().get("remote")


def verify_remote(remote: str | None = None) -> tuple[bool, str]:
    """Check the named remote is an rclone crypt overlay. No network needed."""
    remote = remote or configured_remote()
    if not remote:
        return False, "no remote configured (levi backup configure --remote NAME)"
    if not rclone_available():
        return False, "rclone is not installed"
    try:
        proc = run_rclone("config", "dump", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"could not read rclone config: {exc}"
    if proc.returncode != 0:
        return False, f"rclone config dump failed: {proc.stderr.strip()[:200]}"
    try:
        dump = json.loads(proc.stdout or "{}")
    except ValueError:
        return False, "rclone config dump was not valid JSON"
    entry = dump.get(remote)
    if entry is None:
        return False, f"remote '{remote}' not found in rclone config"
    if entry.get("type") != "crypt":
        return (
            False,
            f"remote '{remote}' is type '{entry.get('type')}', not 'crypt' — "
            "refusing: plaintext must never leave this machine unencrypted",
        )
    if not entry.get("remote"):
        return False, f"remote '{remote}' is crypt but has no wrapped backend"
    return True, f"remote '{remote}' is a crypt overlay wrapping '{entry['remote']}'"


def sync_snapshot(
    tarball: str | Path,
    manifest: str | Path,
    remote: str | None = None,
) -> dict:
    """Copy one snapshot pair to the crypt remote. Returns a result dict."""
    remote = remote or configured_remote()
    if not rclone_available():
        return {
            "ok": False,
            "synced": False,
            "message": "rclone is not installed — snapshot kept locally only. "
            "Install rclone (see docs/BACKUP.md) to enable off-machine sync.",
        }
    ok, why = verify_remote(remote)
    if not ok:
        return {"ok": False, "synced": False, "message": why}

    tarball, manifest = Path(tarball), Path(manifest)
    for label, p in (("tarball", tarball), ("manifest", manifest)):
        if not p.exists():
            return {
                "ok": False,
                "synced": False,
                "message": f"{label} missing: {p}",
            }
    dest = f"{remote}:{REMOTE_DIR}/"
    for label, p in (("tarball", tarball), ("manifest", manifest)):
        try:
            proc = run_rclone("copy", str(p), dest)
        except (OSError, subprocess.TimeoutExpired) as exc:
            _record_sync(False, str(exc))
            return {"ok": False, "synced": False, "message": f"sync failed: {exc}"}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()[:300]
            _record_sync(False, err)
            return {
                "ok": False,
                "synced": False,
                "message": f"rclone copy of {label} failed: {err}",
            }

    _record_sync(True, "")
    return {
        "ok": True,
        "synced": True,
        "message": f"synced to {dest} (encrypted via crypt overlay)",
    }


def _record_sync(ok: bool, error: str) -> None:
    state = load_state()
    state["last_sync_attempt_utc"] = datetime.now(timezone.utc).isoformat()
    state["last_sync_ok"] = ok
    state["last_sync_error"] = error
    if ok:
        state["last_sync_utc"] = state["last_sync_attempt_utc"]
    save_state(state)
