"""Versioned artifact store: immutable versions, diff views, full export.

Model:

- An **artifact** has an id, a type (``doc`` | ``code`` | ``plan``), a
  title, and an ordered list of **versions**.
- A **version** is immutable: ``{n, created_at, content, note}``. Editing
  never rewrites history — it appends version n+1.
- ``diff(a, b)`` renders a unified diff via stdlib :mod:`difflib`.
- :func:`export_artifact` packs EVERY version plus ``manifest.json``
  into a ``.tar.gz`` — the whole history leaves LEVI in open formats.

Storage: ``<home>/<artifact-id>/`` with ``meta.json`` and
``v0001.txt``, ``v0002.txt``, ... (content stored raw so any tool can
read it; the extension hints the type: doc→.md, code→.txt, plan→.md).
"""

from __future__ import annotations

import difflib
import io
import json
import os
import re
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "CanvasError",
    "ArtifactStore",
    "default_home",
    "ARTIFACT_TYPES",
    "FORMAT",
]

ARTIFACT_TYPES = ("doc", "code", "plan")
FORMAT = "levi-canvas/1"
VALID_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_TYPE_EXT = {"doc": ".md", "code": ".txt", "plan": ".md"}


class CanvasError(Exception):
    """Canvas operation failed."""


def default_home() -> Path:
    override = os.environ.get("LEVI_HOME")
    base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "canvas"


def _check_id(artifact_id: str) -> str:
    if not isinstance(artifact_id, str) or not VALID_ID_RE.fullmatch(artifact_id):
        raise CanvasError(
            f"invalid artifact id {artifact_id!r}: 1-64 chars of [A-Za-z0-9_-]"
        )
    return artifact_id


