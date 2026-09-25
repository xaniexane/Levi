"""LEVI growth curriculum — Chauncey and Rex's seed teachings.

Public API:
    LESSONS            structured lesson dicts (lessons.py)
    TOPICS             the five curriculum topics
    load_curriculum()  ingest lessons as seed entries (idempotent)
    curriculum_topics()  per-topic seed counts
    curriculum_entries()  the loaded seed entries

Blue-team track (blue_team.py) — defensive analyst / LEVI-domain lessons
for the study hall, kept separate from the founder seeds so each track
keeps its own validation and topic set:
    BLUE_TEAM_LESSONS  defensive lesson dicts for study-hall quizzes
    BLUE_TEAM_TOPICS   the six blue-team topics
    BLUE_TEAM_KINDS    accepted lesson kinds for the blue-team track
    validate_blue_team_lessons()  structural validation
"""

from levi.growth.curriculum.blue_team import (
    BLUE_TEAM_KINDS,
    BLUE_TEAM_LESSONS,
    BLUE_TEAM_TOPICS,
    validate_blue_team_lessons,
)
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
    "BLUE_TEAM_LESSONS",
    "BLUE_TEAM_TOPICS",
    "BLUE_TEAM_KINDS",
    "validate_blue_team_lessons",
]
