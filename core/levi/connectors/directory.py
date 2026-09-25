"""Directory connector — the ear on a local folder.

Polls a local directory and emits one event per changed file since the
last poll::

    {"kind": "added" | "modified" | "removed",
     "path": "<relative to the watched root>",
     "size": <bytes>, "mtime": <epoch seconds>}

The caller holds the ``state`` (a snapshot: relpath -> [size, mtime_ns])
between polls; the connector is stateless. Only reads — it never
writes, moves, or deletes anything in the watched tree.

Deny-closed paths
-----------------
- the path must exist and be a directory
- the real (symlink-resolved) path must sit under one of
  ``allowed_roots`` (default: the user's home directory)
- symlinks inside the tree are followed, then re-checked against the
  allowed roots — a link pointing outside the roots is skipped, never read
- more than ``max_files`` (default 5000) files is refused rather than
  half-walked
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_DEFAULT_MAX_FILES = 5000


def _allowed_roots(raw: Any) -> List[Path]:
    home = Path.home().resolve()
    if raw is None:
        return [home]
    if not isinstance(raw, (list, tuple)):
        raise ConnectorError("directory: 'allowed_roots' must be a list of paths")
    roots = []
    for r in raw:
        p = Path(os.path.expanduser(str(r))).resolve()
        if not p.is_dir():
            raise ConnectorError(f"directory: allowed root '{r}' is not a directory")
        roots.append(p)
    return roots or [home]


def _guarded_root(path: Path, roots: List[Path]) -> Path:
    real = path.resolve()
    if not real.is_dir():
        raise ConnectorError(f"directory: '{path}' is not a directory")
    if not any(real == r or r in real.parents for r in roots):
        raise ConnectorError(f"directory: '{path}' resolves outside the allowed roots")
    return real


def _walk(root: Path, roots: List[Path], max_files: int) -> Dict[str, List[int]]:
    snapshot: Dict[str, List[int]] = {}
    count = 0
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
        for name in filenames:
            full = Path(dirpath) / name
            try:
                real = full.resolve()
            except OSError:
                continue
            # A symlink escaping the allowed roots is skipped, never read.
            if not any(real == r or r in real.parents for r in roots):
                continue
            try:
                st = real.stat()
            except OSError:
                continue
            count += 1
            if count > max_files:
                raise ConnectorError(
                    f"directory: more than {max_files} files under '{root}' — "
                    "refused rather than half-walked"
                )
            rel = str(full.relative_to(root))
            snapshot[rel] = [st.st_size, st.st_mtime_ns]
    return snapshot


def poll_directory(
    path: str,
    state: Dict[str, Any] | None = None,
    allowed_roots: List[str] | None = None,
    max_files: int = _DEFAULT_MAX_FILES,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not path or not isinstance(path, str):
        raise ConnectorError("directory: 'path' must be a non-empty string")
    if not isinstance(max_files, int) or isinstance(max_files, bool) or max_files < 1:
        raise ConnectorError("directory: 'max_files' must be a positive int")
    roots = _allowed_roots(allowed_roots)
    root = _guarded_root(Path(os.path.expanduser(path)), roots)

    prev: Dict[str, List[int]] = {}
    for k, v in (state or {}).items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            prev[str(k)] = [int(v[0]), int(v[1])]

    current = _walk(root, roots, max_files)
    events: List[Dict[str, Any]] = []
    for rel in sorted(current):
        size, mtime_ns = current[rel]
        if rel not in prev:
            kind = "added"
        elif prev[rel] != [size, mtime_ns]:
            kind = "modified"
        else:
            continue
        events.append(
            {
                "kind": kind,
                "path": rel,
                "size": size,
                "mtime": mtime_ns / 1e9,
            }
        )
    for rel in sorted(set(prev) - set(current)):
        events.append({"kind": "removed", "path": rel, "size": 0, "mtime": 0.0})
    return events, {k: list(v) for k, v in current.items()}


DIRECTORY_CONNECTOR = Connector(
    id="directory",
    name="Directory",
    description=(
        "Polls a local directory for added / modified / removed files; "
        "paths are deny-closed under the allowed roots (default: home)."
    ),
    inputs=("path", "state", "allowed_roots", "max_files"),
    poll=poll_directory,
)

registry.register(DIRECTORY_CONNECTOR)
