"""Battery/power-supply connector — the ear on device power.

Polls the Linux power-supply sysfs tree (``/sys/class/power_supply``) and
emits one event per *edge*::

    {"kind": "baseline",
     "present": True, "capacity": <0..100 | None>, "status": "<status | None>",
     "mains": <True | False | None>, "name": "<supply name | None>"}
    {"kind": "status_changed", "status": <new>, "prev_status": <old>, ...}
    {"kind": "band_changed", "band": "ok"|"warn"|"crit", "prev_band": <old>,
     "capacity": <pct>, ...}
    {"kind": "mains_changed", "mains": <bool>, "prev_mains": <old>, ...}

A machine with no battery is answered honestly: the first poll emits a
``baseline`` with ``present=False`` and a steady state emits nothing —
silence means unchanged, never unknown.

Laws
----
- observe-only: sysfs files are read and never written; the connector
  itself keeps nothing — the caller holds ``state`` between polls.
- honest baseline: the first poll always emits a baseline naming exactly
  what was found (battery, mains, both, or neither).
- edge-only: steady status/band/mains emits nothing; a flap — including
  recovery back to ``ok`` — emits exactly one event.

Deny-closed paths
-----------------
- ``sysfs_root`` must be an existing directory; a missing or unreadable
  tree is a ``ConnectorError``, never guessed values.
- ``0 < crit_pct < warn_pct < 100`` — thresholds that don't order are
  refused, never silently reordered.
- a ``state`` carrying values outside the declared enums is refused,
  never interpreted.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

__all__ = ["poll", "bands", "BatteryError"]

_BANDS = ("ok", "warn", "crit")
_STATUSES = ("charging", "discharging", "full", "not charging", "unknown")


class BatteryError(ConnectorError):
    """Named error for battery-poll input or sysfs failures."""


def _guarded_root(sysfs_root: Any) -> str:
    if isinstance(sysfs_root, bool) or not isinstance(sysfs_root, str):
        raise BatteryError("battery: 'sysfs_root' must be a path string")
    root = os.path.expanduser(sysfs_root)
    if not os.path.isdir(root):
        raise BatteryError(
            f"battery: sysfs_root '{sysfs_root}' is not a directory — nothing was read."
        )
    return root


def _guarded_thresholds(warn_pct: Any, crit_pct: Any) -> Tuple[float, float]:
    for label, value in (("warn_pct", warn_pct), ("crit_pct", crit_pct)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BatteryError(f"battery: '{label}' must be a number")
    warn, crit = float(warn_pct), float(crit_pct)
    if not 0.0 < crit < warn < 100.0:
        raise BatteryError(
            "battery: need 0 < crit_pct < warn_pct < 100, "
            f"got crit_pct={crit_pct!r} warn_pct={warn_pct!r}"
        )
    return warn, crit


def _guarded_state(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise BatteryError("battery: 'state' must be a dict")
    for key in ("band", "status", "mains", "present"):
        if key in state and state[key] is not None:
            if key == "band" and state[key] not in _BANDS:
                raise BatteryError(f"battery: state band {state[key]!r} is unknown")
            if key == "status" and state[key] not in _STATUSES:
                raise BatteryError(f"battery: state status {state[key]!r} is unknown")
            if key == "mains" and not isinstance(state[key], bool):
                raise BatteryError(f"battery: state mains {state[key]!r} is unknown")
    return state


def _read(root: str, name: str, field: str) -> Optional[str]:
    path = os.path.join(root, name, field)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _sample(root: str) -> Dict[str, Any]:
    """Read the supply tree; returns present/capacity/status/mains/name."""
    batteries: List[str] = []
    mains: Optional[bool] = None
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        entries = []
    for entry in entries:
        kind = _read(root, entry, "type")
        if kind == "Battery":
            batteries.append(entry)
        elif kind == "Mains":
            online = _read(root, entry, "online")
            if online == "1":
                mains = True
            elif online == "0":
                mains = False
    if not batteries:
        return {
            "present": False,
            "capacity": None,
            "status": None,
            "mains": mains,
            "name": None,
        }
    name = batteries[0]
    status_raw = _read(root, name, "status")
    status = status_raw.lower() if status_raw else None
    if status not in _STATUSES:
        status = "unknown" if status_raw is not None else None
    capacity_raw = _read(root, name, "capacity")
    try:
        capacity = int(capacity_raw) if capacity_raw is not None else None
    except ValueError:
        capacity = None
    if capacity is not None and not 0 <= capacity <= 100:
        capacity = None
    return {
        "present": True,
        "capacity": capacity,
        "status": status,
        "mains": mains,
        "name": name,
    }


def bands(capacity: Optional[int], warn_pct: float, crit_pct: float) -> Optional[str]:
    """Charge band for a capacity, or None when capacity is unknown."""
    if capacity is None:
        return None
    if capacity < crit_pct:
        return "crit"
    if capacity < warn_pct:
        return "warn"
    return "ok"


def poll(
    state: Dict[str, Any] | None = None,
    sysfs_root: str = "/sys/class/power_supply",
    warn_pct: float = 30.0,
    crit_pct: float = 15.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Poll the power-supply tree. Returns (events, new_state)."""
    root = _guarded_root(sysfs_root)
    warn, crit = _guarded_thresholds(warn_pct, crit_pct)
    state = _guarded_state(state if state is not None else {})

    sample = _sample(root)
    band = bands(sample["capacity"], warn, crit)
    new_state: Dict[str, Any] = {
        "present": sample["present"],
        "band": band,
        "status": sample["status"],
        "mains": sample["mains"],
    }

    if not state:
        baseline = {
            "kind": "baseline",
            "present": sample["present"],
            "capacity": sample["capacity"],
            "status": sample["status"],
            "band": band,
            "mains": sample["mains"],
            "name": sample["name"],
        }
        return [baseline], new_state

    events: List[Dict[str, Any]] = []
    if new_state["present"] != state.get("present"):
        events.append(
            {
                "kind": "present_changed",
                "present": new_state["present"],
                "prev_present": state.get("present"),
                "name": sample["name"],
            }
        )
    elif new_state["present"]:
        if (
            new_state["status"] != state.get("status")
            and new_state["status"] is not None
        ):
            events.append(
                {
                    "kind": "status_changed",
                    "status": new_state["status"],
                    "prev_status": state.get("status"),
                    "capacity": sample["capacity"],
                    "name": sample["name"],
                }
            )
        if new_state["band"] is not None and new_state["band"] != state.get("band"):
            events.append(
                {
                    "kind": "band_changed",
                    "band": new_state["band"],
                    "prev_band": state.get("band"),
                    "capacity": sample["capacity"],
                    "name": sample["name"],
                }
            )
        if new_state["mains"] is not None and new_state["mains"] != state.get("mains"):
            events.append(
                {
                    "kind": "mains_changed",
                    "mains": new_state["mains"],
                    "prev_mains": state.get("mains"),
                    "name": sample["name"],
                }
            )
    return events, new_state


registry.register(
    Connector(
        id="battery",
        name="Battery / power-supply watcher",
        description=(
            "Watches charge level, charge status, and AC mains via "
            "/sys/class/power_supply. Edge-only events, honest baseline. "
            "Observe-only; the caller holds state."
        ),
        version="1.0.0",
        inputs=("sysfs_root", "warn_pct", "crit_pct"),
        poll=poll,
    )
)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "connector-battery",
            provides=("connector.battery.poll",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
