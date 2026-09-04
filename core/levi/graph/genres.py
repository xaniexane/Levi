"""
L.W.P. Complete Genre Registry — ALL 97 formal genres

Binding rule: Never silently truncate to a subset.
When other systems or AIs design against L.W.P., this registry is the
source of truth. User-designed genres are additive; they do not replace
the complete set.

Genres are first-class interpenetrable nodes: they compose with personas,
skills, specialists, automations, and composites.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class GenreCategory(str, Enum):
    CORE_CLASSICAL = "core_classical"           # 16
    SIGNATURE_LATTICE = "signature_lattice"     # 7
    HYBRID = "hybrid"                           # 2
    ATMOSPHERE_STRUCTURE = "atmosphere_structure"  # 12
    WORLD_SOCIETY = "world_society"             # 12
    MIND_IDENTITY = "mind_identity"             # 10
    FORM_FORWARD = "form_forward"               # 8
    LWP_SPECIALTY = "lwp_specialty"             # 10
    MAINSTREAM_EXTENDED = "mainstream_extended" # 20


@dataclass
class Genre:
    id: str
    category: GenreCategory
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "tags": self.tags,
        }


# ── Complete formal set (97) — do not truncate ─────────────────

_GENRE_TABLE: List[tuple] = [
    # Core / classical (16)
    ("literary", GenreCategory.CORE_CLASSICAL),
    ("thriller", GenreCategory.CORE_CLASSICAL),
    ("psychological_thriller", GenreCategory.CORE_CLASSICAL),
    ("horror", GenreCategory.CORE_CLASSICAL),
    ("mystery", GenreCategory.CORE_CLASSICAL),
    ("noir", GenreCategory.CORE_CLASSICAL),
    ("dystopian", GenreCategory.CORE_CLASSICAL),
    ("sci_fi", GenreCategory.CORE_CLASSICAL),
    ("gothic", GenreCategory.CORE_CLASSICAL),
    ("romance", GenreCategory.CORE_CLASSICAL),
    ("romance_erotic", GenreCategory.CORE_CLASSICAL),
    ("comedy", GenreCategory.CORE_CLASSICAL),
    ("script", GenreCategory.CORE_CLASSICAL),
    ("suspense", GenreCategory.CORE_CLASSICAL),
    ("emotional", GenreCategory.CORE_CLASSICAL),
    ("humor", GenreCategory.CORE_CLASSICAL),
    # Signature lattice (7)
    ("systems_horror", GenreCategory.SIGNATURE_LATTICE),
    ("memory_thriller", GenreCategory.SIGNATURE_LATTICE),
    ("consent_dystopia", GenreCategory.SIGNATURE_LATTICE),
    ("lattice_gothic", GenreCategory.SIGNATURE_LATTICE),
    ("post_privacy_noir", GenreCategory.SIGNATURE_LATTICE),
    ("trauma_recursion", GenreCategory.SIGNATURE_LATTICE),
    ("eco_psychic", GenreCategory.SIGNATURE_LATTICE),
    # Hybrid (2)
    ("speculative_literary", GenreCategory.HYBRID),
    ("cascade_realism", GenreCategory.HYBRID),
    # Atmosphere & structure (12)
    ("cosmic_horror", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("body_horror", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("folk_horror", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("occult_mystery", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("conspiracy_thriller", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("espionage", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("crime", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("hardboiled", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("surrealism", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("magical_realism", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("absurdist", GenreCategory.ATMOSPHERE_STRUCTURE),
    ("parable", GenreCategory.ATMOSPHERE_STRUCTURE),
    # World & society (12)
    ("climate_fiction", GenreCategory.WORLD_SOCIETY),
    ("solarpunk", GenreCategory.WORLD_SOCIETY),
    ("cyberpunk", GenreCategory.WORLD_SOCIETY),
    ("biopunk", GenreCategory.WORLD_SOCIETY),
    ("hopepunk", GenreCategory.WORLD_SOCIETY),
    ("alternate_history", GenreCategory.WORLD_SOCIETY),
    ("political_thriller", GenreCategory.WORLD_SOCIETY),
    ("institutional_drama", GenreCategory.WORLD_SOCIETY),
    ("workplace_dystopia", GenreCategory.WORLD_SOCIETY),
    ("surveillance_state", GenreCategory.WORLD_SOCIETY),
    ("collapse_fiction", GenreCategory.WORLD_SOCIETY),
    ("migration_epic", GenreCategory.WORLD_SOCIETY),
    # Mind & identity (10)
    ("identity_thriller", GenreCategory.MIND_IDENTITY),
    ("double_life", GenreCategory.MIND_IDENTITY),
    ("unreliable_memoir", GenreCategory.MIND_IDENTITY),
    ("found_footage_prose", GenreCategory.MIND_IDENTITY),
    ("epistolary", GenreCategory.MIND_IDENTITY),
    ("confessional", GenreCategory.MIND_IDENTITY),
    ("grief_narrative", GenreCategory.MIND_IDENTITY),
    ("addiction_realism", GenreCategory.MIND_IDENTITY),
    ("neurodivergent_lit", GenreCategory.MIND_IDENTITY),
    ("possession_drama", GenreCategory.MIND_IDENTITY),
    # Form-forward (8)
    ("mosaic_novel", GenreCategory.FORM_FORWARD),
    ("braided_narrative", GenreCategory.FORM_FORWARD),
    ("choral_novel", GenreCategory.FORM_FORWARD),
    ("documentary_fiction", GenreCategory.FORM_FORWARD),
    ("metafiction", GenreCategory.FORM_FORWARD),
    ("antinovel", GenreCategory.FORM_FORWARD),
    ("constraint_fiction", GenreCategory.FORM_FORWARD),
    ("procedural_lyric", GenreCategory.FORM_FORWARD),
    # L.W.P. specialty (10)
    ("attention_economy_horror", GenreCategory.LWP_SPECIALTY),
    ("platform_gothic", GenreCategory.LWP_SPECIALTY),
    ("data_haunting", GenreCategory.LWP_SPECIALTY),
    ("algorithmic_fate", GenreCategory.LWP_SPECIALTY),
    ("scar_liturgy", GenreCategory.LWP_SPECIALTY),
    ("continuity_horror", GenreCategory.LWP_SPECIALTY),
    ("gold_path_epic", GenreCategory.LWP_SPECIALTY),
    ("breaker_tragedy", GenreCategory.LWP_SPECIALTY),
    ("daemon_comedy", GenreCategory.LWP_SPECIALTY),
    ("interpenetration_romance", GenreCategory.LWP_SPECIALTY),
    # Mainstream extended (20)
    ("drama", GenreCategory.MAINSTREAM_EXTENDED),
    ("dark_comedy", GenreCategory.MAINSTREAM_EXTENDED),
    ("romantic_comedy", GenreCategory.MAINSTREAM_EXTENDED),
    ("family_drama", GenreCategory.MAINSTREAM_EXTENDED),
    ("historical_fiction", GenreCategory.MAINSTREAM_EXTENDED),
    ("literary_fiction", GenreCategory.MAINSTREAM_EXTENDED),
    ("young_adult", GenreCategory.MAINSTREAM_EXTENDED),
    ("adventure", GenreCategory.MAINSTREAM_EXTENDED),
    ("action", GenreCategory.MAINSTREAM_EXTENDED),
    ("western", GenreCategory.MAINSTREAM_EXTENDED),
    ("war", GenreCategory.MAINSTREAM_EXTENDED),
    ("sports", GenreCategory.MAINSTREAM_EXTENDED),
    ("slice_of_life", GenreCategory.MAINSTREAM_EXTENDED),
    ("coming_of_age", GenreCategory.MAINSTREAM_EXTENDED),
    ("tragedy", GenreCategory.MAINSTREAM_EXTENDED),
    ("melodrama", GenreCategory.MAINSTREAM_EXTENDED),
    ("satire", GenreCategory.MAINSTREAM_EXTENDED),
    ("farce", GenreCategory.MAINSTREAM_EXTENDED),
    ("whodunit", GenreCategory.MAINSTREAM_EXTENDED),
    ("cozy_mystery", GenreCategory.MAINSTREAM_EXTENDED),
]


class GenreRegistry:
    """
    Source of truth for L.W.P. genres.
    Total must remain 97 formal genres unless explicitly extended (never reduced).
    """

    EXPECTED_COUNT = 97

    def __init__(self):
        self._genres: Dict[str, Genre] = {}
        for gid, cat in _GENRE_TABLE:
            self._genres[gid] = Genre(
                id=gid,
                category=cat,
                tags=["lwp", "genre", cat.value],
            )
        assert len(self._genres) == self.EXPECTED_COUNT, (
            f"Genre registry integrity failure: expected {self.EXPECTED_COUNT}, "
            f"got {len(self._genres)}. Do not truncate."
        )

    def get(self, genre_id: str) -> Optional[Genre]:
        return self._genres.get(genre_id)

    def list(self, category: Optional[GenreCategory] = None) -> List[Genre]:
        results = list(self._genres.values())
        if category:
            results = [g for g in results if g.category == category]
        return sorted(results, key=lambda g: g.id)

    def categories(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for g in self._genres.values():
            counts[g.category.value] = counts.get(g.category.value, 0) + 1
        return counts

    def ids(self) -> List[str]:
        return sorted(self._genres.keys())

    def count(self) -> int:
        return len(self._genres)

    def integrity_check(self) -> Dict[str, Any]:
        return {
            "expected": self.EXPECTED_COUNT,
            "actual": len(self._genres),
            "ok": len(self._genres) == self.EXPECTED_COUNT,
            "categories": self.categories(),
            "rule": "Never silently truncate. User-designed genres are additive only.",
        }

    def add_custom(self, genre_id: str, category: GenreCategory = GenreCategory.HYBRID, description: str = "") -> Genre:
        """Additive only — does not remove formal 97."""
        gid = genre_id.strip().lower().replace(" ", "_")
        if gid in self._genres:
            return self._genres[gid]
        g = Genre(id=gid, category=category, description=description, tags=["custom", "additive"])
        self._genres[gid] = g
        return g
