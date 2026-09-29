"""LEVI legal skill pack: data-driven registration tests.

``legal_skills.LEGAL_SKILLS`` is built by scanning
``core/levi/skill/playbooks/legal/*.md`` and parsing each file's mandatory
frontmatter block (the legal extension of the cyber pattern, with
jurisdiction, sources, requires_attorney_review, disclaimer_version, and
last_verified keys). These tests assert:

- every .md file carries valid frontmatter (all required keys, valid risk,
  id scheme ``legal_<slug_with_underscores>`` matching the filename,
  category ``legal``, non-empty jurisdiction and sources, boolean
  requires_attorney_review, ISO last_verified date);
- every playbook body has the required sections and opens with the
  general-information banner (the disclaimer is mechanical, not decorative);
- every playbook cites at least one authority URL (law.cornell.edu or an
  official .gov source) — citations or it didn't happen;
- registered count == .md file count (not a fixed number: later rings land
  in the same directory);
- safety invariants: unique ids, risk within the SkillRisk enum, every
  skill registered in SkillRegistry with category "legal";
- registry handlers return the full usable playbook (>= 1000 chars, title
  present, banner present);
- the LEGAL edition manifest in catalog.py carries the knowledge-backbone
  description, the doctrine-playbooks workflow entry, and the two new
  excluded entries (binding legal opinions, pro se court filings).

Run:  python3 tests/test_legal_skills.py     (has a real __main__ runner)
      python3 -m pytest tests/test_legal_skills.py -q
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.skill.registry import SkillRegistry, SkillRisk  # noqa: E402
from levi.skill import legal_skills  # noqa: E402

PLAYBOOK_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "legal"

# Required body sections (frontmatter stripped before checking).
REQUIRED_SECTIONS = [
    "## Purpose",
    "## The doctrine",
    "## Checklist",
    "## Red flags",
    "## Authorities",
]

# The mechanical disclaimer banner every playbook body must open with.
BANNER = "> **General legal information — not legal advice.**"

# At least one of these authority hosts must appear in every body.
AUTHORITY_HOSTS = ("law.cornell.edu", ".gov/")

# Ring 1 slugs — the Tier 1 corpus this build ships. Later rings add files
# to the same directory; the count test stays relative, this list pins the
# ring this commit promised.
RING1_SLUGS = [
    "legal_gpl_copyleft_scope",
    "legal_open_source_license_choice",
    "legal_copyright_basics",
    "legal_fair_use",
    "legal_dmca_safe_harbor",
    "legal_trademark_clearance",
    "legal_trade_secrets",
    "legal_contract_formation",
    "legal_entity_choice",
    "legal_llc_operating_agreement",
    "legal_business_tax",
    "legal_crypto_tax",
    "legal_individual_state_tax",
    "legal_estate_planning",
    "legal_dynasty_trusts",
    "legal_employment_basics",
    "legal_worker_classification",
]


def _body(path: Path) -> str:
    return legal_skills._playbook_body(path)


def _meta(path: Path):
    meta = legal_skills._parse_frontmatter(path)
    assert meta is not None, f"{path.name}: missing frontmatter block"
    return meta


def test_all_files_have_valid_frontmatter():
    files = sorted(PLAYBOOK_DIR.glob("*.md"))
    assert files, "no legal playbooks found"
    for path in files:
        meta = _meta(path)
        for key in legal_skills.FRONTMATTER_KEYS:
            assert key in meta, f"{path.name}: missing frontmatter key {key!r}"
        skill_id = str(meta["skill_id"])
        expected = "legal_" + path.stem.replace("-", "_")
        assert re.fullmatch(r"legal_[a-z0-9_]+", skill_id), (
            f"{path.name}: bad id scheme {skill_id!r}"
        )
        assert skill_id == expected, (
            f"{path.name}: skill_id {skill_id!r} != filename-derived {expected!r}"
        )
        assert str(meta["category"]).lower() == "legal", (
            f"{path.name}: category must be legal"
        )
        assert str(meta["risk"]).lower() in (
            "info",
            "low",
            "moderate",
            "high",
        ), f"{path.name}: invalid risk {meta['risk']!r}"
        assert isinstance(meta["jurisdiction"], list) and meta["jurisdiction"], (
            f"{path.name}: jurisdiction must be a non-empty list"
        )
        assert isinstance(meta["sources"], list) and meta["sources"], (
            f"{path.name}: sources must be a non-empty list"
        )
        assert isinstance(meta["requires_attorney_review"], bool), (
            f"{path.name}: requires_attorney_review must be boolean"
        )
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta["last_verified"])), (
            f"{path.name}: last_verified must be ISO date"
        )


def test_bodies_have_required_sections_and_banner():
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        body = _body(path)
        assert body.startswith(BANNER), (
            f"{path.name}: body must open with the disclaimer banner"
        )
        for section in REQUIRED_SECTIONS:
            assert section in body, f"{path.name}: missing required section {section!r}"


def test_bodies_cite_authorities():
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        body = _body(path)
        assert any(host in body for host in AUTHORITY_HOSTS), (
            f"{path.name}: no authority URL (law.cornell.edu or .gov) cited"
        )


def test_registered_count_matches_files():
    files = sorted(PLAYBOOK_DIR.glob("*.md"))
    assert len(legal_skills.LEGAL_SKILLS) == len(files), (
        f"registered {len(legal_skills.LEGAL_SKILLS)} != files {len(files)}"
    )


def test_ring1_slugs_all_registered():
    registered = {s.id for s in legal_skills.LEGAL_SKILLS}
    for slug in RING1_SLUGS:
        assert slug in registered, f"Ring 1 playbook missing: {slug}"


def test_safety_invariants():
    skills = legal_skills.LEGAL_SKILLS
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids)), "duplicate skill ids"
    for s in skills:
        assert isinstance(s.risk_level, SkillRisk), f"{s.id}: bad risk"
        assert s.category == "legal", f"{s.id}: bad category"
        assert s.handler is not None, f"{s.id}: missing handler"


def test_registry_integration():
    registry = SkillRegistry()
    legal = registry.list(category="legal")
    assert len(legal) == len(legal_skills.LEGAL_SKILLS), (
        "registry legal count != LEGAL_SKILLS count"
    )
    by_id = {s.id: s for s in legal}
    for slug in RING1_SLUGS:
        assert slug in by_id, f"registry missing {slug}"


def test_handlers_return_full_playbooks():
    for s in legal_skills.LEGAL_SKILLS:
        assert s.handler is not None
        text = s.handler({})
        assert len(text) >= 1000, f"{s.id}: handler returned stub ({len(text)} chars)"
        assert BANNER in text, f"{s.id}: handler output missing banner"
        assert s.name in text, f"{s.id}: handler output missing title"


def test_legal_edition_manifest_updated():
    from levi.editions.catalog import LEGAL

    assert "never presents itself as a lawyer" in LEGAL.description, (
        "LEGAL description must state the edition never presents as a lawyer"
    )
    assert any("doctrine playbooks" in w for w in LEGAL.workflows), (
        "LEGAL workflows must include the doctrine-playbooks entry"
    )
    excluded_names = [name for name, _ in LEGAL.excluded]
    assert "binding legal opinions" in excluded_names, (
        "LEGAL excluded must bar binding legal opinions"
    )
    assert "pro se court filings" in excluded_names, (
        "LEGAL excluded must bar pro se court filings"
    )
    assert "assists counsel" in LEGAL.tagline.lower() or "never practices" in (
        LEGAL.tagline.lower()
    ), "tagline must keep the assists-counsel stance"


TESTS = [
    test_all_files_have_valid_frontmatter,
    test_bodies_have_required_sections_and_banner,
    test_bodies_cite_authorities,
    test_registered_count_matches_files,
    test_ring1_slugs_all_registered,
    test_safety_invariants,
    test_registry_integration,
    test_handlers_return_full_playbooks,
    test_legal_edition_manifest_updated,
]


def main() -> int:
    failures = 0
    for fn in TESTS:
        try:
            fn()
        except Exception:
            failures += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
        else:
            print(f"ok   {fn.__name__}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
