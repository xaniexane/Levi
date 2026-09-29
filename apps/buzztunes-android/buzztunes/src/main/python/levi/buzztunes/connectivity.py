"""Connectivity state — online-default, offline-capable.

Chauncey's directive (2026-09-28): "Should be online connection default
but offline capable with downloads."

The phone's real network state is pushed in from the Java side
(ConnectivityManager + NetworkCallback -> bridge.set_online). Until the
first report arrives the state is ONLINE — online is the default, no
manual toggle needed to go online. Tests and headless runs drive it
directly via :meth:`Connectivity.set_online`.

The engine consults this before choosing a playback route:
  * a downloaded copy on-device  -> local file, whatever the state
  * ONLINE                        -> the online route (YouTube seam, with
                                     honest not-linked handling until
                                     Chauncey links it)
  * OFFLINE + nothing downloaded  -> honest "unavailable offline"
                                     refusal — never faked audio, never
                                     a crash
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Connectivity:
    """Last-known network state. Defaults to online per the directive."""

    online: bool = True
    source: str = "default"  # "default" | "android" | "test" | ...
    changed_at: str = field(default_factory=_utcnow)
    transitions: int = 0

    def set_online(self, online: bool, source: str = "android") -> dict:
        """Record a connectivity flip. Returns the new status record."""
        online = bool(online)
        if online != self.online:
            self.online = online
            self.transitions += 1
            self.changed_at = _utcnow()
        self.source = source
        return self.to_record()

    def is_online(self) -> bool:
        return self.online

    def to_record(self) -> dict:
        return {
            "online": self.online,
            "state": "online" if self.online else "offline",
            "source": self.source,
            "changed_at": self.changed_at,
            "transitions": self.transitions,
        }
