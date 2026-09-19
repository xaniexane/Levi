"""First-consumer-style browsable service directory (type + zone chooser).

Studied from: protocols-hunt-20260916-0041/report.md [Find 4 - AppleTalk]

Functional description: services register under a (name, type, zone) triple
and clients browse them the way early network users picked a printer off a
list — choose a zone, then a type, then a name. Lookups, zone/type listings,
and name-to-address resolution are all in-memory and synchronous.

Care note: the functional pattern (zone-then-type-then-name browsing) is
revived; no trademarks or product names are reused.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/service-directory"


@dataclass
class Service:
    """One named, addressable service."""

    name: str
    type: str
    zone: str
    address: str
    blurb: str = ""


class ServiceDirectory:
    """A browsable directory of services organized by type and zone."""

    def __init__(self) -> None:
        self._services: Dict[str, Service] = {}

    # -- registration --------------------------------------------------
    def register(
        self,
        name: str,
        type: str,
        zone: str,
        address: str,
        blurb: str = "",
    ) -> Service:
        if not name or not type or not zone or not address:
            raise ValueError("name, type, zone, and address are all required")
        key = (zone, type, name)
        if key in self._services:
            raise ValueError(f"service already registered: {name!r} ({type} in {zone})")
        svc = Service(name, type, zone, address, blurb)
        self._services[key] = svc
        return svc

    def unregister(self, name: str, type: str, zone: str) -> bool:
        return self._services.pop((zone, type, name), None) is not None

    # -- browsing ------------------------------------------------------
    def zones(self) -> List[str]:
        return sorted({s.zone for s in self._services.values()})

    def types(self, zone: Optional[str] = None) -> List[str]:
        services = self._services.values()
        if zone is not None:
            services = [s for s in services if s.zone == zone]
        return sorted({s.type for s in services})

    def browse(
        self,
        type: Optional[str] = None,
        zone: Optional[str] = None,
    ) -> List[Service]:
        """List services, optionally filtered by type and/or zone.

        With no filters this is the whole directory, sorted by zone, type,
        name — the full chooser view.
        """
        out = list(self._services.values())
        if zone is not None:
            out = [s for s in out if s.zone == zone]
        if type is not None:
            out = [s for s in out if s.type == type]
        out.sort(key=lambda s: (s.zone, s.type, s.name))
        return out

    def lookup(self, name: str, zone: Optional[str] = None) -> List[Service]:
        """Find services by exact name, optionally constrained to a zone."""
        out = [s for s in self._services.values() if s.name == name]
        if zone is not None:
            out = [s for s in out if s.zone == zone]
        return out

    def resolve(self, name: str, type: str, zone: str) -> str:
        """Resolve the address of one named service (KeyError if unknown)."""
        return self._services[(zone, type, name)].address

    def count(self) -> int:
        return len(self._services)


def demo_directory() -> Dict[str, object]:
    d = ServiceDirectory()
    d.register("inkjet-upstairs", "printer", "home", "addr://printer/inkjet-upstairs")
    d.register("laser-study", "printer", "home", "addr://printer/laser-study")
    d.register("archive-disk", "fileserver", "home", "addr://fs/archive-disk")
    d.register("plotter-lab", "printer", "workshop", "addr://printer/plotter-lab")
    return {
        "zones": d.zones(),
        "types_in_home": d.types("home"),
        "home_printers": [s.name for s in d.browse(type="printer", zone="home")],
        "resolved": d.resolve("archive-disk", "fileserver", "home"),
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_directory(), indent=2))
