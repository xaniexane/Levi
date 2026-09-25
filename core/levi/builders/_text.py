"""Shared text helpers for the builder engine.

Kept in their own module so the planner and the scaffold can both use
them without a circular import.
"""

from __future__ import annotations

import re
from typing import List

# Words that never become app names or entities.
_STOPWORDS = frozenset(
    """
    a an the and or for with to of in on at is are be as by from that this it
    its app application build create make me my want need please add new simple
    basic easy fast just very really also can will would should could there
    their them they we you your our us i me manage manager manages track
    tracker tracks store stores organize keeps keep list lists
    """.split()
)


def _tokens(prompt: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", prompt.lower())


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "app"


def _plural(entity: str) -> str:
    """Naive English plural for route/entity naming (deterministic)."""
    if entity.endswith("y") and len(entity) > 1 and entity[-2] not in "aeiou":
        return entity[:-1] + "ies"  # priority -> priorities
    return entity if entity.endswith("s") else entity + "s"
