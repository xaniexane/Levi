"""Alpha artifact materialization: from ``{path: content}`` to real files, safely.

Companion to ``generators`` (Alpha's no-code compiler): that module hands
back artifacts as an in-memory ``{path: content}`` map and deliberately
never touches disk. This module is the other half of Alpha — the safe
writer that lays those artifacts down:

- ``preview`` — look at what's coming. Pure function, no I/O, LEVI's voice.
- ``plan`` — per-file verdicts: ``write`` | ``skip-existing`` | ``blocked``.
- ``write`` — the gated writer. Refuses to touch disk without
  ``approve=True``, refuses to overwrite existing files without
  ``overwrite=True``, stages every file atomically (temp file + rename,
  so a crash never leaves a torn file), then re-reads every written
  file and byte-compares plus sha256. Returns a signed receipt.
- ``verify`` — re-check a receipt (or a files map) against disk at any
  later time; catches tamper-after-write.

Safety is the whole point of this module: every path is resolved against
``dest`` and anything that escapes it — absolute paths, ``..`` segments,
symlink tricks — is refused as ``blocked``. Nothing ever lands outside
``dest``, and nothing lands at all without your explicit say-so.

Stdlib only. Pure LEVI.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival-omega/materialize"

ACTION_WRITE = "write"
ACTION_SKIP_EXISTING = "skip-existing"
ACTION_BLOCKED = "blocked"


# --------------------------------------------------------------------------
# validation (honest errors)
# --------------------------------------------------------------------------


def _validate_files(files: object, *, allow_empty: bool = False) -> Dict[str, str]:
    if not isinstance(files, dict):
        raise ValueError(
            f"files must be a dict of {{path: content}}, got {type(files).__name__}"
        )
    if not files and not allow_empty:
        raise ValueError("files is empty: nothing to materialize")
    for path, content in files.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"file paths must be non-empty strings, got {path!r}")
        if not isinstance(content, str):
            raise ValueError(
                f"content for {path!r} must be str, got {type(content).__name__}"
            )
    return files


def _resolve_dest(dest: object) -> str:
    if not isinstance(dest, str) or not dest:
        raise ValueError(f"unknown dest: {dest!r} — give me a real directory")
    if not os.path.isdir(dest):
        raise ValueError(f"unknown dest: {dest!r} — not an existing directory")
    return os.path.realpath(dest)


def _safe_target(base: str, path: str) -> Optional[str]:
    """Resolve ``path`` inside ``base``; return ``None`` if it escapes.

    Catches absolute paths, ``..`` segments, and symlink tricks by
    resolving with ``realpath`` and requiring the result to stay under
    ``base``.
    """
    if os.path.isabs(path):
        return None
    target = os.path.realpath(os.path.join(base, path))
    if target == base or not target.startswith(base + os.sep):
        return None
    return target


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


# --------------------------------------------------------------------------
# preview — pure, no I/O
# --------------------------------------------------------------------------


def preview(files: Dict[str, str], max_lines: int = 40) -> str:
    """Render a human-readable preview of the artifacts, in LEVI's voice.

    Pure function: reads nothing, writes nothing. Shows each path plus its
    first ``max_lines`` lines of content.
    """
    files = _validate_files(files, allow_empty=True)
    if not files:
        return "Nothing to preview — the files map is empty.\n"
    lines = [
        f"LEVI's materializer is holding {_plural(len(files), 'artifact')}, "
        "ready to land:",
        "",
    ]
    for path, content in files.items():
        content_lines = content.splitlines()
        total = len(content_lines)
        lines.append(f"  ▸ {path}  ({_plural(total, 'line')})")
        for text in content_lines[:max_lines]:
            lines.append(f"    {text}")
        if total > max_lines:
            lines.append(f"    … {_plural(total - max_lines, 'more line')}")
        lines.append("")
    lines.append(
        "Say the word: plan() maps where each one lands, "
        "write(..., approve=True) lays them down."
    )
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# plan — per-file verdicts
# --------------------------------------------------------------------------


def plan(files: Dict[str, str], dest: str) -> Dict[str, object]:
    """Decide what each artifact would do at ``dest``.

    Returns ``{"dest", "files", "entries"}`` where ``entries`` is a list of
    ``{path, action, reason}`` with action one of ``write``,
    ``skip-existing``, ``blocked``. The embedded ``files`` map lets the
    result be handed straight to ``write()``.
    """
    files = _validate_files(files)
    base = _resolve_dest(dest)
    entries: List[Dict[str, str]] = []
    for path in files:
        target = _safe_target(base, path)
        if target is None:
            entries.append(
                {
                    "path": path,
                    "action": ACTION_BLOCKED,
                    "reason": (
                        "escapes the destination "
                        "(absolute path, '..' segment, or symlink trick) — refused"
                    ),
                }
            )
        elif os.path.exists(target):
            entries.append(
                {
                    "path": path,
                    "action": ACTION_SKIP_EXISTING,
                    "reason": "already exists — pass overwrite=True to replace it",
                }
            )
        else:
            entries.append(
                {
                    "path": path,
                    "action": ACTION_WRITE,
                    "reason": "new file inside the destination",
                }
            )
    return {"dest": base, "files": dict(files), "entries": entries}


# --------------------------------------------------------------------------
# write — the gated writer + post-write verification
# --------------------------------------------------------------------------


def _normalize_write_input(files_or_plan: object) -> Dict[str, str]:
    if isinstance(files_or_plan, dict) and isinstance(
        files_or_plan.get("entries"), list
    ):
        return _validate_files(files_or_plan.get("files"))
    return _validate_files(files_or_plan)


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def write(
    files_or_plan: object,
    dest: str,
    *,
    approve: bool = False,
    overwrite: bool = False,
) -> Dict[str, object]:
    """Lay the artifacts down at ``dest`` and verify them.

    ``files_or_plan`` is either the raw ``{path: content}`` map or a plan
    dict as returned by ``plan()``.

    Raises ``PermissionError`` unless ``approve=True`` — that gate is
    deliberate; nothing lands on disk without an explicit say-so. Existing
    files are refused unless ``overwrite=True``; they become ``skipped``
    entries, never clobbered by accident. Paths escaping ``dest`` are
    refused as ``blocked``.

    After writing, every file is re-read and byte-compared, with a sha256
    recorded per file. Writes are atomic (temp file + rename): a crash
    mid-write leaves no torn file at the target path. Returns the receipt::

        {"dest", "written": [{path, bytes, sha256}], "skipped": [{path, reason}],
         "verified": bool, "mismatches": [...], "atomic": True, "timestamp"}
    """
    if not approve:
        raise PermissionError(
            "materialize.write needs your say-so: pass approve=True. "
            "Nothing lands on disk without it — that's the law."
        )
    files = _normalize_write_input(files_or_plan)
    base = _resolve_dest(dest)

    written: List[Dict[str, object]] = []
    skipped: List[Dict[str, str]] = []
    staged: List[Tuple[str, str, bytes]] = []

    for path, content in files.items():
        target = _safe_target(base, path)
        if target is None:
            skipped.append(
                {
                    "path": path,
                    "reason": "blocked: path escapes the destination directory",
                }
            )
            continue
        if os.path.isdir(target):
            skipped.append(
                {
                    "path": path,
                    "reason": "blocked: an existing directory sits at that path",
                }
            )
            continue
        if os.path.exists(target) and not overwrite:
            skipped.append(
                {
                    "path": path,
                    "reason": "already exists: pass overwrite=True to replace it",
                }
            )
            continue
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = content.encode("utf-8")
        # Atomic staging: the bytes land on a temp file in the same
        # directory first, then os.replace() swaps it into place. A crash
        # mid-write can never leave a torn file at the target path — the
        # reader either sees the old file or the whole new one.
        fd, tmp_path = tempfile.mkstemp(
            dir=parent or base, prefix=".levi-materialize-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        staged.append((path, target, data))

    mismatches: List[Dict[str, object]] = []
    for path, target, data in staged:
        digest = hashlib.sha256(data).hexdigest()
        try:
            actual = _read_bytes(target)
        except OSError:
            actual = None
        if actual != data:
            mismatches.append(
                {
                    "path": path,
                    "reason": "post-write read-back mismatch",
                    "expected_sha256": digest,
                    "actual_sha256": (
                        hashlib.sha256(actual).hexdigest()
                        if actual is not None
                        else None
                    ),
                }
            )
        else:
            written.append({"path": path, "bytes": len(data), "sha256": digest})

    return {
        "dest": base,
        "written": written,
        "skipped": skipped,
        "verified": not mismatches,
        "mismatches": mismatches,
        "atomic": True,  # every write landed via temp-file + os.replace
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------
# verify — re-check a receipt (or files map) against disk
# --------------------------------------------------------------------------


def _expectations_from_receipt(
    receipt: Dict[str, object],
) -> List[Tuple[str, str, int]]:
    raw = receipt.get("written")
    if not isinstance(raw, list):
        raise ValueError("receipt 'written' must be a list of entries")
    expectations = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"receipt entry must be a dict, got {entry!r}")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError(f"receipt entry has a bad path: {entry!r}")
        expectations.append((path, entry.get("sha256"), entry.get("bytes")))
    return expectations


def verify(receipt_or_files: object, dest: str) -> Dict[str, object]:
    """Re-check artifacts on disk against a receipt or a files map.

    Accepts either a receipt as returned by ``write()`` (byte-compare via
    the recorded sha256) or the original ``{path: content}`` map (exact
    byte-compare against the content). Returns::

        {"verified": bool, "checked": int, "mismatches": [...]}

    Catches tamper-after-write: any file whose bytes changed, went
    missing, or whose path escapes ``dest`` shows up in ``mismatches``.
    """
    base = _resolve_dest(dest)
    if isinstance(receipt_or_files, dict) and isinstance(
        receipt_or_files.get("written"), list
    ):
        expectations = _expectations_from_receipt(receipt_or_files)
        files_map: Optional[Dict[str, str]] = None
    else:
        files_map = _validate_files(receipt_or_files)
        expectations = [
            (
                path,
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                len(content.encode("utf-8")),
            )
            for path, content in files_map.items()
        ]

    mismatches: List[Dict[str, object]] = []
    checked = 0
    for path, expected_sha, _expected_bytes in expectations:
        target = _safe_target(base, path)
        if target is None:
            mismatches.append(
                {
                    "path": path,
                    "reason": "blocked: path escapes the destination directory",
                }
            )
            continue
        if not os.path.isfile(target):
            mismatches.append({"path": path, "reason": "missing on disk"})
            continue
        actual = _read_bytes(target)
        actual_sha = hashlib.sha256(actual).hexdigest()
        expected_bytes = (
            files_map[path].encode("utf-8") if files_map is not None else None
        )
        ok = actual == expected_bytes if expected_bytes is not None else True
        if ok and actual_sha != expected_sha:
            ok = False
        checked += 1
        if not ok:
            mismatches.append(
                {
                    "path": path,
                    "reason": "content mismatch — tampered or replaced after write",
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                }
            )
    return {"verified": not mismatches, "checked": checked, "mismatches": mismatches}
