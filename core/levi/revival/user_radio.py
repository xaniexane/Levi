"""A directory for user-runnable radio stations.

Studied from: desktop-casualties-20260916/report.md (2. Winamp).

The old mechanism: anyone could run an internet-radio station, and a
shared directory let listeners find them — tens of thousands of
stations, participatory media instead of a licensed catalog. LEVI's
reimplementation keeps the platform shape without the wire: a station
registry, listener counts, now-playing announcements with a history
log, a bounded request line, and genre search. Directory metadata only.

Honest limits: nothing here streams audio. This is the participatory
registry — who is on air, what they're playing, who's listening, what
the room wants to hear next — computed locally, no network, no audio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/user_radio"

MAX_REQUESTS = 25  # the request line is finite, like the old ones
MAX_HISTORY = 100  # now-playing entries kept per station

CALLSIGN_RE = re.compile(r"^[A-Z0-9]{3,8}$")


@dataclass
class Station:
    callsign: str
    owner: str
    genre: str
    description: str = ""
    on_air: bool = False
    listeners: int = 0
    now_playing: str = ""
    play_history: List[str] = field(default_factory=list)
    requests: List[str] = field(default_factory=list)

    def summary(self) -> str:
        state = "ON AIR" if self.on_air else "dark"
        return f"{self.callsign} [{self.genre}] {state} — {self.listeners} listening"


class Directory:
    """The shared listing every station registers with and every
    listener browses."""

    def __init__(self) -> None:
        self.stations: Dict[str, Station] = {}

    # -- running a station ----------------------------------------------
    def register(
        self, callsign: str, owner: str, genre: str, description: str = ""
    ) -> Station:
        call = callsign.strip().upper()
        if not CALLSIGN_RE.match(call):
            raise ValueError("callsign must be 3-8 letters/digits")
        if call in self.stations:
            raise ValueError(f"station {call} already registered")
        if not owner.strip() or not genre.strip():
            raise ValueError("owner and genre required")
        station = Station(
            callsign=call,
            owner=owner.strip(),
            genre=genre.strip().lower(),
            description=description.strip(),
        )
        self.stations[call] = station
        return station

    def unregister(self, callsign: str, owner: str) -> None:
        station = self._get(callsign)
        if station.owner != owner.strip():
            raise ValueError("only the owner can unregister a station")
        if station.on_air:
            raise ValueError("go dark before unregistering")
        del self.stations[station.callsign]

    def go_live(self, callsign: str, owner: str) -> Station:
        station = self._owner_check(callsign, owner)
        station.on_air = True
        return station

    def go_dark(self, callsign: str, owner: str) -> Station:
        station = self._owner_check(callsign, owner)
        station.on_air = False
        station.listeners = 0
        station.now_playing = ""
        return station

    def announce(self, callsign: str, owner: str, track: str) -> Station:
        """The DJ's now-playing update; history is bounded."""
        station = self._owner_check(callsign, owner)
        if not station.on_air:
            raise ValueError(f"{station.callsign} is dark")
        if not track.strip():
            raise ValueError("track required")
        station.now_playing = track.strip()
        station.play_history.append(track.strip())
        station.play_history[:] = station.play_history[-MAX_HISTORY:]
        return station

    # -- listening --------------------------------------------------------
    def listen(self, callsign: str) -> int:
        station = self._get(callsign)
        if not station.on_air:
            raise ValueError(f"{station.callsign} is dark")
        station.listeners += 1
        return station.listeners

    def drop(self, callsign: str) -> int:
        station = self._get(callsign)
        station.listeners = max(0, station.listeners - 1)
        return station.listeners

    def request(self, callsign: str, listener: str, track: str) -> int:
        """Put a track on the station's request line. The line is finite;
        a full line refuses politely."""
        station = self._get(callsign)
        if not station.on_air:
            raise ValueError(f"{station.callsign} is dark")
        if len(station.requests) >= MAX_REQUESTS:
            raise ValueError("request line is full")
        if not track.strip():
            raise ValueError("track required")
        station.requests.append(f"{listener.strip()}: {track.strip()}")
        return len(station.requests)

    def take_request(self, callsign: str, owner: str) -> Optional[str]:
        station = self._owner_check(callsign, owner)
        if station.requests:
            return station.requests.pop(0)
        return None

    # -- browsing ----------------------------------------------------------
    def on_air(self) -> List[Station]:
        return [s for s in self.stations.values() if s.on_air]

    def by_genre(self, genre: str) -> List[Station]:
        g = genre.strip().lower()
        return [s for s in self.stations.values() if s.genre == g]

    def search(self, text: str) -> List[Station]:
        needle = text.strip().lower()
        if not needle:
            return []
        return [
            s
            for s in self.stations.values()
            if needle in s.callsign.lower()
            or needle in s.description.lower()
            or needle in s.genre
        ]

    def top(self, n: int = 10) -> List[Station]:
        return sorted(self.on_air(), key=lambda s: s.listeners, reverse=True)[
            : max(0, n)
        ]

    def directory_status(self) -> Dict[str, object]:
        return {
            "stations": len(self.stations),
            "on_air": len(self.on_air()),
            "listeners": sum(s.listeners for s in self.stations.values()),
            "genres": sorted({s.genre for s in self.stations.values()}),
        }

    # -- internals ---------------------------------------------------------
    def _get(self, callsign: str) -> Station:
        try:
            return self.stations[callsign.strip().upper()]
        except KeyError:
            raise ValueError(f"no station {callsign!r}") from None

    def _owner_check(self, callsign: str, owner: str) -> Station:
        station = self._get(callsign)
        if station.owner != owner.strip():
            raise ValueError("only the owner controls this station")
        return station