class ArtifactStore:
    """Versioned artifacts under one home directory."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass

    # -- internal ------------------------------------------------------
    def _dir(self, artifact_id: str) -> Path:
        return self.home / _check_id(artifact_id)

    def _meta_path(self, artifact_id: str) -> Path:
        return self._dir(artifact_id) / "meta.json"

    def _read_meta(self, artifact_id: str) -> Dict[str, Any]:
        path = self._meta_path(artifact_id)
        if not path.exists():
            raise CanvasError(f"unknown artifact {artifact_id!r}")
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CanvasError(
                f"artifact {artifact_id!r}: meta.json unreadable ({exc})"
            ) from exc
        if not isinstance(meta, dict) or "versions" not in meta:
            raise CanvasError(f"artifact {artifact_id!r}: meta.json malformed")
        return meta

    def _write_meta(self, artifact_id: str, meta: Dict[str, Any]) -> None:
        path = self._meta_path(artifact_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _version_file(self, artifact_id: str, n: int, atype: str) -> Path:
        return self._dir(artifact_id) / f"v{n:04d}{_TYPE_EXT.get(atype, '.txt')}"

    # -- lifecycle -----------------------------------------------------
    def create(
        self,
        artifact_id: str,
        atype: str,
        title: str,
        content: str = "",
        note: str = "created",
    ) -> Dict[str, Any]:
        _check_id(artifact_id)
        if atype not in ARTIFACT_TYPES:
            raise CanvasError(
                f"unknown artifact type {atype!r} (known: {ARTIFACT_TYPES})"
            )
        if self._dir(artifact_id).exists():
            raise CanvasError(f"artifact {artifact_id!r} already exists")
        if not isinstance(title, str) or not title.strip():
            raise CanvasError("title must be a non-empty string")
        self._dir(artifact_id).mkdir(parents=True)
        meta = {
            "id": artifact_id,
            "type": atype,
            "title": title.strip(),
            "created_at": time.time(),
            "versions": [],
        }
        self._write_meta(artifact_id, meta)
        self.edit(artifact_id, content, note=note)
        return self._read_meta(artifact_id)

    def edit(self, artifact_id: str, content: str, note: str = "") -> int:
        """Append a new immutable version. Returns the version number."""
        if not isinstance(content, str):
            raise CanvasError("content must be a string")
        meta = self._read_meta(artifact_id)
        n = len(meta["versions"]) + 1
        self._version_file(artifact_id, n, meta["type"]).write_text(
            content, encoding="utf-8"
        )
        meta["versions"].append(
            {"n": n, "created_at": time.time(), "note": note, "chars": len(content)}
        )
        meta["updated_at"] = time.time()
        self._write_meta(artifact_id, meta)
        return n

    def get(self, artifact_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        meta = self._read_meta(artifact_id)
        versions = meta["versions"]
        if not versions:
            raise CanvasError(f"artifact {artifact_id!r} has no versions")
        n = version if version is not None else versions[-1]["n"]
        rec = next((v for v in versions if v["n"] == n), None)
        if rec is None:
            raise CanvasError(
                f"artifact {artifact_id!r} has no version {n} "
                f"(has 1..{versions[-1]['n']})"
            )
        content = self._version_file(artifact_id, n, meta["type"]).read_text(
            encoding="utf-8"
        )
        return {
            "id": artifact_id,
            "type": meta["type"],
            "title": meta["title"],
            "version": rec,
            "content": content,
        }

    def versions(self, artifact_id: str) -> List[Dict[str, Any]]:
        return list(self._read_meta(artifact_id)["versions"])

    def diff(self, artifact_id: str, a: int, b: int) -> str:
        """Unified diff between two versions (stdlib difflib)."""
        ca = self.get(artifact_id, a)["content"].splitlines()
        cb = self.get(artifact_id, b)["content"].splitlines()
        meta = self._read_meta(artifact_id)
        lines = list(
            difflib.unified_diff(
                ca,
                cb,
                fromfile=f"{artifact_id}@v{a}",
                tofile=f"{artifact_id}@v{b}",
                lineterm="",
            )
        )
        return "\n".join(lines) if lines else "(no differences)"

    def rename(self, artifact_id: str, title: str) -> None:
        meta = self._read_meta(artifact_id)
        if not isinstance(title, str) or not title.strip():
            raise CanvasError("title must be a non-empty string")
        meta["title"] = title.strip()
        self._write_meta(artifact_id, meta)

    def delete(self, artifact_id: str) -> bool:
        target = self._dir(artifact_id)
        if not target.is_dir():
            return False
        import shutil

        shutil.rmtree(target)
        return True

    def list(self) -> List[Dict[str, Any]]:
        out = []
        if not self.home.is_dir():
            return out
        for p in sorted(self.home.iterdir()):
            if p.is_dir() and VALID_ID_RE.fullmatch(p.name):
                try:
                    meta = self._read_meta(p.name)
                except CanvasError:
                    continue
                out.append(
                    {
                        "id": meta["id"],
                        "type": meta["type"],
                        "title": meta["title"],
                        "versions": len(meta["versions"]),
                        "updated_at": meta.get("updated_at", meta.get("created_at")),
                    }
                )
        return out

    # -- export ----------------------------------------------------------
    def export(self, artifact_id: str, dest: Path) -> Path:
        """Export EVERY version + manifest.json into a .tar.gz bundle."""
        meta = self._read_meta(artifact_id)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "format": FORMAT,
            "id": meta["id"],
            "type": meta["type"],
            "title": meta["title"],
            "exported_at": time.time(),
            "versions": meta["versions"],
        }
        with tarfile.open(dest, "w:gz") as tf:
            data = json.dumps(manifest, indent=2).encode("utf-8")
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mtime = len(data), int(time.time())
            tf.addfile(info, io.BytesIO(data))
            for v in meta["versions"]:
                vf = self._version_file(artifact_id, v["n"], meta["type"])
                arcname = f"versions/v{v['n']:04d}{_TYPE_EXT.get(meta['type'], '.txt')}"
                info = tarfile.TarInfo(arcname)
                raw = vf.read_bytes()
                info.size, info.mtime = len(raw), int(v["created_at"])
                tf.addfile(info, io.BytesIO(raw))
        return dest
