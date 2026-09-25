"""Log-tail connector — the ear on a local log file.

Polls a local text file and emits one event per new line since the last
poll::

    {"kind": "line", "line_no": <int>, "text": "<the line, truncated>",
     "path": "<absolute path>"}

The caller holds the ``state`` (a byte offset, the file's identity, and
the last line number) between polls; the connector itself keeps nothing.
Only reads — it never writes, truncates, or rotates the tailed file.

Rotation / replacement is handled honestly, never half-read: if the file
was replaced (inode changed) or shrank (size < remembered offset), the
poll emits a single ``{"kind": "rotated"}`` event and re-baselines at the
start of the new file.

Deny-closed paths
-----------------
- the path must exist and be a regular file
- the real (symlink-resolved) path must sit under one of
  ``allowed_roots`` (default: the user's home directory)
- more than ``max_lines`` (default 500) new lines is refused rather than
  flooding the caller
- lines longer than ``max_line_chars`` (default 1000) are truncated, never
  refused
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_DEFAULT_MAX_LINES = 500
_DEFAULT_MAX_LINE_CHARS = 1000


def _allowed_roots(raw: Any) -> List[Path]:
    home = Path.home().resolve()
    if raw is None:
        return [home]
    if not isinstance(raw, (list, tuple)):
        raise ConnectorError("logtail: 'allowed_roots' must be a list of paths")
    roots = []
    for r in raw:
        p = Path(os.path.expanduser(str(r))).resolve()
        if not p.is_dir():
            raise ConnectorError(f"logtail: allowed root '{r}' is not a directory")
        roots.append(p)
    return roots or [home]


def _guarded_file(path: Any, roots: List[Path]) -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise ConnectorError("logtail: 'path' must be a string path")
    real = Path(os.path.expanduser(str(path))).resolve()
    if not real.is_file():
        raise ConnectorError(f"logtail: '{path}' is not a file")
    if not any(real == r or r in real.parents for r in roots):
        raise ConnectorError(f"logtail: '{path}' resolves outside the allowed roots")
    return real


def _read_new_lines(
    real: Path, offset: int, max_lines: int, max_chars: int
) -> Tuple[List[Tuple[int, str]], int]:
    """(new (rel_line_no, text) pairs, new offset) reading forward from *offset*."""
    with real.open("rb") as fh:
        fh.seek(offset)
        raw = fh.read()
        new_offset = fh.tell()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        raise ConnectorError(
            f"logtail: {len(lines)} new lines exceeds max_lines={max_lines}; "
            "refused rather than flooding"
        )
    return [(i, line[:max_chars]) for i, line in enumerate(lines)], new_offset


def poll_logtail(
    path: Any,
    allowed_roots: Any = None,
    max_lines: int = _DEFAULT_MAX_LINES,
    max_line_chars: int = _DEFAULT_MAX_LINE_CHARS,
    state: Dict[str, Any] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll one local log file; see module docstring for the contract."""
    if not isinstance(max_lines, int) or max_lines <= 0:
        raise ConnectorError("logtail: 'max_lines' must be a positive int")
    if not isinstance(max_line_chars, int) or max_line_chars <= 0:
        raise ConnectorError("logtail: 'max_line_chars' must be a positive int")
    state = dict(state or {})
    roots = _allowed_roots(allowed_roots)
    real = _guarded_file(path, roots)
    st = real.stat()
    identity = (st.st_ino, st.st_dev)
    size = st.st_size

    last_identity = state.get("identity")
    last_offset = int(state.get("offset", 0) or 0)
    last_line = int(state.get("line_no", 0) or 0)

    if last_identity is not None and (
        tuple(last_identity) != identity or size < last_offset
    ):
        # Rotated or replaced: say so honestly, re-baseline at byte zero.
        new_state = {"offset": 0, "identity": list(identity), "line_no": 0}
        events: List[Dict[str, Any]] = [
            {"kind": "rotated", "path": str(real), "line_no": 0}
        ]
        return events, new_state

    new_lines, new_offset = _read_new_lines(
        real, last_offset, max_lines, max_line_chars
    )
    events = [
        {
            "kind": "line",
            "line_no": last_line + i + 1,
            "text": line,
            "path": str(real),
        }
        for i, line in new_lines
    ]
    new_state = {
        "offset": new_offset,
        "identity": list(identity),
        "line_no": last_line + len(new_lines),
    }
    return events, new_state


registry.register(
    Connector(
        id="logtail",
        name="Log Tail",
        description="Emits one event per new line appended to a local log "
        "file; rotation is reported honestly and re-baselined.",
        version="1.0.0",
        inputs=("path", "allowed_roots", "max_lines", "max_line_chars", "state"),
        risk="info",
        poll=poll_logtail,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-logtail",
            provides=("connector.logtail.poll", "connector.logtail.cli"),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
