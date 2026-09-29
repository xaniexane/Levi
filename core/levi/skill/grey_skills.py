"""LEVI grey-team skill library: exercise/range infrastructure.

Every playbook in ``playbooks/grey/*.md`` carries a mandatory YAML
frontmatter block (parsed with stdlib only)::

    ---
    skill_id: grey_<slug_with_underscores>
    name: Human Readable Title
    description: Single-sentence description.
    risk: moderate          # info | low | moderate | high | critical
    permissions: []
    requires_confirmation: true
    tags: [grey-team, ...]
    version: 1.0.0
    team: grey
    ---

``GREY_SKILLS`` is built dynamically at import by scanning the directory:
no hand-maintained list, so later playbook batches register automatically
with zero merge conflicts. ``category`` is always ``"cybersecurity"`` (the
red/grey packs are subdivisions of the single security corpus; the team
rides in the skill-id prefix and the tags, per the one-corpus ruling).
The id scheme is locked to ``grey_<slug_with_underscores>``.

LAWS (invariants — the test suite proves these behaviorally):
  1. Every ``*.md`` file carries complete, valid frontmatter. Invalid
     files are rejected LOUDLY (ValueError at import), never skipped.
  2. Skill ids are unique and filename-derived: ``grey_<stem>`` with
     hyphens converted to underscores. Duplicates fail the import.
  3. ``team`` is ``"grey"``; a red playbook landing in this directory
     fails the import instead of silently registering.
  4. Risk gate: ``requires_confirmation`` is True if and only if risk is
     MODERATE or higher. Destructive resets/snapshots are HIGH +
     confirmation; knowledge material (scoring rubrics, observation
     templates) may be LOW.
  5. Handlers are lazy and read-only: invoking a skill only reads its
     playbook file. Nothing executes.
  6. Every playbook body carries the exercise-guard footer, including the
     never-on-production rule.

GUARDS:
  - Strict frontmatter validation: missing keys, unknown keys, bad types,
    bad risk values, non-semver versions, and id/filename mismatches all
    raise ValueError naming the file and the reason.
  - The exercise footer is structurally required, not decorative.

PROVENANCE:
  Batch 1 (50 playbooks) is original work authored for LEVI 2026-09-29
  from scratch. No external repository was read, contacted, or copied
  during authoring. Coverage spans exercise infrastructure: provisioning
  and setup, scoring, observers/referees, and resets/snapshots. No
  Dynasty/IP material.

PROOF HONESTY:
  The accompanying tests are behavioral verification of the laws above
  (property tests over frontmatter, ids, risk gates, lazy invocation) —
  not formal proof. They demonstrate the invariants hold for the shipped
  corpus; they do not prove them for all possible inputs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from levi.skill.registry import Skill, SkillRisk

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks" / "grey"

FRONTMATTER_KEYS = (
    "skill_id",
    "name",
    "description",
    "risk",
    "permissions",
    "requires_confirmation",
    "tags",
    "version",
    "team",
)

_RISK_BY_NAME = {
    "info": SkillRisk.INFO,
    "low": SkillRisk.LOW,
    "moderate": SkillRisk.MODERATE,
    "high": SkillRisk.HIGH,
    "critical": SkillRisk.CRITICAL,
}
_RISK_NAME = {v: k for k, v in _RISK_BY_NAME.items()}

_ID_RE = re.compile(r"grey_[a-z0-9_]+\Z")
_BOOL_RE = re.compile(r"\A(true|false)\Z")
_SEMVER_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")
# Only the head of each file is ever needed for frontmatter.
_FRONTMATTER_HEAD_BYTES = 32768

# Structural guard: every grey playbook must carry this footer marker,
# which includes the never-on-production rule.
_EXERCISE_FOOTER_MARKER = "Exercise guard."


def _fail(path: Path, reason: str) -> "ValueError":
    return ValueError(f"grey_skills: {path.name}: {reason}")


def _parse_frontmatter(path: Path) -> Dict[str, object]:
    """Parse the mandatory frontmatter block using stdlib only.

    Raises ValueError naming the file on any malformation: missing block,
    missing keys, or unknown keys.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read(_FRONTMATTER_HEAD_BYTES)
    except OSError as exc:
        raise _fail(path, f"unreadable: {exc}") from exc
    if not text.startswith("---\n"):
        raise _fail(path, "missing frontmatter block (must open with ---)")
    end = text.find("\n---", 4)
    if end == -1:
        raise _fail(path, "unterminated frontmatter block")
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
            if key in meta:
                raise _fail(path, f"duplicate frontmatter key: {key!r}")
            meta[key] = value
    missing = [k for k in FRONTMATTER_KEYS if k not in meta]
    if missing:
        raise _fail(path, f"missing frontmatter keys: {missing}")
    unknown = [k for k in meta if k not in FRONTMATTER_KEYS]
    if unknown:
        raise _fail(path, f"unknown frontmatter keys: {unknown}")
    return meta


