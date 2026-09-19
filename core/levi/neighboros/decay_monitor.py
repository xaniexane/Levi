"""Decay-monitored delivery — the job isn't done at delivery.

Post-delivery health monitoring: every registered delivery carries a
check interval and a heartbeat log. :func:`record_heartbeat` logs
each health check; :func:`nudges` returns pull-based nudge records
for deliveries whose latest heartbeat is unhealthy or whose check is
overdue. Nudges are records, not pushes — there is no notification
rail, so the operator pulls them.

Honest limit: this monitors the *recorded* health of delivered work.
It cannot detect degradation nobody reports; the heartbeat is the
instrument, and the instrument needs a hand.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.neighboros import _seal

_SECONDS_PER_DAY = 86400.0


def _monitor_path(home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "delivery_health"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d / "deliveries.json"


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _now(now: Optional[float]) -> float:
    return now if now is not None else time.time()


def _load(home: Optional[Path] = None) -> Dict[str, Any]:
    p = _monitor_path(home)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(record: Dict[str, Any], home: Optional[Path] = None) -> None:
    _write_json(_monitor_path(home), record)


def register_delivery(delivery_id: str, offering_id: str,
                      check_interval_days: float = 30.0,
                      home: Optional[Path] = None,
                      now: Optional[float] = None) -> Dict[str, Any]:
    """Register a delivery for post-delivery health monitoring."""
    if not delivery_id or not delivery_id.strip():
        raise ValueError("delivery_id must be non-empty")
    if not offering_id or not offering_id.strip():
        raise ValueError("offering_id must be non-empty")
    interval = float(check_interval_days)
    if interval <= 0:
        raise ValueError("check_interval_days must be positive")
    record = _load(home)
    if delivery_id in record:
        raise ValueError(f"delivery {delivery_id!r} is already registered")
    ts = _now(now)
    record[delivery_id] = {
        "delivery_id": delivery_id,
        "offering_id": offering_id,
        "check_interval_days": interval,
        "registered_at": ts,
        "last_check_at": None,
        "heartbeats": [],
    }
    _save(record, home)
    return {"delivery_id": delivery_id, "offering_id": offering_id,
            "check_interval_days": interval, "monitoring": True}


def record_heartbeat(delivery_id: str, healthy: bool, note: str = "",
                     home: Optional[Path] = None,
                     now: Optional[float] = None) -> Dict[str, Any]:
    """Log one health check for a delivery."""
    record = _load(home)
    if delivery_id not in record:
        raise KeyError(f"unknown delivery {delivery_id!r}")
    ts = _now(now)
    entry = record[delivery_id]
    entry["heartbeats"].append({"ts": ts, "healthy": bool(healthy),
                                "note": str(note or "")})
    entry["last_check_at"] = ts
    _save(record, home)
    return {"delivery_id": delivery_id, "healthy": bool(healthy),
            "heartbeats": len(entry["heartbeats"])}


def delivery_health(delivery_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Current health snapshot for one delivery."""
    record = _load(home)
    if delivery_id not in record:
        raise KeyError(f"unknown delivery {delivery_id!r}")
    entry = record[delivery_id]
    last = entry["heartbeats"][-1] if entry["heartbeats"] else None
    return {"delivery_id": delivery_id, "offering_id": entry["offering_id"],
            "last_healthy": None if last is None else last["healthy"],
            "last_check_at": entry["last_check_at"],
            "heartbeats": len(entry["heartbeats"])}


def nudges(home: Optional[Path] = None, now: Optional[float] = None) -> List[Dict[str, Any]]:
    """Pull-based nudge records: unhealthy or overdue deliveries."""
    ts = _now(now)
    out = []
    for delivery_id, entry in sorted(_load(home).items()):
        interval_s = entry["check_interval_days"] * _SECONDS_PER_DAY
        last_check = entry["last_check_at"]
        last = entry["heartbeats"][-1] if entry["heartbeats"] else None
        if last is not None and not last["healthy"]:
            out.append({"delivery_id": delivery_id,
                        "offering_id": entry["offering_id"],
                        "reason": "unhealthy",
                        "detail": last.get("note", ""),
                        "since": last["ts"]})
        elif last_check is None:
            if ts - entry["registered_at"] > interval_s:
                out.append({"delivery_id": delivery_id,
                            "offering_id": entry["offering_id"],
                            "reason": "overdue",
                            "detail": "no health check recorded yet",
                            "since": entry["registered_at"]})
        elif ts - last_check > interval_s:
            out.append({"delivery_id": delivery_id,
                        "offering_id": entry["offering_id"],
                        "reason": "overdue",
                        "detail": "check interval elapsed",
                        "since": last_check})
    return out
