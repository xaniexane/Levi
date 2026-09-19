"""LEVI operator skill pack: data-driven registration tests.

``operator_skills.OPERATOR_SKILLS`` is built by scanning
``core/levi/skill/playbooks/operator/*.md`` and parsing each file's mandatory
frontmatter block. These tests assert:

- exactly 17 playbooks exist and all load via the loader;
- every playbook carries valid frontmatter (all required keys, valid risk,
  id scheme ``operator.<slug>`` matching the filename);
- every playbook body has the required sections;
- all 17 register in ``SkillRegistry`` with unique ``operator.*`` ids and
  ``category == "operator"``;
- ``chips.json`` holds exactly 7 chips, each with non-empty id/label/inject;
- safety invariants: unique ids, INFO risk across the pack, no forbidden
  identity terms in any operator text.

Run:  python3 -m pytest tests/test_operator_skills.py -q
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.skill.registry import SkillRegistry, SkillRisk  # noqa: E402
from levi.skill import operator_skills  # noqa: E402

PLAYBOOK_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "operator"
CHIPS_PATH = ROOT / "core" / "levi" / "skill" / "chips.json"

EXPECTED_IDS = [
    "operator.stress",
    "operator.eighty",
    "operator.mvd",
    "operator.ship",
    "operator.lock",
    "operator.triage",
    "operator.review",
    "operator.deep",
    "operator.blocker",
    "operator.actions",
    "operator.no",
    "operator.streak",
    "operator.spark",
    "operator.cut",
    "operator.voice",
    "operator.title",
    "operator.xyz",
]

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

REQUIRED_SECTIONS = ("## Purpose", "## When to use", "## Steps", "## Honesty notes")

# Identity rule: the reference product is never named in code, docs, IDs, or
# skill text. (Checked case-insensitively.)
FORBIDDEN_TERMS = ("kai9000", "kai-9000", "muse kai9000")


def _files():
    return sorted(PLAYBOOK_DIR.glob("*.md"))


def test_exactly_seventeen_playbooks_present():
    files = _files()
    assert len(files) == 17, f"expected 17 operator playbooks, found {len(files)}"


def test_all_seventeen_load_via_loader():
    skills = operator_skills.OPERATOR_SKILLS
    assert len(skills) == 17
    assert sorted(s.id for s in skills) == sorted(EXPECTED_IDS)


def test_ids_unique_and_operator_namespaced():
    ids = [s.id for s in operator_skills.OPERATOR_SKILLS]
    assert len(set(ids)) == len(ids), "duplicate operator skill ids"
    for skill_id in ids:
        assert skill_id.startswith("operator."), f"bad namespace: {skill_id}"
        assert re.match(r"operator\.[a-z0-9_]+\Z", skill_id), f"bad id: {skill_id}"


def test_frontmatter_valid_on_every_playbook():
    for path in _files():
        meta = operator_skills._parse_frontmatter(path)
        assert meta is not None, f"{path.name}: missing frontmatter"
        for key in FRONTMATTER_KEYS:
            assert key in meta, f"{path.name}: missing frontmatter key {key}"
        skill_id = str(meta["skill_id"])
        expected = "operator." + path.stem.replace("-", "_")
        assert skill_id == expected, f"{path.name}: id {skill_id} != {expected}"
        assert str(meta["risk"]).lower() == "info", f"{path.name}: risk must be info"
        assert meta["permissions"] == [], f"{path.name}: permissions must be []"
        assert meta["requires_confirmation"] is False
        assert isinstance(meta["tags"], list) and len(meta["tags"]) >= 1
        assert str(meta["name"]).strip()
        assert str(meta["description"]).strip()


def test_playbook_bodies_have_required_sections():
    for path in _files():
        text = path.read_text(encoding="utf-8")
        # Strip the frontmatter block before checking body sections.
        end = text.find("\n---", 4)
        body = text[end + 4 :] if text.startswith("---\n") and end != -1 else text
        for section in REQUIRED_SECTIONS:
            assert section in body, f"{path.name}: missing section {section}"


def test_registry_registers_all_seventeen():
    registry = SkillRegistry()
    for skill_id in EXPECTED_IDS:
        skill = registry.get(skill_id)
        assert skill is not None, f"{skill_id} not registered"
        assert skill.category == "operator", f"{skill_id}: wrong category"
        assert skill.risk_level == SkillRisk.INFO, f"{skill_id}: wrong risk"
        assert callable(skill.handler)
        # The handler returns the playbook text.
        rendered = skill.handler({})
        assert "operator." in rendered or skill.name in rendered


def test_chips_json_exactly_seven_valid_entries():
    raw = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list) and len(raw) == 7, "chips.json must hold 7 chips"
    ids = []
    for entry in raw:
        assert isinstance(entry, dict)
        for key in ("id", "label", "inject"):
            value = entry.get(key)
            assert isinstance(value, str) and value.strip(), f"chip bad {key}: {entry}"
        assert entry["id"].startswith("chip."), f"bad chip id: {entry['id']}"
        ids.append(entry["id"])
    assert len(set(ids)) == 7, "duplicate chip ids"
    # Loader agrees with the file.
    loaded = operator_skills.load_chips()
    assert [c["id"] for c in loaded] == ids


def test_no_forbidden_identity_terms():
    checked = 0
    for path in list(_files()) + [CHIPS_PATH]:
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_TERMS:
            assert term not in text, f"{path.name}: forbidden term {term!r}"
        checked += 1
    module_text = Path(operator_skills.__file__).read_text(encoding="utf-8").lower()
    for term in FORBIDDEN_TERMS:
        assert term not in module_text, f"operator_skills.py: forbidden term {term!r}"
    assert checked == 18
