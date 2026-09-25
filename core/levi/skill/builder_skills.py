"""LEVI builder skill library: data-driven registration.

Every playbook in ``playbooks/builder/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only)::

    ---
    skill_id: builder.<slug>
    name: Human Readable Title
    description: Single-sentence description.
    risk: info            # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: false
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``BUILDER_SKILLS`` is built dynamically at import by scanning the
directory: no hand-maintained list, so later playbook batches register
automatically with zero merge conflicts. ``category`` is always
``"builder"`` and the id scheme is locked to ``builder.<slug>``.

The builder lens: how a keeper ships — small diffs, honest receipts,
named patterns, working trails. Advisory only: no system actions, no
surveillance, no coercion. Risk is INFO across the pack.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "builder"

FRONTMATTER_KEYS = (
    "skill_id",
    "name",
    "description",
    "risk",
    "permissions",
    "requires_confirmation",
    "tags",
    "version",
)

_RISK_BY_NAME = {
    "info": SkillRisk.INFO,
    "low": SkillRisk.LOW,
    "moderate": SkillRisk.MODERATE,
    "high": SkillRisk.HIGH,
    "critical": SkillRisk.CRITICAL,
}

_ID_RE = re.compile(r"builder\.[a-z0-9_]+\Z")
_BOOL_RE = re.compile(r"\A(true|false)\Z")


def _parse_frontmatter(path: Path) -> Optional[Dict[str, object]]:
    """Parse the mandatory frontmatter block using stdlib only.

    Supports ``key: value`` lines, ``[...]`` inline lists and
    true/false. Returns None when no well-formed block is present.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    meta: Dict[str, object] = {}
    for raw in text[4:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [  # type: ignore[assignment]
                item.strip().strip("'\"")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        elif _BOOL_RE.match(value.lower()):
            value = value.lower() == "true"  # type: ignore[assignment]
        else:
            value = value.strip("'\"")  # type: ignore[assignment]
        if key:
            meta[key] = value
    return meta


def _skill_from_file(path: Path) -> Optional[Skill]:
    """Build a Skill from one playbook file; None if it is not usable.

    Files without a valid frontmatter block are skipped (never crash
    the import: a second writer batch lands files in this directory
    while it is still being written). The test suite enforces the
    invariant that every file carries valid frontmatter.
    """
    meta = _parse_frontmatter(path)
    if meta is None:
        return None
    if any(k not in meta for k in FRONTMATTER_KEYS):
        return None
    skill_id = str(meta["skill_id"])
    expected_id = "builder." + path.stem.replace("-", "_")
    if not _ID_RE.match(skill_id) or skill_id != expected_id:
        return None
    risk = _RISK_BY_NAME.get(str(meta["risk"]).lower())
    if risk is None:
        return None
    permissions = meta["permissions"]
    tags = meta["tags"]
    requires_confirmation = meta["requires_confirmation"]
    if (
        not isinstance(permissions, list)
        or not isinstance(tags, list)
        or not isinstance(requires_confirmation, bool)
    ):
        return None

    def _handler(_args: dict, _path: Path = path) -> str:
        try:
            return _path.read_text(encoding="utf-8")
        except OSError as exc:
            return f"builder skill playbook unavailable: {exc}"

    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="builder",
        version=str(meta["version"]),
        risk_level=risk,
        permissions=[str(p) for p in permissions],
        requires_confirmation=requires_confirmation,
        tags=[str(t) for t in tags],
        handler=_handler,
    )


def _load_builder_skills() -> List[Skill]:
    """Scan the playbook directory and build every Skill dynamically."""
    skills: List[Skill] = []
    if not PLAYBOOK_DIR.is_dir():
        return skills
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        skill = _skill_from_file(path)
        if skill is not None:
            skills.append(skill)
    return skills


# The full registration list, built dynamically at import.
# SkillRegistry consumes this (import + extend).
BUILDER_SKILLS: List[Skill] = _load_builder_skills()
