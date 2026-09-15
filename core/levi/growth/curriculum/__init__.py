"""LEVI growth curriculum — Chauncey and Rex's seed teachings.

Public API:
    LESSONS            structured lesson dicts (lessons.py)
    TOPICS             the five curriculum topics
    load_curriculum()  ingest lessons as seed entries (idempotent)
    curriculum_topics()  per-topic seed counts
    curriculum_entries()  the loaded seed entries
"""

from levi.growth.curriculum.lessons import (
    LESSONS,
    TOPICS,
    validate_lessons,
)
from levi.growth.curriculum.loader import (
    CURRICULUM_CYCLE_ID,
    SEED_CONFIDENCE,
    SEED_CORROBORATED_COUNT,
    curriculum_entries,
    curriculum_topics,
    load_curriculum,
)

__all__ = [
    "LESSONS",
    "TOPICS",
    "validate_lessons",
    "load_curriculum",
    "curriculum_topics",
    "curriculum_entries",
    "SEED_CONFIDENCE",
    "SEED_CORROBORATED_COUNT",
    "CURRICULUM_CYCLE_ID",
]
