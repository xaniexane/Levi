"""Eden forbidden zones: containment, quarantine, clearance, receipts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


class ZoneError(ValueError):
    """Refusal: bad zone name, path escape, unknown zone."""


class ClearanceError(ZoneError):
    """Refusal: release without recorded clearance."""


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seal(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass
class EdenRun:
    """A sealed receipt for one experiment run."""
    run_id: str
    zone: str
    name: str
    ok: bool
    detail: str
    files: List[str]
    cleared: bool
    cleared_by: str
    at: str
    seal: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "zone": self.zone,
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "files": list(self.files),
            "cleared": self.cleared,
            "cleared_by": self.cleared_by,
            "at": self.at,
            "seal": self.seal,
        }


class EdenZone:
    """One forbidden zone: a contained root directory."""

    def __init__(self, name: str, root: str) -> None:
        self.name = name
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def resolve(self, relpath: str) -> str:
        """Resolve a relative path inside the zone; refuse escapes."""
        if not isinstance(relpath, str) or not relpath:
            raise ZoneError("path must be a non-empty string")
        if os.path.isabs(relpath):
            raise ZoneError(f"absolute paths forbidden in Eden: {relpath!r}")
        target = os.path.abspath(os.path.join(self.root, relpath))
        if target != self.root and not target.startswith(self.root + os.sep):
            raise ZoneError(f"path escapes the zone: {relpath!r}")
        return target

    def write(self, relpath: str, content: str) -> str:
        target = self.resolve(relpath)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(content)
        return os.path.relpath(target, self.root)


class Eden:
    """The forbidden zone: create zones, run contained experiments."""

    def __init__(self, base_dir: str) -> None:
        if not isinstance(base_dir, str) or not base_dir:
            raise ZoneError("base_dir must be a non-empty string")
        self.base = os.path.abspath(base_dir)
        os.makedirs(self.base, exist_ok=True)
        self._zones: Dict[str, EdenZone] = {}
        self._receipts: List[EdenRun] = []
        self._seq = 0

    # -- zones ---------------------------------------------------------
    def open_zone(self, name: str) -> EdenZone:
        """Open (or re-open) a named forbidden zone."""
        if not isinstance(name, str) or not name.strip():
            raise ZoneError("zone name must be a non-empty string")
        if name in self._zones:
            return self._zones[name]
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)
        zone = EdenZone(name, os.path.join(self.base, safe))
        self._zones[name] = zone
        return zone

    def zone(self, name: str) -> EdenZone:
        try:
            return self._zones[name]
        except KeyError:
            raise ZoneError(f"unknown zone: {name!r}") from None

    # -- runs ----------------------------------------------------------
    def run(self, zone_name: str, name: str,
            experiment: Callable[[EdenZone], str]) -> EdenRun:
        """Run an experiment contained in a zone; seal a receipt.

        The callable receives the zone and returns a detail string.
        Any exception marks the run failed — the receipt is still
        sealed (failed history is compost, not silence).
        """
        zone = self.zone(zone_name)
        self._seq += 1
        run_id = f"eden-{self._seq:06d}"
        before = set()
        for dirpath, _dirnames, filenames in os.walk(zone.root):
            for fname in filenames:
                before.add(os.path.relpath(os.path.join(dirpath, fname), zone.root))
        try:
            detail = experiment(zone) or ""
            ok = True
        except Exception as exc:  # noqa: BLE001 - recorded in the receipt
            detail = f"failed: {exc}"
            ok = False
        after = set()
        for dirpath, _dirnames, filenames in os.walk(zone.root):
            for fname in filenames:
                after.add(os.path.relpath(os.path.join(dirpath, fname), zone.root))
        receipt = EdenRun(
            run_id=run_id, zone=zone_name, name=name, ok=ok, detail=detail,
            files=sorted(after - before), cleared=False, cleared_by="",
            at=_utcnow(),
        )
        receipt.seal = _seal({k: v for k, v in receipt.as_dict().items()
                              if k != "seal"})
        self._receipts.append(receipt)
        return receipt

    # -- clearance -----------------------------------------------------
    def clear(self, run_id: str, cleared_by: str) -> EdenRun:
        """Release a run's outputs from quarantine with recorded clearance.

        Returns a NEW sealed receipt marked cleared; the original
        receipt is kept untouched (history is immutable).
        """
        if not isinstance(cleared_by, str) or not cleared_by.strip():
            raise ClearanceError("clearance requires a named authorizer")
        original = None
        for receipt in self._receipts:
            if receipt.run_id == run_id:
                original = receipt
                break
        if original is None:
            raise ZoneError(f"unknown run: {run_id!r}")
        if not original.ok:
            raise ClearanceError("failed runs cannot be cleared")
        cleared = EdenRun(
            run_id=original.run_id, zone=original.zone, name=original.name,
            ok=original.ok, detail=original.detail, files=list(original.files),
            cleared=True, cleared_by=cleared_by.strip(), at=_utcnow(),
        )
        cleared.seal = _seal({k: v for k, v in cleared.as_dict().items()
                              if k != "seal"})
        self._receipts.append(cleared)
        return cleared

    # -- reads ---------------------------------------------------------
    def receipts(self, zone_name: str | None = None) -> List[Dict[str, Any]]:
        receipts = self._receipts
        if zone_name is not None:
            receipts = [r for r in receipts if r.zone == zone_name]
        return [r.as_dict() for r in receipts]

    def verify_receipts(self) -> Dict[str, Any]:
        """Re-seal every receipt; any mismatch is tamper."""
        for receipt in self._receipts:
            body = {k: v for k, v in receipt.as_dict().items() if k != "seal"}
            if _seal(body) != receipt.seal:
                return {"ok": False, "run_id": receipt.run_id,
                        "reason": "receipt seal mismatch"}
        return {"ok": True, "receipts": len(self._receipts)}

    def destroy_zone(self, name: str) -> None:
        """Tear down a zone's directory (receipts survive — history stays)."""
        zone = self.zone(name)
        shutil.rmtree(zone.root, ignore_errors=True)
        del self._zones[name]