def _skill_from_meta(path: Path, meta: Dict[str, object]) -> Skill:
    """Build a Skill from parsed frontmatter; raises on any invalidity."""
    skill_id = str(meta["skill_id"])
    expected_id = "grey_" + path.stem.replace("-", "_")
    if not _ID_RE.match(skill_id):
        raise _fail(path, f"skill_id {skill_id!r} not of form grey_<slug>")
    if skill_id != expected_id:
        raise _fail(
            path, f"skill_id {skill_id!r} != filename-derived {expected_id!r}"
        )
    if str(meta["team"]) != "grey":
        raise _fail(path, f"team must be 'grey', got {meta['team']!r}")
    risk = _RISK_BY_NAME.get(str(meta["risk"]).lower())
    if risk is None:
        raise _fail(path, f"unknown risk {meta['risk']!r}")
    permissions = meta["permissions"]
    tags = meta["tags"]
    requires_confirmation = meta["requires_confirmation"]
    if not isinstance(permissions, list) or not all(
        isinstance(p, str) for p in permissions
    ):
        raise _fail(path, "permissions must be a list of strings")
    if (
        not isinstance(tags, list)
        or not tags
        or not all(isinstance(t, str) and t for t in tags)
    ):
        raise _fail(path, "tags must be a non-empty list of strings")
    if not isinstance(requires_confirmation, bool):
        raise _fail(path, "requires_confirmation must be true/false")
    # Risk gate (law 4): confirmation iff MODERATE or higher.
    want_confirm = risk in (
        SkillRisk.MODERATE,
        SkillRisk.HIGH,
        SkillRisk.CRITICAL,
    )
    if requires_confirmation != want_confirm:
        raise _fail(
            path,
            f"risk {_RISK_NAME[risk]} requires requires_confirmation="
            f"{str(want_confirm).lower()}",
        )
    name = str(meta["name"]).strip()
    description = str(meta["description"]).strip()
    if not name:
        raise _fail(path, "name must be non-empty")
    if not description:
        raise _fail(path, "description must be non-empty")
    version = str(meta["version"])
    if not _SEMVER_RE.match(version):
        raise _fail(path, f"version {version!r} is not semver")
    # Structural guard: the exercise footer must be present.
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _fail(path, f"unreadable body: {exc}") from exc
    if _EXERCISE_FOOTER_MARKER not in body:
        raise _fail(path, "missing exercise-guard footer")

    def _handler(_args: dict, _path: Path = path) -> str:
        # Lazy and read-only: the playbook file is read only when the
        # skill is invoked. Invoking a grey skill never executes anything;
        # it returns the playbook text for the operator to read.
        try:
            return _path.read_text(encoding="utf-8")
        except OSError as exc:
            return f"grey skill playbook unavailable: {exc}"

    return Skill(
        id=skill_id,
        name=name,
        description=description,
        category="cybersecurity",
        version=version,
        risk_level=risk,
        permissions=[str(p) for p in permissions],
        requires_confirmation=requires_confirmation,
        tags=[str(t) for t in tags],
        handler=_handler,
    )


def load_grey_skills(playbook_dir: Path = PLAYBOOK_DIR) -> List[Skill]:
    """Scan *playbook_dir* and build every Skill. Raises ValueError on the
    first invalid file — invalid playbooks are rejected loudly, never
    skipped. Duplicate skill ids also raise."""
    if not playbook_dir.is_dir():
        raise ValueError(f"grey_skills: playbook dir missing: {playbook_dir}")
    skills: List[Skill] = []
    seen: Dict[str, Path] = {}
    for path in sorted(playbook_dir.glob("*.md")):
        skill = _skill_from_meta(path, _parse_frontmatter(path))
        if skill.id in seen:
            raise ValueError(
                f"grey_skills: duplicate skill id {skill.id!r}: "
                f"{seen[skill.id].name} and {path.name}"
            )
        seen[skill.id] = path
        skills.append(skill)
    if not skills:
        raise ValueError(f"grey_skills: no playbooks found in {playbook_dir}")
    return skills


# The full registration list, built dynamically at import.
# SkillRegistry consumes this (import + extend).
GREY_SKILLS: List[Skill] = load_grey_skills()
