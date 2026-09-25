"""Google Drive bridge for video learning — packs out, refined packs back in.

Chauncey's loop: export_pack() uploads the analysis pack JSON to Drive,
he refines it in Grok / GPT / Claude chat, saves the refined version
(JSON or Markdown) into the same Drive folder, and download_refined()
pulls it back for ingest.

The default runner shells to `hatch_gws_cli`. Tests inject a fake runner,
so no Drive traffic happens in the test suite.

DRIVE_FOLDER env var (LEVI_VIDEO_LEARN_FOLDER) pins an existing folder id;
otherwise the folder "Levi Video Learning" is found or created on first use.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .analyze import SCHEMA

DEFAULT_FOLDER_NAME = "Levi Video Learning"
REGISTRY_DIR = Path.home() / ".levi" / "video_learn"
EXPORTS_DIR = REGISTRY_DIR / "exports"
REGISTRY_FILE = REGISTRY_DIR / "exports.jsonl"

Runner = Callable[[List[str]], Dict]


class DriveError(RuntimeError):
    """Raised when the Drive CLI call fails."""


def _default_runner(cmd: List[str]) -> Dict:
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise DriveError(f"drive command failed: {' '.join(cmd[:4])}: {out[:300]}")
    try:
        return json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        return {"raw": out}


def _run(runner: Optional[Runner], cmd: List[str]) -> Dict:
    return (runner or _default_runner)(cmd)


def ensure_folder(
    name: str = DEFAULT_FOLDER_NAME, runner: Optional[Runner] = None
) -> str:
    """Return the folder id, creating the folder if needed."""
    pinned = os.environ.get("LEVI_VIDEO_LEARN_FOLDER")
    if pinned:
        return pinned
    found = _run(
        runner,
        [
            "hatch_gws_cli", "drive", "files", "list",
            "--params", json.dumps({
                "q": (
                    f"name = '{name}' and "
                    "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                ),
                "fields": "files(id,name)",
            }),
        ],
    )
    files = found.get("files") or []
    if files:
        return files[0]["id"]
    created = _run(
        runner,
        [
            "hatch_gws_cli", "drive", "files", "create",
            "--json", json.dumps({
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
            }),
            "--params", json.dumps({"fields": "id,name"}),
        ],
    )
    folder_id = created.get("id")
    if not folder_id:
        raise DriveError(f"could not create Drive folder {name!r}: {created!r}")
    return folder_id


def export_pack(
    pack: Dict,
    folder_name: str = DEFAULT_FOLDER_NAME,
    runner: Optional[Runner] = None,
    registry_file: Optional[Path] = None,
) -> Dict:
    """Upload a pack to Drive and record it in the export registry.

    Returns a receipt: pack_hash, drive_file_id, folder_id, exported_at.
    The registry is what ingest_refined checks against (law 3: no orphaned
    knowledge — refined packs must reference a pack we actually exported).
    """
    if pack.get("schema") != SCHEMA:
        raise DriveError(f"not a video pack (schema={pack.get('schema')!r})")
    if not pack.get("pack_hash"):
        raise DriveError("pack has no pack_hash — analyze it first")
    folder_id = ensure_folder(folder_name, runner)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    local_path = EXPORTS_DIR / f"{pack['pack_hash']}.json"
    local_path.write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")

    uploaded = _run(
        runner,
        [
            "hatch_gws_cli", "drive", "+upload", str(local_path),
            "--parent", folder_id,
            "--name", f"video-pack-{pack['pack_hash'][:12]}.json",
        ],
    )
    file_id = uploaded.get("id") or uploaded.get("fileId")
    if not file_id:
        raise DriveError(f"upload returned no file id: {uploaded!r}")

    reg = registry_file or REGISTRY_FILE
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "pack_hash": pack["pack_hash"],
            "url": pack.get("url"),
            "drive_file_id": file_id,
            "folder_id": folder_id,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }) + "\n")

    return {
        "pack_hash": pack["pack_hash"],
        "drive_file_id": file_id,
        "folder_id": folder_id,
        "local_path": str(local_path),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def list_refined(
    folder_name: str = DEFAULT_FOLDER_NAME, runner: Optional[Runner] = None
) -> List[Dict]:
    """List candidate refined files Chauncey dropped in the folder."""
    folder_id = ensure_folder(folder_name, runner)
    found = _run(
        runner,
        [
            "hatch_gws_cli", "drive", "files", "list",
            "--params", json.dumps({
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "files(id,name,mimeType,modifiedTime)",
                "orderBy": "modifiedTime desc",
            }),
        ],
    )
    return [
        f for f in (found.get("files") or [])
        if f.get("name", "").startswith(("refined-", "video-refined-"))
        or f.get("name", "").endswith((".json", ".md"))
    ]


def download_refined(
    file_id: str,
    dest_dir: Optional[Path] = None,
    runner: Optional[Runner] = None,
) -> Path:
    """Download one refined file from Drive. Returns the local path."""
    dest = Path(dest_dir) if dest_dir else (REGISTRY_DIR / "refined")
    dest.mkdir(parents=True, exist_ok=True)
    local = dest / f"{file_id}.json"
    if runner is not None:
        # fake runner path for tests: runner returns {"content": "..."}
        res = _run(runner, ["download", file_id])
        local.write_text(res.get("content", ""), encoding="utf-8")
        return local
    meta = _run(
        ["hatch_gws_cli", "drive", "files", "get",
         "--params", json.dumps({"fileId": file_id, "fields": "name,mimeType"})],
    )
    name = meta.get("name", f"{file_id}.json")
    local = dest / name
    # media download via files get with alt=media
    proc = subprocess.run(
        ["hatch_gws_cli", "drive", "files", "get",
         "--params", json.dumps({"fileId": file_id, "alt": "media"}),
         "-o", str(local)],
        capture_output=True, timeout=120,
    )
    if proc.returncode != 0:
        raise DriveError(f"download failed for {file_id}: {proc.stderr.decode()[:200]}")
    return local
