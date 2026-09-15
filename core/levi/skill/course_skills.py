"""LEVI curriculum skill pack: data-driven registration of course subjects.

Every subject in the awesome-courses ingest becomes a skill whose handler
returns the subject's field guide (``knowledge/courses/briefs/<slug>.md``).
``COURSE_SKILLS`` is built dynamically at import by reading
``knowledge/courses/catalog.json``: no hand-maintained list, so re-ingesting
the catalog registers new subjects automatically.

``category`` is always ``"curriculum"`` and the id scheme is locked to
``course_<slug_with_underscores>``. All entries are read-only (INFO risk):
they surface structured curriculum knowledge the agent can study from.
They do not confer expertise — see docs/COURSES.md for honest limits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from levi.skill.registry import Skill, SkillRisk

COURSES_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "courses"
BRIEFS_DIR = COURSES_DIR / "briefs"


def _brief_for(slug: str) -> str:
    path = BRIEFS_DIR / f"{slug}.md"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return f"No field guide ingested yet for subject {slug!r}."


def _make_handler(slug: str):
    def _handler(params: Dict) -> str:  # noqa: ANN001, ANN202
        return _brief_for(slug)

    return _handler


def _load() -> List[Skill]:
    catalog_path = COURSES_DIR / "catalog.json"
    if not catalog_path.exists():
        return []
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    skills: List[Skill] = []
    for subj in catalog.get("subjects", []):
        slug = subj["slug"]
        n = len(subj["courses"])
        skills.append(
            Skill(
                id="course_" + slug.replace("-", "_"),
                name=f"Curriculum: {subj['name']}",
                description=(
                    f"Field guide for {subj['name']}: {n} awesome-courses "
                    f"entries with schools, topic keywords, and start-here "
                    f"picks (extractive, read-only)."
                ),
                category="curriculum",
                risk_level=SkillRisk.INFO,
                handler=_make_handler(slug),
                tags=["curriculum", "courses", slug],
            )
        )
    return skills


COURSE_SKILLS: List[Skill] = _load()
