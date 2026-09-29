"""Intake connector — the staging ear on a drop folder.

Where the ``directory`` connector reports *what changed*, the intake
connector reports *what arrived and is still waiting*: one
``intake_candidate`` event per file the drop folder holds that no earlier
poll has seen. Seen files never re-emit — intake is one-shot, so the
Archive port can claim candidates without double-archiving.

Event shape::

    {"kind": "intake_candidate",
     "path": "<relative to the intake root>",
     "bytes": <int>,
     "sha256": "<hex>",
     "sniff": "empty" | "text" | "binary",
     "head": "<first line of text, <= 120 chars, else ''>",
     "quarantine": None | {"reason": "oversize" | "unreadable"}}

Deny-closed:

- the path must exist and be a directory
- the real (symlink-resolved) path must sit under one of
  ``allowed_roots`` (default: the user's home directory)
- symlinks inside the tree are resolved and re-checked — a link
  escaping the allowed roots is skipped, never read
- more than ``max_files`` (default 5000) files is refused, never
  half-walked
- a file larger than ``max_bytes`` is still *reported* — honest intake
  never silently drops — but carries ``quarantine: {"reason": "oversize"}``

The caller holds the ``state`` (relpath -> sha256) between polls; the
connector keeps nothing. Observe-only: intake never moves, renames,
claims, or deletes anything.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_DEFAULT_MAX_FILES = 5000
_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB — candidates are triage, not blobs
_SNIFF_BYTES = 8192
_HEAD_CHARS = 120


def _allowed_roots(raw: Any) -> List[Path]:
    home = Path.home().resolve()
    if raw is None:
        return [home]
    if not isinstance(raw, (list, tuple)):
        raise ConnectorError("intake: 'allowed_roots' must be a list of paths")
    roots = []
    for r in raw:
        p = Path(os.path.expanduser(str(r))).resolve()
        if not p.is_dir():
            raise ConnectorError(f"intake: allowed root '{r}' is not a directory")
        roots.append(p)
    return roots or [home]


def _under_roots(real: Path, roots: List[Path]) -> bool:
    return any(real == r or r in real.parents for r in roots)


def _sniff(data: bytes) -> Tuple[str, str]:
    """Return (sniff, head) for a file's leading bytes."""
    if not data:
        return "empty", ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "binary", ""
    head = text.splitlines()[0] if text.splitlines() else ""
    return "text", head[:_HEAD_CHARS]


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def poll_intake(
    path: Any,
    state: Optional[Dict[str, str]] = None,
    allowed_roots: Any = None,
    max_bytes: Any = _DEFAULT_MAX_BYTES,
    max_files: Any = _DEFAULT_MAX_FILES,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Poll an intake drop folder for new arrivals.

    Returns ``(events, new_state)`` per the connector contract.
    ``state`` maps relpath -> sha256 of files already reported.
    """
    if path is None or not str(path):
        raise ConnectorError("intake: 'path' is required")
    root = Path(os.path.expanduser(str(path))).resolve()
    if not root.is_dir():
        raise ConnectorError(f"intake: '{path}' is not a directory")
    roots = _allowed_roots(allowed_roots)
    if not _under_roots(root, roots):
        raise ConnectorError(f"intake: '{path}' is outside the allowed roots")

    try:
        max_files_n = int(max_files)
    except (TypeError, ValueError):
        raise ConnectorError("intake: 'max_files' must be an integer") from None
    try:
        max_bytes_n = int(max_bytes)
    except (TypeError, ValueError):
        raise ConnectorError("intake: 'max_bytes' must be an integer") from None
    if max_files_n <= 0:
        raise ConnectorError("intake: 'max_files' must be positive")
    if max_bytes_n <= 0:
        raise ConnectorError("intake: 'max_bytes' must be positive")

    prev: Dict[str, str] = dict(state or {})
    current: Dict[str, str] = {}
    events: List[Dict[str, Any]] = []

    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        # Keep the walk inside the roots: prune any directory whose real
        # path escapes, and never follow a symlink that escapes.
        real_dir = Path(dirpath).resolve()
        if not _under_roots(real_dir, roots):
            dirnames[:] = []
            continue
        kept = []
        for d in dirnames:
            real_sub = (real_dir / d).resolve()
            if _under_roots(real_sub, roots):
                kept.append(d)
        dirnames[:] = kept
        for name in sorted(filenames):
            count += 1
            if count > max_files_n:
                raise ConnectorError(
                    f"intake: more than {max_files_n} files — refused, not half-walked"
                )
            fpath = real_dir / name
            real_file = fpath.resolve()
            if not _under_roots(real_file, roots) or not real_file.is_file():
                continue
            rel = str(real_file.relative_to(root))
            try:
                size = real_file.stat().st_size
                digest = _sha256_of(real_file)
            except OSError:
                # Unreadable files are reported, not dropped — quarantined.
                current[rel] = "unreadable"
                events.append(
                    {
                        "kind": "intake_candidate",
                        "path": rel,
                        "bytes": -1,
                        "sha256": "",
                        "sniff": "binary",
                        "head": "",
                        "quarantine": {"reason": "unreadable"},
                    }
                )
                continue
            current[rel] = digest
            if rel in prev:
                continue  # already reported — intake is one-shot
            quarantine = None
            sniff, head = "binary", ""
            if size > max_bytes_n:
                quarantine = {"reason": "oversize"}
            else:
                try:
                    with real_file.open("rb") as fh:
                        sniff, head = _sniff(fh.read(_SNIFF_BYTES))
                except OSError:
                    quarantine = {"reason": "unreadable"}
            events.append(
                {
                    "kind": "intake_candidate",
                    "path": rel,
                    "bytes": size,
                    "sha256": digest,
                    "sniff": sniff,
                    "head": head,
                    "quarantine": quarantine,
                }
            )
    return events, current


INTAKE_CONNECTOR = Connector(
    id="intake",
    name="Intake",
    description=(
        "Polls a drop folder and emits one intake_candidate event per "
        "newly arrived file (sha256, content sniff, quarantine verdict); "
        "seen files never re-emit. Paths are deny-closed under the "
        "allowed roots (default: home)."
    ),
    inputs=("path", "state", "allowed_roots", "max_bytes", "max_files"),
    poll=poll_intake,
)

registry.register(INTAKE_CONNECTOR)
