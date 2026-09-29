"""Cron-map connector — the ear on scheduled-job changes.

Polls a local crontab file and emits one event per added or removed cron
entry; the first poll emits a single ``baseline`` event naming the entry
count — a watched crontab is never silently assumed. Observe-only: the
caller holds ``state`` between polls; the connector itself keeps nothing.

Entries are normalized cron lines: blank lines and ``#`` comments are
skipped. A valid entry is either a five-field schedule followed by a
command, or a ``@special`` name followed by a command. Anything else on
a non-comment, non-blank line (environment assignments, unparseable
lines) is *counted* but not watched — the baseline and any change in the
unparsed count say so honestly.

Laws
----
- observe-only: reads the crontab file; never writes, executes, or
  touches anything else
- honest baseline: the first poll (no state) emits a ``baseline`` event
  naming the entry count and the unparsed count — a watched crontab is
  never silently assumed
- edge-only: a steady crontab emits nothing; an added or removed entry
  emits exactly one event naming the entry and its line number

Deny-closed paths
-----------------
- ``path`` must be a non-empty string naming a regular file
- the resolved path must sit under one of ``allowed_roots`` (default:
  the user's home directory); symlinks are resolved then re-checked
- unknown keyword inputs are refused, never ignored
- a ``state`` carrying a malformed entry table is refused, never guessed
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_TIME_FIELD = re.compile(r"^[0-9*,\-/]+$")
_SPECIALS = frozenset(
    {
        "@reboot",
        "@yearly",
        "@annually",
        "@monthly",
        "@weekly",
        "@daily",
        "@midnight",
        "@hourly",
    }
)


def _is_time_fields(fields: List[str]) -> bool:
    return len(fields) == 5 and all(bool(_TIME_FIELD.match(f)) for f in fields)


def parse_cron_entries(text: str) -> Tuple[List[Tuple[int, str]], int]:
    """Split crontab text into (line_no, entry) pairs plus an unparsed count.

    Blank lines and ``#`` comments are skipped silently. A line is an
    *entry* when it is a five-field schedule or ``@special`` followed by a
    command; anything else non-blank is counted as unparsed.
    """
    entries: List[Tuple[int, str]] = []
    unparsed = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if parts[0] in _SPECIALS:
            if len(parts) >= 2:
                entries.append((lineno, stripped))
            else:
                unparsed += 1
            continue
        if len(parts) >= 6 and _is_time_fields(parts[:5]) and parts[5].strip():
            entries.append((lineno, stripped))
        else:
            unparsed += 1
    return entries, unparsed


def _fingerprint(entry: str) -> str:
    return hashlib.sha256(entry.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _validate_path(path: Any, allowed_roots: Any) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ConnectorError("cronmap: 'path' must be a non-empty string")
    roots_list: List[str]
    if allowed_roots is None:
        roots_list = [str(Path.home())]
    elif isinstance(allowed_roots, (list, tuple)) and allowed_roots:
        roots_list = list(allowed_roots)
    else:
        raise ConnectorError(
            "cronmap: 'allowed_roots' must be a non-empty list of paths"
        )
    resolved_roots = []
    for root in roots_list:
        if not isinstance(root, str) or not root.strip():
            raise ConnectorError("cronmap: 'allowed_roots' must hold non-empty strings")
        resolved_roots.append(os.path.realpath(root))
    real = os.path.realpath(path.strip())
    if not any(
        real == root or real.startswith(root + os.sep) for root in resolved_roots
    ):
        raise ConnectorError(
            f"cronmap: path {real!r} is outside the allowed roots — refused"
        )
    candidate = Path(real)
    if not candidate.is_file():
        raise ConnectorError(f"cronmap: path {real!r} is not a regular file — refused")
    return candidate


def _validate_state(state: Any) -> Dict[str, Any] | None:
    if state is None:
        return None
    if not isinstance(state, dict):
        raise ConnectorError("cronmap: 'state' must be a dict or None — refused")
    entries = state.get("entries")
    unparsed = state.get("unparsed", 0)
    if not isinstance(entries, dict) or not isinstance(unparsed, int):
        raise ConnectorError("cronmap: malformed state — refused, never guessed")
    for _fp, rec in entries.items():
        if not isinstance(rec, dict) or "entry" not in rec or "line_no" not in rec:
            raise ConnectorError("cronmap: malformed state entries — refused")
    return state


# ---------------------------------------------------------------------------
# The poll
# ---------------------------------------------------------------------------


def poll_cronmap(
    path: str = "",
    state: Dict[str, Any] | None = None,
    allowed_roots: Any = None,
    **unknown: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll a crontab file for entry changes.

    ``state`` is the previous ``{"entries": {fp: {entry, line_no}},
    "unparsed": n}`` table (``None`` on first poll). Returns
    ``(events, new_state)`` per the connector contract.
    """
    if unknown:
        raise ConnectorError(
            f"cronmap: unknown inputs {sorted(unknown)} — refused, never ignored"
        )
    target = _validate_path(path, allowed_roots)
    prev = _validate_state(state)

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ConnectorError(f"cronmap: cannot read {target}: {exc}") from exc

    entries, unparsed = parse_cron_entries(text)
    new_table = {
        _fingerprint(entry): {"entry": entry, "line_no": lineno}
        for lineno, entry in entries
    }
    new_state: Dict[str, Any] = {"entries": new_table, "unparsed": unparsed}

    if prev is None:
        return (
            [
                {
                    "kind": "baseline",
                    "path": str(target),
                    "entries": len(entries),
                    "unparsed": unparsed,
                }
            ],
            new_state,
        )

    prev_table = prev["entries"]
    prev_unparsed = prev.get("unparsed", 0)
    events: List[Dict[str, Any]] = []
    for fp in sorted(set(new_table) - set(prev_table)):
        rec = new_table[fp]
        events.append(
            {
                "kind": "added",
                "path": str(target),
                "entry": rec["entry"],
                "line_no": rec["line_no"],
            }
        )
    for fp in sorted(set(prev_table) - set(new_table)):
        rec = prev_table[fp]
        events.append(
            {
                "kind": "removed",
                "path": str(target),
                "entry": rec["entry"],
                "line_no": rec["line_no"],
            }
        )
    if unparsed != prev_unparsed:
        events.append(
            {
                "kind": "unparsed_changed",
                "path": str(target),
                "prev": prev_unparsed,
                "current": unparsed,
            }
        )
    return events, new_state


registry.register(
    Connector(
        id="cronmap",
        name="Cron Map",
        description="Polls a local crontab file and emits one event per "
        "added/removed cron entry (edge-only, honest baseline, "
        "unparsed lines counted, never watched). Observe-only; the "
        "caller holds the last entry table as state.",
        version="1.0.0",
        inputs=("path", "state", "allowed_roots"),
        risk="info",
        poll=poll_cronmap,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-cronmap",
            provides=("connector.cronmap.poll",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
