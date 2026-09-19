"""Edition manifests: the data model. Data, not code sprawl.

An edition is a team template: which operators fill the roster, how the
AI/SI mix leans, what workflows it runs, how it handles data, what law
it answers to, and what it deliberately refuses to include. The catalog
lives in catalog.py; this module holds the shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Ring(Enum):
    """The three rings: distribution architecture, not product lines."""

    OPEN_CREATIONAL = "open-creational"
    CLOSED = "closed"
    GOVERNMENT = "government"


@dataclass(frozen=True)
class RosterSlot:
    """One seat on the edition's team, filled from the 471-agent catalog.

    Slots select by category (and optional subcategories) rather than raw
    agent ids, so catalog re-stamping never breaks an edition. Resolution
    is deterministic: matching agents sorted by id, first ``count`` taken.
    """

    category: str
    subcategories: Tuple[str, ...] = ()
    side: str = "either"  # "ai" | "si" | "either"
    count: int = 1
    purpose: str = ""

    def matches(self, agent) -> bool:
        if agent.category != self.category:
            return False
        if self.subcategories and agent.subcategory not in self.subcategories:
            return False
        return True


@dataclass(frozen=True)
class DataPosture:
    """How the edition treats the sector's data. Always explicit."""

    residency: str = "local-first"
    trains_on_data: bool = False  # never; sold as a feature
    retention: str = "keeper-defined, minimal by default"
    audit: str = "sealed receipts on every run"
    notes: str = ""


@dataclass(frozen=True)
class EditionManifest:
    """The full definition of one sector edition."""

    id: str
    name: str
    sector: str
    ring: Ring
    tagline: str
    description: str
    roster: Tuple[RosterSlot, ...] = ()
    ai_si_mix: str = ""
    workflows: Tuple[str, ...] = ()
    data_posture: DataPosture = field(default_factory=DataPosture)
    compliance: Tuple[str, ...] = ()
    excluded: Tuple[Tuple[str, str], ...] = ()  # (what, why) — deliberate refusals
    tier_fit: str = ""
    pricing_note: str = ""

    def roster_size(self) -> int:
        return sum(slot.count for slot in self.roster)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "sector": self.sector,
            "ring": self.ring.value,
            "tagline": self.tagline,
            "description": self.description,
            "roster": [
                {
                    "category": s.category,
                    "subcategories": list(s.subcategories),
                    "side": s.side,
                    "count": s.count,
                    "purpose": s.purpose,
                }
                for s in self.roster
            ],
            "roster_size": self.roster_size(),
            "ai_si_mix": self.ai_si_mix,
            "workflows": list(self.workflows),
            "data_posture": {
                "residency": self.data_posture.residency,
                "trains_on_data": self.data_posture.trains_on_data,
                "retention": self.data_posture.retention,
                "audit": self.data_posture.audit,
                "notes": self.data_posture.notes,
            },
            "compliance": list(self.compliance),
            "excluded": [{"what": w, "why": why} for w, why in self.excluded],
            "tier_fit": self.tier_fit,
            "pricing_note": self.pricing_note,
        }


def resolve_roster(manifest: EditionManifest, agents) -> List:
    """Fill every slot from the agent catalog. Deterministic."""
    pool = sorted(agents, key=lambda a: a.id)
    filled: List = []
    used = set()
    for slot in manifest.roster:
        matches = [a for a in pool if a.id not in used and slot.matches(a)]
        chosen = matches[: slot.count]
        filled.extend(chosen)
        used.update(a.id for a in chosen)
    return filled


def validate_manifest(manifest: EditionManifest, agents) -> List[str]:
    """Return a list of problems; empty means the manifest is sound."""
    problems: List[str] = []
    if not manifest.id or not manifest.name:
        problems.append("missing id or name")
    if not isinstance(manifest.ring, Ring):
        problems.append("ring must be a Ring")
    if manifest.data_posture.trains_on_data:
        problems.append("editions never train on sector data")
    pool = list(agents)
    for slot in manifest.roster:
        matches = [a for a in pool if slot.matches(a)]
        if not matches:
            problems.append(f"slot resolves to zero agents: {slot.category}")
        elif len(matches) < slot.count:
            problems.append(
                f"slot wants {slot.count} from {slot.category}, only "
                f"{len(matches)} match"
            )
        if slot.side not in ("ai", "si", "either"):
            problems.append(f"bad side on slot: {slot.side}")
    for what, why in manifest.excluded:
        if not what or not why:
            problems.append("excluded entries need both what and why")
    return problems
