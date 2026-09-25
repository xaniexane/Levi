"""Shared JSON-store persistence for the methods package (private helper).

Every method that persists state stores JSON under ``~/.levi/methods/``.
Rules:

- Corrupt JSON is never silently absorbed: the file is moved aside to
  ``<name>.corrupt-<unix-ts>.json`` (quarantined) and a
  :class:`CorruptStoreError` is raised. The caller sees the failure and the
  data is preserved for forensics.
- Writes are atomic: write to a temp file in the same directory, then rename.
- ``LEVI_HOME`` overrides the home directory (used by hermetic tests).
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


class CorruptStoreError(Exception):
    """Raised when a persisted store cannot be parsed. The bad file has been
    quarantined to ``<name>.corrupt-<ts>.json`` beside the original path."""


def base_dir() -> Path:
    home = os.environ.get("LEVI_HOME")
    root = Path(home).expanduser() if home else Path.home()
    d = root / ".levi" / "methods"
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"refusing unsafe store name: {name!r}")
    return base_dir() / f"{name}.json"


def load_json(path: Path):
    """Load a JSON store. Quarantines corrupt files and raises."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        stamp = int(time.time())
        quarantine = path.with_name(f"{path.stem}.corrupt-{stamp}.json")
        try:
            shutil.move(str(path), str(quarantine))
        except OSError:
            quarantine = None
        raise CorruptStoreError(
            f"store {path} is corrupt and was quarantined"
            + (f" at {quarantine}" if quarantine else "")
        ) from exc


def save_json(path: Path, data) -> None:
    """Atomically write a JSON store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)
