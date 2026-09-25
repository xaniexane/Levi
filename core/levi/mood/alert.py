"""MOOD alerts — immediate alert to Chauncey on every trip (L4).

The module writes alerts to a local queue (``~/.levi/mood/alerts.jsonl``,
mode 0600) and returns. DELIVERY IS THE HOST'S JOB: this module never
opens a socket, never sends mail, never posts anywhere (L2, L4). A host
integration polls :meth:`AlertQueue.drain` and hands alerts to Chauncey
however he configured it.

Honest limit, stated here: an alert in the queue is an alert *written*,
not an alert *delivered*. Delivery guarantees belong to the host wiring,
not to this module.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from levi.mood.laws import ZONE
from levi.mood.tripwires import TripEvent

__all__ = ["AlertQueue"]

_RECORD_MODE = 0o600


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AlertQueue:
    """Local alert queue for Chauncey (L4). Write-only for the module."""

    def __init__(self, home: Path) -> None:
        self._path = Path(home) / ".levi" / ZONE / "alerts.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("", encoding="utf-8")
            os.chmod(self._path, _RECORD_MODE)

    def enqueue(
        self, event: TripEvent, note: str = "", ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Write one alert for a tripped wire; return the alert record."""
        alert: Dict[str, Any] = {
            "zone": ZONE,
            "mood": True,
            "ts": ts or _utcnow(),
            "to": "chauncey",
            "kind": "mood_trip",
            "trip": event.to_dict(),
            "note": note,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(alert) + "\n")
        os.chmod(self._path, _RECORD_MODE)
        return alert

    def pending(self) -> List[Dict[str, Any]]:
        """Alerts not yet drained by the host."""
        return list(self._iter())

    def drain(self) -> List[Dict[str, Any]]:
        """Host pickup: return all pending alerts and clear the queue."""
        alerts = self.pending()
        self._path.write_text("", encoding="utf-8")
        os.chmod(self._path, _RECORD_MODE)
        return alerts

    @property
    def path(self) -> Path:
        return self._path

    def _iter(self) -> Iterator[Dict[str, Any]]:
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)
