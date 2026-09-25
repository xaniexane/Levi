"""Cybrus device trust — enrollment and trust levels for known devices.

Trust levels, strictest-first: ``untrusted < known < trusted``.
Every newly enrolled device starts at ``untrusted`` — trust is granted
explicitly, never assumed.

LEFT-GUARD (Cybrus mandate, 2026-09-22): this registry is watchful.
Promotions (rank increases) happen ONLY through a consumed, single-use,
human-approved ``device.trust_grant`` approval — there is no programmatic
way to promote a device silently: a direct :meth:`set_trust` upgrade with no
matching approval raises :class:`TrustGrantError` and the trust level does
not move. Demotions (rank decreases) are always allowed without an
approval — fail-closed is never gated (L3 deny-wins).

Devices persist as JSON under ``~/.levi/cybrus/devices.json``
(``LEVI_HOME`` override honored) via the shared ``_paths`` helpers.

LAW → GUARD → PROVE (L8): the invariants live in
``levi.cybrus.device_guard`` and are machine-checked by
``tests/test_cybrus_device_guard.py``.
"""

from __future__ import annotations

import hashlib
import secrets
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


def _approval_engine():  # noqa: D103 - private helper, same rationale
    try:
        from levi.cybrus.approval import ApprovalEngine

        return ApprovalEngine()
    except ImportError:  # pragma: no cover - standalone path
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus.approval.standalone",
            Path(__file__).resolve().parent / "approval.py",
        )
        if spec is None or spec.loader is None:
            raise ImportError("cybrus approval engine unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.ApprovalEngine()


def _audit():  # noqa: D103 - private helper, same rationale
    try:
        from levi.cybrus.audit import AuditEngine

        return AuditEngine()
    except ImportError:  # pragma: no cover - standalone path
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus.audit.standalone",
            Path(__file__).resolve().parent / "audit.py",
        )
        if spec is None or spec.loader is None:
            raise ImportError("cybrus audit engine unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.AuditEngine()


TRUST_LEVELS = ("untrusted", "known", "trusted")
_TRUST_RANK = {"untrusted": 0, "known": 1, "trusted": 2}

#: The approval action a human must approve (and the guard must consume,
#: single-use) before a device can be promoted. Bound to
#: details {"device_id", "level"} so a grant for one device/level can never
#: be replayed onto another (L5).
DEVICE_TRUST_GRANT_ACTION = "device.trust_grant"

#: Fingerprint hashing domain separator (anti-spoofing: raw fingerprints
#: never persist, only a salted hash).
_FP_DOMAIN = "cybrus-device-fingerprint-v1"

_STORE_NAME = "devices"


class TrustGrantError(ValueError):
    """A trust UPGRADE was attempted without an approved, single-use
    ``device.trust_grant`` human approval. The trust level did not move.

    Remedy (L6): raise the approval — ``DeviceGuard.sighting()`` /
    ``levi cybrus device request <id> --level <level>`` — have a human run
    ``levi cybrus approve <id>``, then retry the promotion.
    """


def _fingerprint_hash(fingerprint: str, salt: str) -> str:
    return hashlib.sha256(
        f"{_FP_DOMAIN}:{salt}:{fingerprint}".encode("utf-8")
    ).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def _find(self, device_id: str) -> Optional[Dict]:
        for record in self._devices:
            if record["id"] == device_id:
                return record
        return None

    # -- enrollment ------------------------------------------------------

    def enroll(
        self,
        device_id: str,
        name: str,
        *,
        fingerprint: Optional[str] = None,
    ) -> Dict:
        """Enroll a device. Always starts at ``untrusted``. Raises
        :class:`ValueError` when the id is blank or already enrolled.

        When *fingerprint* is given it is bound at first sight (trust on
        first use): only its salted hash persists — raw fingerprints never
        touch disk (L4) and are never audited.

        The duplicate check and the insert run under the store lock."""
        device_id = (device_id or "").strip()
        name = (name or "").strip()
        if not device_id:
            raise ValueError("device_id must be a non-empty string")
        if not name:
            raise ValueError("device name must be a non-empty string")
        now = _utcnow_iso()
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            if self._find(device_id) is not None:
                raise ValueError(f"device already enrolled: {device_id!r}")
            record: Dict = {
                "id": device_id,
                "name": name,
                "trust": "untrusted",
                "enrolled_at": now,
                "first_seen": now,
                "last_seen": now,
                "fingerprint_hash": None,
                "fingerprint_salt": None,
                "last_granted_at": None,
                "last_grant_decided_by": None,
            }
            if fingerprint:
                salt = secrets.token_hex(16)
                record["fingerprint_hash"] = _fingerprint_hash(fingerprint, salt)
                record["fingerprint_salt"] = salt
            self._devices.append(record)
            self._save()
            return dict(record)

    def set_trust(self, device_id: str, level: str) -> Dict:
        """Set a device's trust level. Raises :class:`ValueError` on an
        unknown level, :class:`KeyError` on an unknown device.

        LEFT-GUARD: a rank INCREASE consumes a single-use, human-approved
        ``device.trust_grant`` approval bound to
        ``{"device_id", "level"}`` — atomically, under the store lock, via
        :meth:`ApprovalEngine.consume_approved`. With no matching approved
        approval the upgrade raises :class:`TrustGrantError` and the level
        does not move. A rank DECREASE (demotion) or a no-op re-set is
        always allowed — fail-closed is never gated (L3).

        Both promotions and demotions leave an audit receipt (L1/L12)."""
        if level not in _TRUST_RANK:
            raise ValueError(
                f"unknown trust level {level!r}; valid: {list(TRUST_LEVELS)}"
            )
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            record = self._find(device_id)
            if record is None:
                raise KeyError(f"unknown device: {device_id!r}")
            current_rank = _TRUST_RANK[record["trust"]]
            new_rank = _TRUST_RANK[level]
            if new_rank > current_rank:
                approvals = _approval_engine()
                grant = approvals.consume_approved(
                    DEVICE_TRUST_GRANT_ACTION,
                    {"device_id": device_id, "level": level},
                )
                if grant is None:
                    raise TrustGrantError(
                        f"trust upgrade {device_id!r} {record['trust']} -> "
                        f"{level} refused: no approved, unconsumed "
                        f"{DEVICE_TRUST_GRANT_ACTION!r} approval for this "
                        "device/level (single-use; expired or already-used "
                        "approvals do not count). Remedy: raise a new "
                        "approval (levi cybrus device request "
                        f"{device_id} --level {level}), have a human approve "
                        "it, then retry."
                    )
                record["trust"] = level
                record["last_granted_at"] = _utcnow_iso()
                record["last_grant_decided_by"] = grant.get("decided_by")
                self._save()
                _audit().append(
                    "device.trust_granted",
                    "cybrus.devices",
                    {
                        "device_id": device_id,
                        "from": TRUST_LEVELS[current_rank],
                        "to": level,
                        "approval_id": grant["id"][:8],
                        "decided_by": grant.get("decided_by"),
                    },
                )
                return dict(record)
            # Demotion or no-op: fail-closed, never gated.
            if new_rank < current_rank:
                record["trust"] = level
                self._save()
                _audit().append(
                    "device.trust_demoted",
                    "cybrus.devices",
                    {
                        "device_id": device_id,
                        "from": TRUST_LEVELS[current_rank],
                        "to": level,
                    },
                )
            return dict(record)

    def revoke(self, device_id: str) -> bool:
        """Remove a device entirely. Raises :class:`KeyError` when the
        device is not enrolled. Leaves an audit receipt (L1)."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            record = self._find(device_id)
            if record is None:
                raise KeyError(f"unknown device: {device_id!r}")
            self._devices.remove(record)
            self._save()
        _audit().append(
            "device.revoked",
            "cybrus.devices",
            {"device_id": device_id, "name": record.get("name")},
        )
        return True

    def touch(self, device_id: str) -> Optional[Dict]:
        """Heartbeat: refresh ``last_seen``. No-op when unknown. Returns
        the record or ``None``."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            record = self._find(device_id)
            if record is None:
                return None
            record["last_seen"] = _utcnow_iso()
            self._save()
            return dict(record)

    def refresh(self) -> None:
        """Reload the in-memory registry from disk (lock-protected)."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()

    def fingerprint_matches(self, device_id: str, fingerprint: str) -> Optional[bool]:
        """``True`` when the device has a bound fingerprint and it matches,
        ``False`` when bound and it does NOT match, ``None`` when no
        fingerprint is bound (nothing to compare against)."""
        record = self.get(device_id)
        if record is None:
            return None
        salt = record.get("fingerprint_salt")
        bound = record.get("fingerprint_hash")
        if not salt or not bound:
            return None
        return secrets.compare_digest(
            _fingerprint_hash(fingerprint or "", salt), bound
        )

    def bind_fingerprint(self, device_id: str, fingerprint: str) -> Dict:
        """Bind a fingerprint to a device that has none yet (trust on
        first use). Raises :class:`ValueError` when one is already bound —
        re-binding goes through :meth:`DeviceGuard.challenge` instead."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            record = self._find(device_id)
            if record is None:
                raise KeyError(f"unknown device: {device_id!r}")
            if record.get("fingerprint_hash"):
                raise ValueError(
                    f"device {device_id!r} already has a bound fingerprint; "
                    "use DeviceGuard.challenge to re-bind"
                )
            salt = secrets.token_hex(16)
            record["fingerprint_hash"] = _fingerprint_hash(fingerprint, salt)
            record["fingerprint_salt"] = salt
            self._save()
            return dict(record)

    # -- reads -----------------------------------------------------------

    def get(self, device_id: str) -> Optional[Dict]:
        for record in self._devices:
            if record["id"] == device_id:
                return dict(record)
        return None

    def public_record(self, device_id: str) -> Optional[Dict]:
        """The device record safe for listings: fingerprint salts/hashes
        are stripped (L4 — hashes are metadata-adjacent secrets material)."""
        record = self.get(device_id)
        if record is None:
            return None
        bound = bool(record.pop("fingerprint_hash", None))
        record.pop("fingerprint_salt", None)
        record["fingerprint_bound"] = bound
        return record

    def list(self) -> List[Dict]:
        return [dict(record) for record in self._devices]

    def list_public(self) -> List[Dict]:
        """All devices, fingerprint material stripped (L4)."""
        out = []
        for record in self._devices:
            copy = dict(record)
            bound = bool(copy.pop("fingerprint_hash", None))
            copy.pop("fingerprint_salt", None)
            copy["fingerprint_bound"] = bound
            out.append(copy)
        return out

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
