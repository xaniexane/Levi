"""The Compagnonnage: the Tour de France of the Compagnons du Devoir.

Origin: aspirant craftsmen spent 3-7 years traveling France, changing
town and workshop every 6-12 months to learn each region's masters,
living in communal houses (cayennes) run by a 'mere'; the journey
culminated in a chef-d'oeuvre and full compagnon status. No single
master's blind spots could survive the rotation, and a symbolic graphic
language (le Trait geometry) plus shared rites bound the dispersed
network into one institution. The Tour was a training institution, not
just a journey.

What it is in LEVI: ``RotationTour`` — a fixed tour of workshops, each
with a master and a skill. The apprentice must complete every station
strictly in order, and at each stop must correctly demonstrate the
network's shared symbolic vocabulary. Out-of-order work is refused.

Honesty label: LOAD-BEARING — ordered multi-station rotation with a
symbolic-vocabulary check per stop is a concrete, transferable
mechanism.

Deny-closed inputs: empty station/master/skill/symbol names, duplicate
station names, adding stations after the tour has begun, unknown station
names, completing a station out of order, completing an already
completed station, and demonstrating the wrong symbol at a station are
all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Station", "RotationTour"]


@dataclass
class Station:
    """One stop on the tour: a workshop, its master, the skill taught,
    and the symbol of the shared graphic vocabulary the apprentice must
    demonstrate there."""

    name: str
    master: str
    skill: str
    symbol: str

    def __post_init__(self) -> None:
        for attr in ("name", "master", "skill", "symbol"):
            value = getattr(self, attr)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"station {attr} must be a non-empty string")
            setattr(self, attr, value.strip())


class RotationTour:
    """A forced-mobility training tour: every station, in order, no
    skipping — no single master's blind spots survive the rotation."""

    def __init__(self, apprentice: str):
        if not isinstance(apprentice, str) or not apprentice.strip():
            raise ValueError("apprentice must be a non-empty string")
        self.apprentice = apprentice.strip()
        self._stations: list[Station] = []
        self._completed: list[str] = []  # station names, in completion order

    # -- the itinerary -------------------------------------------------------
    def add_station(self, name: str, master: str, skill: str, symbol: str) -> Station:
        """Fix one stop of the itinerary. The tour is defined before it
        begins; stations cannot be added mid-tour."""
        if self._completed:
            raise ValueError("tour has begun; the itinerary is fixed")
        station = Station(name=name, master=master, skill=skill, symbol=symbol)
        if any(s.name.lower() == station.name.lower() for s in self._stations):
            raise ValueError(f"duplicate station: {station.name!r}")
        self._stations.append(station)
        return station

    @property
    def next_station(self) -> Station | None:
        """The station the apprentice must complete next, or None when the
        tour is done."""
        idx = len(self._completed)
        return self._stations[idx] if idx < len(self._stations) else None

    # -- the journey -----------------------------------------------------------
    def complete_station(self, station_name: str, symbol: str) -> Station:
        """Complete the current station, demonstrating its symbol. The
        station must be the next one on the itinerary and the symbol must
        match — the shared vocabulary is tested at every stop."""
        nxt = self.next_station
        if nxt is None:
            raise ValueError("tour is complete; no stations remain")
        if (
            not isinstance(station_name, str)
            or station_name.strip().lower() != nxt.name.lower()
        ):
            raise ValueError(
                f"out of order: next station is {nxt.name!r}, not {station_name!r}"
            )
        if not isinstance(symbol, str) or symbol.strip().lower() != nxt.symbol.lower():
            raise ValueError(f"wrong symbol at {nxt.name!r}: expected {nxt.symbol!r}")
        self._completed.append(nxt.name)
        return nxt

    @property
    def is_complete(self) -> bool:
        return bool(self._stations) and self.next_station is None

    def progress(self) -> dict:
        return {
            "apprentice": self.apprentice,
            "stations": [s.name for s in self._stations],
            "completed": list(self._completed),
            "next": self.next_station.name if self.next_station else None,
            "complete": self.is_complete,
        }
