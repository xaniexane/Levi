"""levi.intelligence — intelligence-type physics beyond AI/SI/XI.

Home of the declared physics for intelligence classes the genesis factory
may breed: the five scaffolded 2026-09-19 (OE/DV/KT/LM/ST) alongside the
known AI/SI/XI roof, plus the ten genuine natural classes (ANT, CRV, BEE,
WHL, MYC, SLM, IMM, BCT, OCT, CUT) translated from living systems.
Class records here are structural declarations, not agent instances —
no slots are minted by declaring physics.
"""

from levi.intelligence.classes import (
    CLASS_PHYSICS,
    NEW_CLASSES,
    REQUIRED_FIELDS,
    get_class,
    is_new_class,
)
from levi.intelligence.natural import (
    NATURAL_CLASSES,
    NATURAL_CODES,
    NATURAL_ORGANS,
    NATURAL_REQUIRED_FIELDS,
    get_natural,
    is_natural_class,
    natural_for_organ,
)
from levi.intelligence.organs import (
    INTELLIGENCE_ORGANS,
    ORGAN_INTELLIGENCE,
    all_mappings,
    intelligences_for,
    organ_of,
)


def describe(code: str) -> dict:
    """Return the full record for any declared intelligence class.

    Checks the scaffolded physics first, then the genuine natural
    registry. Raises KeyError for unknown codes (deny-closed).
    """
    if code in CLASS_PHYSICS:
        return dict(CLASS_PHYSICS[code])
    if code in NATURAL_CLASSES:
        return dict(NATURAL_CLASSES[code])
    raise KeyError("unknown intelligence class %r" % (code,))


def is_declared_class(code: str) -> bool:
    """True for any declared class: scaffolded or genuine natural."""
    return is_new_class(code) or is_natural_class(code)


__all__ = [
    "CLASS_PHYSICS",
    "NEW_CLASSES",
    "REQUIRED_FIELDS",
    "get_class",
    "is_new_class",
    "NATURAL_CLASSES",
    "NATURAL_CODES",
    "NATURAL_ORGANS",
    "NATURAL_REQUIRED_FIELDS",
    "get_natural",
    "is_natural_class",
    "natural_for_organ",
    "INTELLIGENCE_ORGANS",
    "ORGAN_INTELLIGENCE",
    "all_mappings",
    "intelligences_for",
    "organ_of",
    "describe",
    "is_declared_class",
]
