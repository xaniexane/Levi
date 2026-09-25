"""Chain-local storage: homes, append-only JSONL ledgers, owner-only files.

Everything here is offline and local. Receipts and permission tokens are
appended as one-JSON-per-line under ``<LEVI_HOME>/chain/``; files are
created (and kept) at mode 0600 so only the owner can read them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_HOME_T = Union[str, os.PathLike, None]


def chain_home(home: _HOME_T = None) -> Path:
    """Resolve ``<LEVI_HOME>/chain`` at call time (hermetic).

    ``LEVI_HOME`` wins; otherwise ``~/.levi``. An explicit ``home``
    argument overrides both — tests pin it to a tmp dir.
    """
    if home is not None:
        base = Path(home)
    else:
        override = os.environ.get("LEVI_HOME")
        base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "chain"


def receipts_path(home: _HOME_T = None) -> Path:
    """Path of the append-only chain receipt ledger."""
    return chain_home(home) / "receipts.jsonl"


def permissions_path(home: _HOME_T = None) -> Path:
    """Path of the append-only permission-token ledger."""
    return chain_home(home) / "permissions.jsonl"


def _append_jsonl(path: Path, record: Dict[str, Any]) -> Path:
    """Append one JSON record to ``path``, keeping the file at mode 0600.

    The file is created with 0600 via ``os.open`` so there is no window
    where it is world-readable; ``os.chmod`` afterwards hardens the case
    where the file already existed with looser bits.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, default=str) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line)
    finally:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def append_receipt(record: Dict[str, Any], home: _HOME_T = None) -> Path:
    """Append a link receipt to the receipt ledger. Returns the ledger path."""
    return _append_jsonl(receipts_path(home), record)


def append_permission(record: Dict[str, Any], home: _HOME_T = None) -> Path:
    """Append a permission token to the permission ledger."""
    return _append_jsonl(permissions_path(home), record)


def _read_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a corrupt line never breaks the ledger read
    except OSError:
        return []
    if limit is not None:
        out = out[-limit:]
    return out


def read_receipts(
    home: _HOME_T = None, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Read link receipts from the ledger, oldest first (tail with ``limit``)."""
    return _read_jsonl(receipts_path(home), limit)


def read_permissions(home: _HOME_T = None) -> List[Dict[str, Any]]:
    """Read recorded permission tokens, oldest first."""
    return _read_jsonl(permissions_path(home))
