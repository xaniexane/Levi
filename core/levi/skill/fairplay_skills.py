"""LEVI fairplay skill library: data-driven registration.

Every playbook in ``playbooks/fairplay/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only)::

    ---
    skill_id: fairplay.<slug>
    name: Human Readable Title
    description: Single-sentence description.
    category: fairplay
    risk: info            # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: false
    tags: [tag1, tag2]
    version: 1.0.0
    ---

``FAIRPLAY_SKILLS`` is built dynamically at import by scanning the directory:
no hand-maintained list, so later fairplay playbooks register automatically
with zero merge conflicts. ``category`` is always ``"fairplay"`` and the id
scheme is locked to ``fairplay.<slug>`` (slug = filename stem).

Handlers are advisory by default — they return the playbook procedure text.
``fairplay.audit_offer`` additionally *executes* the real sly-trade detector
(``levi.fairplay.audit.audit_offer``) when the caller passes an ``offer``
mapping in args; a non-mapping ``offer`` is refused honestly, never guessed.

Defensive blue-team: detection and honest alternatives only. Risk is INFO
across the pack; the detector is pure (reads the offer, never mutates it).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "fairplay"

FRONTMATTER_KEYS = (
    "skill_id",
    "name",
    "description",
    "category",
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

_ID_RE = re.compile(r"fairplay\.[a-z0-9_]+\Z")
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
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if key not in FRONTMATTER_KEYS:
            continue
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            meta[key] = (
                [p.strip() for p in inner.split(",") if p.strip()] if inner else []
            )
        elif _BOOL_RE.match(raw):
            meta[key] = raw == "true"
        else:
            meta[key] = raw
    return meta


def _render_audit(offer: Mapping) -> str:
    """Run the real sly-trade detector and render the verdict as text."""
    from levi.fairplay.audit import audit_offer

    report = audit_offer(offer)
    lines = [
        f"offer: {report.offer_name}",
        f"verdict: {report.verdict()}",
        f"sly: {report.sly_count()} | caution: {report.caution_count()}",
    ]
    for finding in report.findings:
        lines.append(
            f"- [{finding.severity}] {finding.pattern}: {finding.evidence} "
            f"-> honest alternative: {finding.honest_alternative}"
        )
    return "\n".join(lines)


def _audit_handler(args: Optional[dict], path: Path) -> str:
    """Advisory playbook text, or a live audit when an offer is passed."""
    args = args or {}
    if "offer" not in args:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            return f"fairplay skill playbook unavailable: {exc}"
    offer = args["offer"]
    if not isinstance(offer, Mapping):
        return (
            "fairplay.audit_offer refused: 'offer' must be a mapping of "
            f"declared claims, got {type(offer).__name__} — nothing was "
            "audited, nothing was guessed."
        )
    return _render_audit(offer)


def _skill_from_file(path: Path) -> Optional[Skill]:
    """Build a Skill from one playbook file; None if it is not usable.

    Files without a valid frontmatter block are skipped (never crash the
    import). The test suite enforces the invariant that every file carries
    valid frontmatter.
    """
    meta = _parse_frontmatter(path)
    if meta is None:
        return None
    if (
        any(k not in meta for k in FRONTMATTER_KEYS)
        or str(meta["category"]) != "fairplay"
    ):
        return None
    skill_id = str(meta["skill_id"])
    expected_id = "fairplay." + path.stem
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

    if skill_id == "fairplay.audit_offer":

        def _handler(_args: Optional[dict] = None, _path: Path = path) -> str:
            return _audit_handler(_args, _path)

    else:

        def _handler(_args: Optional[dict] = None, _path: Path = path) -> str:
            try:
                return _path.read_text(encoding="utf-8")
            except OSError as exc:
                return f"fairplay skill playbook unavailable: {exc}"

    return Skill(
        id=skill_id,
        name=str(meta["name"]),
        description=str(meta["description"]),
        category="fairplay",
        version=str(meta["version"]),
        risk_level=risk,
        permissions=[str(p) for p in permissions],
        requires_confirmation=requires_confirmation,
        tags=[str(t) for t in tags],
        handler=_handler,
    )


def _load_fairplay_skills() -> List[Skill]:
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
FAIRPLAY_SKILLS: List[Skill] = _load_fairplay_skills()
