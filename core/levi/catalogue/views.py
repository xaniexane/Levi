"""Catalogue views — founder sees everything; everyone else the gated surface.

Founder-gating law: every creation's TRUE POTENTIAL is founder-only.
The catalogue is a public surface, so it lists the restricted surface
and never the full capability — except to the founder.

``catalogue_view(entries, identity_record)`` consults
``levi.cybrus.identity.is_founder``: the founder gets
``entry.founder_dict()`` (incl. ``full_capabilities``); anyone else —
including a missing/unknown identity — gets ``entry.public_dict()``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from levi.cybrus.identity import is_founder

from .entries import CatalogueEntry


def catalogue_view(
    entries: List[CatalogueEntry], identity_record: Optional[Dict] = None
) -> List[Dict]:
    """Render the catalogue for an identity. Founder = full, else gated."""
    founder = is_founder(identity_record)
    if founder:
        return [e.founder_dict() for e in entries]
    return [e.public_dict() for e in entries]
