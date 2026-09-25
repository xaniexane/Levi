"""LEVI twin-pair skill pack: data-driven registration.

Every playbook in ``playbooks/twinpair/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only — same shape as the compressed
pack, self-contained parser)::

    ---
    skill_id: twinpair.<slug>
    name: Human Readable Title
    description: Single-sentence description.
    risk: info            # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: false
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``TWINPAIR_SKILLS`` is built dynamically at import by scanning the
directory: no hand-maintained list, so later batches register
automatically with zero merge conflicts. ``category`` is always
``"twin-pair"`` and the id scheme is locked to ``twinpair.<slug>``.

This pack rebuilds the expander canon as LEVI-native originals: twin-pair
moves where two engines have to match (Echo×Mandella, REIM×RIEM), the
circuit-breaker veto that refuses bad pairings, and the point-inward
operating instruction. Advisory across the pack; nothing here acts,
sends, or spends.

The module declares itself to the interop registry at import time
(runtime self-registration is the documented path for new modules).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "twinpair"

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

_ID_RE = re.compile(r"twinpair\.[a-z0-9_-]+\Z")
_BOOL_RE = re.compile(r"\A(true|false)\Z")


def _parse_frontmatter(path: Path) -> Optional[Dict[str, object]]:
    """Parse the mandatory frontmatter block using stdlib only."""
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
    """Build a Skill from one playbook file; None if it is not usable."""
    meta = _parse_frontmatter(path)
    if not meta:
        return None
    skill_id = str(meta.get("skill_id", ""))
    expected_id = f"twinpair.{path.stem}"
    if not _ID_RE.match(skill_id) or skill_id != expected_id:
        return None
    if not all(meta.get(k) for k in ("name", "description")):
        return None
    risk = _RISK_BY_NAME.get(str(meta.get("risk", "info")).lower(), SkillRisk.INFO)
    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="twin-pair",
        risk_level=risk,
        permissions=list(meta.get("permissions") or []),
        requires_confirmation=bool(meta.get("requires_confirmation", False)),
        tags=list(meta.get("tags") or []),
        version=str(meta.get("version", "1.0.0")),
        handler=None,
    )


def _load_skills() -> List[Skill]:
    if not PLAYBOOK_DIR.is_dir():
        return []
    skills = []
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        skill = _skill_from_file(path)
        if skill is not None:
            skills.append(skill)
    return skills


TWINPAIR_SKILLS: List[Skill] = _load_skills()


def expected_ids() -> List[str]:
    """Every playbook file's locked id — used by the test suite."""
    if not PLAYBOOK_DIR.is_dir():
        return []
    return [f"twinpair.{p.stem}" for p in sorted(PLAYBOOK_DIR.glob("*.md"))]


def get_skill(skill_id: str) -> Optional[Skill]:
    """Look up one twin-pair skill by id; None when unknown."""
    for skill in TWINPAIR_SKILLS:
        if skill.id == skill_id:
            return skill
    return None


# -- runtime self-registration with the interop capability registry -------
# The static manifest (levi.interop.manifest) is additive-only for existing
# modules; new modules declare themselves at runtime through register().


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    provides = [f"skill.{s.id}" for s in TWINPAIR_SKILLS]
    try:
        register(
            "skill-twinpair",
            provides=tuple(provides),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
