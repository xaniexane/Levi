"""Disk-watch connector — the ear on local disk health.

Polls ``shutil.disk_usage`` for a path and emits one event per band
change::

    {"kind": "baseline" | "band_changed",
     "band": "ok" | "warn" | "crit",
     "prev_band": <band | None>,
     "used_pct": <float>, "free_bytes": <int>, "total_bytes": <int>,
     "path": "<absolute path>"}

Bands come from ``warn_pct`` (default 80) and ``crit_pct`` (default 95):
used% below warn → ``ok``; below crit → ``warn``; at/above crit →
``crit``. The caller holds ``state`` (the last band) between polls; the
connector itself keeps nothing.

Laws
----
- observe-only: reads ``shutil.disk_usage``; never writes, deletes, or
  touches the watched path
- honest baseline: the first poll (no state) emits a ``baseline`` event
  naming the current band — a watched disk is never silently assumed
- edge-only: a steady band emits nothing; a band change — including
  recovery back to ``ok`` — emits exactly one event

Deny-closed paths
-----------------
- ``path`` must exist (any file or directory — disk usage is per volume)
- ``0 < warn_pct < crit_pct < 100``, else refused
- a ``state`` carrying an unknown band is refused, never guessed
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_BANDS = ("ok", "warn", "crit")
_DEFAULT_WARN_PCT = 80.0
_DEFAULT_CRIT_PCT = 95.0


def _guarded_path(path: Any) -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise ConnectorError("diskwatch: 'path' must be a string path")
    real = Path(os.path.expanduser(str(path))).resolve()
    if not real.exists():
        raise ConnectorError(f"diskwatch: '{path}' does not exist")
    return real


def _guarded_thresholds(warn_pct: Any, crit_pct: Any) -> Tuple[float, float]:
    for name, value in (("warn_pct", warn_pct), ("crit_pct", crit_pct)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConnectorError(f"diskwatch: '{name}' must be a number")
    warn, crit = float(warn_pct), float(crit_pct)
    if not 0.0 < warn < crit < 100.0:
        raise ConnectorError(
            "diskwatch: need 0 < warn_pct < crit_pct < 100, "
            f"got warn_pct={warn_pct} crit_pct={crit_pct}"
        )
    return warn, crit


def _band(used_pct: float, warn: float, crit: float) -> str:
    if used_pct >= crit:
        return "crit"
    if used_pct >= warn:
        return "warn"
    return "ok"


def poll_diskwatch(
    path: Any = None,
    warn_pct: Any = _DEFAULT_WARN_PCT,
    crit_pct: Any = _DEFAULT_CRIT_PCT,
    state: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll contract: ``(events, new_state)``."""
    if path is None:
        raise ConnectorError("diskwatch: 'path' is required")
    real = _guarded_path(path)
    warn, crit = _guarded_thresholds(warn_pct, crit_pct)

    if state is None:
        state = {}
    if not isinstance(state, dict):
        raise ConnectorError("diskwatch: 'state' must be a dict")
    prev_band = state.get("band")
    if prev_band is not None and prev_band not in _BANDS:
        raise ConnectorError(f"diskwatch: unknown band in state: {prev_band!r}")

    usage = shutil.disk_usage(real)
    used_pct = (usage.total - usage.free) / usage.total * 100.0 if usage.total else 0.0
    band = _band(used_pct, warn, crit)

    reading = {
        "band": band,
        "used_pct": round(used_pct, 2),
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "path": str(real),
    }

    if prev_band is None:
        events = [dict(reading, kind="baseline", prev_band=None)]
    elif prev_band == band:
        events = []
    else:
        events = [dict(reading, kind="band_changed", prev_band=prev_band)]

    return events, {"band": band}


registry.register(
    Connector(
        id="diskwatch",
        name="Disk Watch",
        description="Polls local disk usage and emits one event per "
        "usage-band change (ok/warn/crit), including recovery. "
        "Observe-only; the caller holds the last band as state.",
        version="1.0.0",
        inputs=("path", "warn_pct", "crit_pct", "state"),
        risk="info",
        poll=poll_diskwatch,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-diskwatch",
            provides=("connector.diskwatch.poll",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
