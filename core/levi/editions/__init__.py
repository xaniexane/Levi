"""LEVI editions: sector-tailored team editions for every division of the economy.

An edition is a curated team template: a roster of AI/SI operators,
sector workflows, a data-handling posture, and a compliance stance —
shipped inside one of the three rings (open creational / closed /
government). Editions are not separate products; all sit beneath
OMEGA Powered by Alpha, Levi the head of all.

Layout:
    manifest.py  - EditionManifest, RosterSlot, DataPosture, Ring (data model)
    rings.py     - the three rings as distribution architecture + file boundaries
    catalog.py   - the 11 edition manifests (data, not code sprawl)
    schema/      - OPEN RING contents: templates and schemas anyone may build on
    DESIGN.md    - the design doc
"""

from .manifest import DataPosture, EditionManifest, Ring, RosterSlot
from .rings import (
    GOVERNMENT_HARDENING_CHECKLIST,
    ring_for_path,
)

__all__ = [
    "DataPosture",
    "EditionManifest",
    "Ring",
    "RosterSlot",
    "GOVERNMENT_HARDENING_CHECKLIST",
    "ring_for_path",
]
