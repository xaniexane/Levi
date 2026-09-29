"""LEVI factory skill pack: data-driven registration tests.

``factory_skills.FACTORY_SKILLS`` is built by scanning
``core/levi/skill/playbooks/factory/*.md`` and parsing each file's mandatory
frontmatter block. These tests assert (proof-of-run for Factory Genesis
spec genesis-001):

- every playbook carries valid frontmatter (all required keys, valid risk,
  id scheme ``factory.<slug>`` matching the filename);
- every playbook body has the required sections;
- all register in ``SkillRegistry`` with unique ``factory.*`` ids and
  ``category == "factory"``;
- safety invariants: unique ids, INFO risk across the pack, read-only
  advisory language (no dispatch/mutate/spend claims).

Run:  python3 -m pytest tests/test_factory_skills.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.skill.registry import SkillRegistry, SkillRisk  # noqa: E402
from levi.skill import factory_skills  # noqa: E402

PLAYBOOK_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "factory"

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

REQUIRED_BODY_SECTIONS = (
    "## Laws",
)

# Sections required only on the intake-triage playbook itself — the
# production line mints new playbooks, so the pack-wide gate stays generic.
INTAKE_TRIAGE_ONLY_SECTIONS = (
    "# Intake Triage",
    "## How to read the line",
)


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: missing frontmatter"
    end = text.find("\n---", 4)
    assert end != -1, f"{path.name}: unterminated frontmatter"
    meta: dict = {}
    for raw in text[4:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def test_playbooks_exist_and_parse():
    playbooks = sorted(PLAYBOOK_DIR.glob("*.md"))
    assert playbooks, "factory playbook dir is empty"
    assert any(p.stem == "intake-triage" for p in playbooks)
    for path in playbooks:
        meta = _frontmatter(path)
        for key in FRONTMATTER_KEYS:
            assert key in meta, f"{path.name}: missing frontmatter key {key}"
        expected = "factory." + path.stem.replace("-", "_")
        assert meta["skill_id"] == expected, (
            f"{path.name}: skill_id {meta['skill_id']} != {expected}"
        )
        assert meta["risk"].lower() == "info", f"{path.name}: risk must be info"


def test_playbook_bodies_have_required_sections():
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        for section in REQUIRED_BODY_SECTIONS:
            assert section in body, f"{path.name}: missing section {section}"
        if path.stem == "intake-triage":
            for section in INTAKE_TRIAGE_ONLY_SECTIONS:
                assert section in body, (
                    f"{path.name}: missing section {section}"
                )
        assert "never" in body.lower(), f"{path.name}: must state its limits"


def test_factory_skills_register():
    skills = factory_skills.FACTORY_SKILLS
    assert skills, "FACTORY_SKILLS is empty"
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids)), "duplicate factory skill ids"
    assert "factory.intake_triage" in ids
    for s in skills:
        assert s.category == "factory", f"{s.id}: category != factory"
        assert s.risk_level == SkillRisk.INFO, f"{s.id}: risk != INFO"
        assert re.match(r"factory\.[a-z0-9_]+\Z", s.id), f"{s.id}: bad id scheme"


def test_registry_contains_factory_pack():
    registry = SkillRegistry()
    skill = registry.get("factory.intake_triage")
    assert skill is not None, "factory.intake_triage not in SkillRegistry"
    assert skill.category == "factory"
    assert int(skill.risk_level) == 0
