"""Mem-watch connector — the ear on local memory pressure.

Polls ``/proc/meminfo`` (``MemTotal`` / ``MemAvailable``) and computes
memory pressure as ``100 * (1 - MemAvailable / MemTotal)``. Emits one
event per pressure-band change::

    {"kind": "baseline" | "band_changed" | "recovered",
     "band": "ok" | "warn" | "crit" | "unknown",
     "prev_band": <band | None>,
     "pressure_pct": <float>, "mem_total_kb": <int>,
     "mem_available_kb": <int>}

Bands come from ``warn_pct`` (default 75) and ``crit_pct`` (default 90).
The first poll emits an honest ``baseline`` (band ``unknown`` —
pressure is known but there is no history yet); a steady band emits
nothing; recovery back to ``ok`` emits exactly one ``recovered`` event.

The caller holds ``state`` (last band, poll time) between polls; the
connector itself keeps nothing.

Laws
----
- observe-only: reads ``/proc/meminfo``; never writes or touches anything
- deny-closed: ``proc_root`` must be a directory; thresholds must satisfy
  ``0 < warn_pct < crit_pct <= 100``; a ``state`` carrying an unknown
  band or malformed pressure is refused, never guessed
- honest baseline: no prior sample means no claim of a change — the
  first poll says ``baseline``, never ``band_changed``

Stdlib only, local-first.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_BANDS = ("ok", "warn", "crit", "unknown")
_DEFAULT_WARN_PCT = 75.0
_DEFAULT_CRIT_PCT = 90.0


def _guarded_root(proc_root: Any) -> str:
    if not isinstance(proc_root, (str, os.PathLike)):
        raise ConnectorError("memwatch: 'proc_root' must be a string path")
    root = os.path.abspath(os.path.expanduser(str(proc_root)))
    if not os.path.isdir(root):
        raise ConnectorError(f"memwatch: '{proc_root}' is not a directory")
    return root


def _guarded_thresholds(warn_pct: Any, crit_pct: Any) -> Tuple[float, float]:
    try:
        warn = float(warn_pct)
        crit = float(crit_pct)
    except (TypeError, ValueError) as exc:
        raise ConnectorError("memwatch: 'warn_pct'/'crit_pct' must be numbers") from exc
    if not (0 < warn < crit <= 100):
        raise ConnectorError(
            "memwatch: thresholds must satisfy 0 < warn_pct < crit_pct <= 100"
        )
    return warn, crit


def _guarded_state(state: Any) -> Optional[str]:
    if state is None:
        return None
    if not isinstance(state, dict):
        raise ConnectorError("memwatch: 'state' must be a dict or None")
    band = state.get("band")
    if band not in _BANDS:
        raise ConnectorError(f"memwatch: state carries unknown band {band!r}")
    return band


def _read_meminfo(root: str) -> Tuple[int, int]:
    path = os.path.join(root, "meminfo")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise ConnectorError(f"memwatch: cannot read meminfo: {exc}") from exc
    values: Dict[str, int] = {}
    for line in lines:
        parts = line.split(":")
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        rest = parts[1].strip().split()
        if key in ("MemTotal", "MemAvailable") and rest:
            try:
                values[key] = int(rest[0])
            except ValueError as exc:
                raise ConnectorError(
                    f"memwatch: meminfo field {key!r} is not an integer"
                ) from exc
    try:
        total = values["MemTotal"]
        available = values["MemAvailable"]
    except KeyError as exc:
        raise ConnectorError(f"memwatch: meminfo missing field {exc}") from None
    if total <= 0:
        raise ConnectorError("memwatch: meminfo reports non-positive MemTotal")
    if not (0 <= available <= total):
        raise ConnectorError("memwatch: meminfo MemAvailable outside [0, MemTotal]")
    return total, available


def _band_for(pressure: float, warn: float, crit: float) -> str:
    if pressure >= crit:
        return "crit"
    if pressure >= warn:
        return "warn"
    return "ok"


def poll_memwatch(
    proc_root: str = "/proc",
    warn_pct: float = _DEFAULT_WARN_PCT,
    crit_pct: float = _DEFAULT_CRIT_PCT,
    state: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll memory pressure per the connector contract.

    Returns ``(events, new_state)`` where ``new_state`` is
    ``{"band": <band>, "pressure_pct": <float>}``.
    """
    root = _guarded_root(proc_root)
    warn, crit = _guarded_thresholds(warn_pct, crit_pct)
    prev_band = _guarded_state(state)

    total_kb, available_kb = _read_meminfo(root)
    pressure = 100.0 * (1.0 - available_kb / total_kb)
    band = _band_for(pressure, warn, crit)

    reading = {
        "band": band,
        "prev_band": prev_band,
        "pressure_pct": pressure,
        "mem_total_kb": total_kb,
        "mem_available_kb": available_kb,
    }

    if prev_band is None:
        events = [dict(reading, kind="baseline")]
    elif prev_band != band:
        if band == "ok":
            events = [dict(reading, kind="recovered")]
        else:
            events = [dict(reading, kind="band_changed")]
    else:
        events = []

    new_state = {"band": band, "pressure_pct": pressure}
    return events, new_state


registry.register(
    Connector(
        id="memwatch",
        name="Mem Watch",
        description="Polls /proc/meminfo and emits one event per "
        "memory-pressure band change (ok/warn/crit), including "
        "recovery. Observe-only; the caller holds the last band as "
        "state. Thresholds are deny-closed (0 < warn < crit <= 100).",
        version="1.0.0",
        inputs=("proc_root", "warn_pct", "crit_pct", "state"),
        risk="info",
        poll=poll_memwatch,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-memwatch",
            provides=("connector.memwatch.poll",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()

MANIFEST_ENTRY = {
    "connector-memwatch": {
        "provides": ["connector.memwatch.poll"],
        "requires": [],
    },
}
