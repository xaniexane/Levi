"""LEVI operator skill library: data-driven registration.

Every playbook in ``playbooks/operator/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only)::

    ---
    skill_id: operator.<slug>
    name: Human Readable Title
    description: Single-sentence description.
    risk: info            # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: false
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``OPERATOR_SKILLS`` is built dynamically at import by scanning the directory:
no hand-maintained list, so later playbook batches register automatically
with zero merge conflicts. ``category`` is always ``"operator"`` and the id
scheme is locked to ``operator.<slug>``.

All 16 playbooks are original works authored for LEVI (productivity lens:
planning, focus, shipping, honest review — operating leverage for the
human). They are advisory only: no system actions, no surveillance, no
coercion. Risk is INFO across the pack.

``CHIPS`` / ``load_chips()`` expose the one-tap prompt chips from
``chips.json`` (id, label, inject) for UI surfaces that want to offer them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "operator"
CHIPS_PATH = Path(__file__).resolve().parent / "chips.json"

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

_ID_RE = re.compile(r"operator\.[a-z0-9_]+\Z")
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

    Files without a valid frontmatter block are skipped (never crash the
    import: a second writer batch lands files in this directory while it
    is still being written). The test suite enforces the invariant that
    every file carries valid frontmatter.
    """
    meta = _parse_frontmatter(path)
    if meta is None:
        return None
    if any(k not in meta for k in FRONTMATTER_KEYS):
        return None
    skill_id = str(meta["skill_id"])
    expected_id = "operator." + path.stem.replace("-", "_")
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
            return f"operator skill playbook unavailable: {exc}"

    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="operator",
        version=str(meta["version"]),
        risk_level=risk,
        permissions=[str(p) for p in permissions],
        requires_confirmation=requires_confirmation,
        tags=[str(t) for t in tags],
        handler=_handler,
    )


def _load_operator_skills() -> List[Skill]:
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
OPERATOR_SKILLS: List[Skill] = _load_operator_skills()


def load_chips() -> List[Dict[str, str]]:
    """Load the one-tap prompt chips from ``chips.json`` (stdlib only).

    Returns a list of ``{"id", "label", "inject"}`` dicts. Raises
    ``ValueError`` on malformed data so bad chips fail loudly at load
    time rather than silently in a UI.
    """
    try:
        raw = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"chips.json unavailable: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("chips.json must be a JSON array")
    chips: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each chip must be an object")
        for key in ("id", "label", "inject"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"chip missing non-empty string field {key!r}")
        chips.append(
            {
                "id": entry["id"].strip(),
                "label": entry["label"].strip(),
                "inject": entry["inject"].strip(),
            }
        )
    return chips


# The chip list, loaded at import alongside the skills.
CHIPS: List[Dict[str, str]] = load_chips()
