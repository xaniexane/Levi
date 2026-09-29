"""LEVI legal skill library: data-driven registration.

Every playbook in ``playbooks/legal/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only)::

    ---
    skill_id: legal_<slug_with_underscores>
    name: Human Readable Title
    description: Single-sentence description.
    category: legal
    risk: info                 # info | low | moderate | high
    permissions: []
    requires_confirmation: false
    jurisdiction: [US-federal] # explicit per file; IL where state-specific
    sources: [https://...]     # authorities, cited inline in the body too
    requires_attorney_review: true|false
    disclaimer_version: 1.0
    last_verified: 2026-09-28
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``LEGAL_SKILLS`` is built dynamically at import by scanning the directory:
no hand-maintained list, so later rings (Tier 2, Tier 3) register
automatically with zero merge conflicts. ``category`` is always
``"legal"`` and the id scheme is locked to ``legal_<slug_with_underscores>``.

The corpus is small (Ring 1: 17 playbooks), so every import does a full
directory scan — no precomputed manifest, no staleness modes. If a later
ring grows the corpus past a few hundred files, add a manifest following
the ``cyber_skills`` pattern.

Compliance posture: every playbook body opens with the general-information
banner (mechanical, not decorative). Playbooks whose outputs are
substantive carry ``requires_attorney_review: true``; the skill layer
surfaces that gate the way ``requires_confirmation`` works for cyber.
Nothing here is legal advice, nothing forms an attorney-client
relationship, and nothing here substitutes for a licensed attorney.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "legal"

FRONTMATTER_KEYS = (
    "skill_id",
    "name",
    "description",
    "category",
    "risk",
    "permissions",
    "requires_confirmation",
    "jurisdiction",
    "sources",
    "requires_attorney_review",
    "disclaimer_version",
    "last_verified",
    "tags",
    "version",
)

_RISK_BY_NAME = {
    "info": SkillRisk.INFO,
    "low": SkillRisk.LOW,
    "moderate": SkillRisk.MODERATE,
    "high": SkillRisk.HIGH,
}
_RISK_NAME = {v: k for k, v in _RISK_BY_NAME.items()}

_ID_RE = re.compile(r"legal_[a-z0-9_]+\Z")
_BOOL_RE = re.compile(r"\A(true|false)\Z")
_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")

# Only the head of each file is ever needed for frontmatter.
_FRONTMATTER_HEAD_BYTES = 8192


def _parse_frontmatter(path: Path) -> Optional[Dict[str, object]]:
    """Parse the mandatory frontmatter block using stdlib only.

    Supports ``key: value`` lines, ``[...]`` inline lists and
    true/false. Returns None when no well-formed block is present.
    Only the file head is read: frontmatter always opens the file.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read(_FRONTMATTER_HEAD_BYTES)
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


def _playbook_body(path: Path) -> str:
    """Playbook markdown with the frontmatter block stripped."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"legal skill playbook unavailable: {exc}"
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def _skill_from_meta(
    skill_id: str, meta: Dict[str, object], path: Path
) -> Optional[Skill]:
    """Build a Skill from parsed frontmatter; None if it is not usable.

    Files without a valid frontmatter block are skipped (never crash the
    import). The test suite enforces the invariant that every file carries
    valid frontmatter, including the legal-specific keys.
    """
    if any(k not in meta for k in FRONTMATTER_KEYS):
        return None
    expected_id = "legal_" + path.stem.replace("-", "_")
    if not _ID_RE.match(skill_id) or skill_id != expected_id:
        return None
    if str(meta.get("category", "")).lower() != "legal":
        return None
    risk = _RISK_BY_NAME.get(str(meta["risk"]).lower())
    if risk is None:
        return None
    permissions = meta["permissions"]
    tags = meta["tags"]
    jurisdiction = meta["jurisdiction"]
    sources = meta["sources"]
    requires_confirmation = meta["requires_confirmation"]
    requires_attorney_review = meta["requires_attorney_review"]
    last_verified = str(meta["last_verified"])
    if (
        not isinstance(permissions, list)
        or not isinstance(tags, list)
        or not isinstance(jurisdiction, list)
        or not jurisdiction
        or not isinstance(sources, list)
        or not sources
        or not isinstance(requires_confirmation, bool)
        or not isinstance(requires_attorney_review, bool)
        or not _DATE_RE.match(last_verified)
    ):
        return None

    def _handler(_args: dict, _path: Path = path) -> str:
        # Lazy: the playbook file is read only when the skill is invoked.
        # The full file (frontmatter included) is returned so the
        # disclaimer, jurisdiction, and sources travel with the content.
        try:
            return _path.read_text(encoding="utf-8")
        except OSError as exc:
            return f"legal skill playbook unavailable: {exc}"

    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="legal",
        version=str(meta["version"]),
        risk_level=risk,
        permissions=[str(p) for p in permissions],
        requires_confirmation=requires_confirmation,
        tags=[str(t) for t in tags]
        + [f"jurisdiction:{j}" for j in jurisdiction]
        + (["requires_attorney_review"] if requires_attorney_review else []),
        handler=_handler,
    )


def _skill_from_file(path: Path) -> Optional[Skill]:
    """Build a Skill from one playbook file; None if it is not usable."""
    meta = _parse_frontmatter(path)
    if meta is None:
        return None
    skill_id = str(meta.get("skill_id", ""))
    return _skill_from_meta(skill_id, meta, path)


def _load_legal_skills() -> List[Skill]:
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
LEGAL_SKILLS: List[Skill] = _load_legal_skills()
