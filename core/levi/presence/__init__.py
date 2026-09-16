"""Presence rooms — LAN drop-in rooms with no account and no server.

REMIX DELTA: Discord's business *is* hosting your conversations: accounts,
central servers, and quality tiers are the product. LEVI inverts it — the
room substrate is yours. A presence hub runs on any machine on your LAN
(or on loopback for one machine), peers find it with multicast beacons,
and the protocol is plain JSON over TCP you can read, log, and extend.
No account, no signup, no cloud, no quality paywall: there is no one to
pay because there is no one hosting you.

What this package honestly is: the local-first room substrate — peer
discovery, drop-in rooms, text messages, and presence signaling
(join/leave/timeout). What it is NOT: real-time voice. Python's stdlib
has no audio capture or playback (``wave``/``audioop`` process files;
there is no microphone or speaker API), so voice rooms are archived as
unbuildable-stdlib-only — see docs/PRESENCE.md for the full triage and
the documented extension point.

Layout:
    rooms.py      pure room state machine (no sockets; fully unit-testable)
    server.py     TCP hub speaking newline-delimited JSON
    discovery.py  UDP multicast beacons + peer table with TTL expiry
"""

from __future__ import annotations

from levi.presence.rooms import (
    RoomBook,
    now_iso,
)
from levi.presence.server import PresenceHub
from levi.presence.discovery import (
    Beacon,
    BeaconListener,
    BeaconSender,
    DISCOVERY_PORT,
    MULTICAST_GROUP,
)

__all__ = [
    "RoomBook",
    "PresenceHub",
    "Beacon",
    "BeaconListener",
    "BeaconSender",
    "DISCOVERY_PORT",
    "MULTICAST_GROUP",
    "now_iso",
    "SHELF",
]

# Warehouse atlas entry (wired later by the interop/warehouses crew).
SHELF = {
    "name": "presence",
    "summary": (
        "LAN drop-in rooms with no account and no server: multicast peer "
        "discovery, drop-in rooms, text + presence signaling over stdlib "
        "sockets. The honest local-first room substrate; real-time voice "
        "is archived as unbuildable-stdlib-only (see docs/PRESENCE.md)."
    ),
    "items": [
        "rooms: RoomBook — drop-in room state machine (create/join/leave/"
        "post/heartbeat/timeout sweep), no sockets",
        "server: PresenceHub — TCP hub speaking newline-delimited JSON, "
        "per-room broadcast fan-out",
        "discovery: Beacon/BeaconSender/BeaconListener — UDP multicast "
        "presence beacons with TTL peer table",
        "cli: python -m levi.presence serve|peers|rooms|create|join|say",
    ],
}
