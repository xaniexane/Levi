"""One-command export: the finished project as a tarball/zip you own.

Differentiator: full export, no lock-in, no account. Take the tarball
anywhere and keep building with any team, any tools.
"""

from __future__ import annotations

import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _iter_members(project_dir: Path):
    """Yield (arcname, fullpath) for everything shippable.

    Excludes runtime artifacts: the SQLite database, caches, and the
    export directory itself.
    """
    skip_dirs = {"__pycache__", ".git", "exports"}
    skip_suffixes = {".pyc", ".db", ".db-journal", ".sqlite3"}
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if path.suffix in skip_suffixes:
            continue
        yield rel.as_posix(), path


def export_project(
    project_dir: Path, dest_dir: Path | None = None, fmt: str = "tar.gz"
) -> Path:
    """Export ``project_dir`` to a tarball (default) or zip.

    Returns the path of the created archive. The archive's top level is
    the project directory name, so it unpacks cleanly anywhere.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise ValueError(f"not a directory: {project_dir}")
    if fmt not in ("tar.gz", "zip"):
        raise ValueError(f"unknown format {fmt!r}; choices: tar.gz, zip")

    dest_dir = Path(dest_dir) if dest_dir else (project_dir / "exports")
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = dest_dir / f"{project_dir.name}-{stamp}.{fmt}"

    if fmt == "tar.gz":
        with tarfile.open(archive, "w:gz") as tar:
            for arcname, full in _iter_members(project_dir):
                # Don't pack the exports dir into itself.
                if arcname.startswith("exports/"):
                    continue
                tar.add(full, arcname=f"{project_dir.name}/{arcname}")
    else:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, full in _iter_members(project_dir):
                if arcname.startswith("exports/"):
                    continue
                zf.write(full, arcname=f"{project_dir.name}/{arcname}")
    return archive
