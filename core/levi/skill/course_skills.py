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
import re
import sys
from pathlib import Path
from typing import Dict, List

from levi.skill.registry import Skill, SkillRisk

COURSES_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "courses"
BRIEFS_DIR = COURSES_DIR / "briefs"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _brief_for(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        return f"Invalid subject slug {slug!r}."
    path = BRIEFS_DIR / f"{slug}.md"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return f"No field guide ingested yet for subject {slug!r}."


def _make_handler(slug: str):
    def _handler(params: Dict) -> str:  # noqa: ANN001, ANN202
        return _brief_for(slug)

    return _handler


def _load() -> List[Skill]:
    """Build the curriculum skills from the catalog.

    Never raises: a missing or corrupt catalog degrades to no course
    skills (with a stderr note), and malformed subject entries are
    skipped so one bad record cannot hide the valid ones.
    """
    catalog_path = COURSES_DIR / "catalog.json"
    if not catalog_path.exists():
        return []
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(
            f"[levi:course_skills] corrupt catalog {catalog_path}: {exc} — "
            "no curriculum skills registered.",
            file=sys.stderr,
        )
        return []
    if not isinstance(catalog, dict):
        print(
            f"[levi:course_skills] catalog {catalog_path} is not an object — "
            "no curriculum skills registered.",
            file=sys.stderr,
        )
        return []
    skills: List[Skill] = []
    subjects = catalog.get("subjects", [])
    if not isinstance(subjects, list):
        return []
    for subj in subjects:
        if not isinstance(subj, dict):
            continue
        slug = subj.get("slug")
        name = subj.get("name")
        courses = subj.get("courses")
        if (
            not isinstance(slug, str)
            or not _SLUG_RE.match(slug)
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(courses, list)
        ):
            continue
        n = len(courses)
        skills.append(
            Skill(
                id="course_" + slug.replace("-", "_"),
                name=f"Curriculum: {name}",
                description=(
                    f"Field guide for {name}: {n} awesome-courses "
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
