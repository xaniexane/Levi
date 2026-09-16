"""Cybrus device trust — enrollment and trust levels for known devices.

Trust levels, strictest-first: ``untrusted < known < trusted``.
Every newly enrolled device starts at ``untrusted`` — trust is granted
explicitly via :meth:`set_trust`, never assumed. ``revoke`` removes the
device entirely (a re-enrolled device starts over at ``untrusted``).

Devices persist as JSON under ``~/.levi/cybrus/devices.json``
(``LEVI_HOME`` override honored) via the shared ``_paths`` helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# --- standalone-safe import of the sibling _paths helper -------------------
# Same rationale as policy.py: must work even while the package __init__
# is mid-flight on sibling engine modules.
def _paths():  # noqa: D103 - private helper
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


TRUST_LEVELS = ("untrusted", "known", "trusted")
_TRUST_RANK = {"untrusted": 0, "known": 1, "trusted": 2}

_STORE_NAME = "devices"


class DeviceTrust:
    """Enrollment + trust-level management for devices."""

    def __init__(self) -> None:
        p = _paths()
        self._path: Path = p.store_path(_STORE_NAME)
        data = p.load_json_store(self._path)
        self._devices: List[Dict] = data if isinstance(data, list) else []

    # -- persistence -----------------------------------------------------

    def _reload(self) -> None:
        """Reload from disk. Call with the store lock held."""
        data = _paths().load_json_store(self._path)
        self._devices = data if isinstance(data, list) else []

    def _save(self) -> None:
        _paths().save_json_store(self._path, self._devices)

    # -- enrollment ------------------------------------------------------

    def enroll(self, device_id: str, name: str) -> Dict:
        """Enroll a device. Always starts at ``untrusted``. Raises
        :class:`ValueError` when the id is blank or already enrolled.

        The duplicate check and the insert run under the store lock."""
        device_id = (device_id or "").strip()
        name = (name or "").strip()
        if not device_id:
            raise ValueError("device_id must be a non-empty string")
        if not name:
            raise ValueError("device name must be a non-empty string")
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            if self.get(device_id) is not None:
                raise ValueError(f"device already enrolled: {device_id!r}")
            record = {
                "id": device_id,
                "name": name,
                "trust": "untrusted",
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
            }
            self._devices.append(record)
            self._save()
            return dict(record)

    def set_trust(self, device_id: str, level: str) -> Dict:
        """Set a device's trust level. Raises :class:`ValueError` on an
        unknown level, :class:`KeyError` on an unknown device."""
        if level not in _TRUST_RANK:
            raise ValueError(
                f"unknown trust level {level!r}; valid: {list(TRUST_LEVELS)}"
            )
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            for record in self._devices:
                if record["id"] == device_id:
                    record["trust"] = level
                    self._save()
                    return dict(record)
        raise KeyError(f"unknown device: {device_id!r}")

    def revoke(self, device_id: str) -> bool:
        """Remove a device entirely. Raises :class:`KeyError` when the
        device is not enrolled."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            for record in self._devices:
                if record["id"] == device_id:
                    self._devices.remove(record)
                    self._save()
                    return True
        raise KeyError(f"unknown device: {device_id!r}")

    # -- reads -----------------------------------------------------------

    def get(self, device_id: str) -> Optional[Dict]:
        for record in self._devices:
            if record["id"] == device_id:
                return dict(record)
        return None

    def list(self) -> List[Dict]:
        return [dict(record) for record in self._devices]

    def is_trusted(self, device_id: str) -> bool:
        """True only when the device is enrolled at the ``trusted`` level."""
        record = self.get(device_id)
        return record is not None and record["trust"] == "trusted"

    def trust_at_least(self, device_id: str, level: str) -> bool:
        """True when the device's trust rank is at or above *level*."""
        if level not in _TRUST_RANK:
            raise ValueError(f"unknown trust level {level!r}")
        record = self.get(device_id)
        if record is None:
            return False
        return _TRUST_RANK[record["trust"]] >= _TRUST_RANK[level]
