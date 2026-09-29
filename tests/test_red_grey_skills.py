"""LEVI red-team and grey-team skill packs: registration tests.

``red_skills.RED_SKILLS`` / ``grey_skills.GREY_SKILLS`` are built by
scanning ``core/levi/skill/playbooks/red|grey/*.md`` and parsing each
file's mandatory frontmatter block. These tests assert:

- every .md file carries complete, valid frontmatter (all required keys,
  no unknown keys, valid risk, id scheme ``red_<slug>`` / ``grey_<slug>``
  matching the filename);
- every playbook body has the required sections and its team footer
  (red: authorization guard; grey: exercise guard);
- registered count == .md file count (not a fixed number: later batches
  land in the same directories);
- every red skill names a well-formed ``tests_blue`` id that resolves
  against the live cyber library (fail loudly on a missing counterpart);
- risk gate: requires_confirmation is True iff risk is MODERATE or higher;
- invalid playbooks are rejected LOUDLY (ValueError), never skipped:
  missing/unknown keys, id/filename mismatch, duplicate ids, bad risk,
  bad confirmation flag, wrong team, malformed tests_blue, missing
  footer, missing frontmatter block;
- safety invariants: unique ids, risk within the SkillRisk enum,
  MODERATE+ skills confirmation-gated, category "cybersecurity";
- handlers are lazy and read-only: invoking returns the full playbook
  text (>= 1000 chars, title present);
- the registry registers every red and grey skill.

Run:  python3 tests/test_red_grey_skills.py     (has a real __main__ runner)
      python3 -m pytest tests/test_red_grey_skills.py -q
"""

from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.skill.registry import SkillRegistry, SkillRisk  # noqa: E402
from levi.skill import red_skills, grey_skills  # noqa: E402

RED_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "red"
GREY_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "grey"

REQUIRED_SECTIONS = [
    "## Purpose",
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Expected outputs",
    "## Pitfalls",
    "## References",
]

RED_EXTRA_MARKERS = ["Blue-team control under test", "Authorization guard."]
GREY_EXTRA_MARKERS = ["Exercise role", "Exercise guard."]

VALID_RISKS = {"info", "low", "moderate", "high", "critical"}
RED_ID_RE = re.compile(r"red_[a-z0-9_]+\Z")
GREY_ID_RE = re.compile(r"grey_[a-z0-9_]+\Z")
BLUE_ID_RE = re.compile(r"cyber_[a-z0-9_]+\Z")
CONFIRM_RISKS = {SkillRisk.MODERATE, SkillRisk.HIGH, SkillRisk.CRITICAL}

FAILURES: list[str] = []


def check(name, fn):
    try:
        fn()
        print(f"  ok: {name}")
    except Exception:  # noqa: BLE001
        FAILURES.append(name)
        print(f"FAIL: {name}")
        traceback.print_exc(limit=5)


# ── Corpus property tests ────────────────────────────────────────


def _expected_id(team: str, path: Path) -> str:
    return f"{team}_" + path.stem.replace("-", "_")


def _check_corpus(team: str, module, playbook_dir: Path, extra_markers):
    prefix = f"{team}_"
    skills = module.RED_SKILLS if team == "red" else module.GREY_SKILLS
    files = sorted(playbook_dir.glob("*.md"))
    assert files, f"no playbooks in {playbook_dir}"
    assert len(skills) == len(files), (
        f"{team}: registered {len(skills)} != files {len(files)}"
    )
    ids = [s.id for s in skills]
    assert len(set(ids)) == len(ids), f"{team}: duplicate skill ids"
    id_re = RED_ID_RE if team == "red" else GREY_ID_RE
    for skill, path in zip(
        sorted(skills, key=lambda s: s.id), files, strict=True
    ):
        assert id_re.match(skill.id), f"{path.name}: bad id {skill.id!r}"
        assert skill.id == _expected_id(team, path), (
            f"{path.name}: id {skill.id!r} not filename-derived"
        )
        assert skill.category == "cybersecurity", (
            f"{skill.id}: category {skill.category!r}"
        )
        assert f"{team}-team" in skill.tags, (
            f"{skill.id}: tags missing {team}-team: {skill.tags}"
        )
        assert skill.name.strip(), f"{skill.id}: empty name"
        assert skill.description.strip(), f"{skill.id}: empty description"
        assert re.fullmatch(r"\d+\.\d+\.\d+", skill.version), (
            f"{skill.id}: bad version {skill.version!r}"
        )
        want_confirm = skill.risk_level in CONFIRM_RISKS
        assert skill.requires_confirmation == want_confirm, (
            f"{skill.id}: risk {skill.risk_level} requires_confirmation "
            f"must be {want_confirm}"
        )
        body = path.read_text(encoding="utf-8")
        assert body.startswith("---\n"), f"{path.name}: no frontmatter"
        for section in REQUIRED_SECTIONS + extra_markers:
            assert section in body, f"{path.name}: missing {section!r}"
        # Lazy handler: invocation returns the full playbook text.
        out = skill.handler({})
        assert isinstance(out, str) and len(out) >= 1000, (
            f"{skill.id}: handler returned {len(out)} chars"
        )
        assert skill.name in out, f"{skill.id}: handler lost the title"
        if team == "red":
            pair = red_skills.RED_BLUE_PAIRS[skill.id]
            assert BLUE_ID_RE.match(pair), (
                f"{skill.id}: malformed tests_blue {pair!r}"
            )


def test_red_corpus():
    _check_corpus("red", red_skills, RED_DIR, RED_EXTRA_MARKERS)


def test_grey_corpus():
    _check_corpus("grey", grey_skills, GREY_DIR, GREY_EXTRA_MARKERS)


# ── Red/blue pairing resolution ──────────────────────────────────


def test_red_tests_blue_resolve():
    """Every red tests_blue id must exist in the live cyber library."""
    from levi.skill import cyber_skills

    blue_ids = {s.id for s in cyber_skills.CYBER_SKILLS}
    assert blue_ids, "cyber library empty — cannot validate pairings"
    missing = [
        (red, blue)
        for red, blue in sorted(red_skills.RED_BLUE_PAIRS.items())
        if blue not in blue_ids
    ]
    assert not missing, (
        f"{len(missing)} red pairings missing from cyber library: "
        f"{missing[:5]}"
    )


# ── Loud rejection (invalid files must raise, never skip) ────────

_VALID_RED = """---
skill_id: {sid}
name: Test Skill
description: A test playbook.
risk: {risk}
permissions: []
requires_confirmation: {confirm}
tags: [red-team, test]
version: 1.0.0
team: red
tests_blue: cyber_test_blue_skill
---
# Test Skill

## Purpose
X
## When to use
X
## Prerequisites
X
## Procedure
X
## Expected outputs
X
## Pitfalls
X
## References
X
## Blue-team control under test
X
## Authorization guard.
X
"""

_VALID_GREY = """---
skill_id: {sid}
name: Test Skill
description: A test playbook.
risk: {risk}
permissions: []
requires_confirmation: {confirm}
tags: [grey-team, test]
version: 1.0.0
team: grey
---
# Test Skill

## Purpose
X
## When to use
X
## Prerequisites
X
## Procedure
X
## Expected outputs
X
## Pitfalls
X
## References
X
## Exercise role
X
## Exercise guard.
X
"""


def _write_bad(team: str, filename: str, body: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=f"bad-{team}-"))
    (tmp / filename).write_text(body, encoding="utf-8")
    return tmp


def _expect_value_error(name, team: str, filename: str, body: str):
    tmp = _write_bad(team, filename, body)
    loader = (
        red_skills.load_red_skills if team == "red" else grey_skills.load_grey_skills
    )
    try:
        loader(tmp)
    except ValueError:
        return
    raise AssertionError(f"{name}: invalid playbook did not raise ValueError")


def _good(team: str, **kw) -> str:
    tmpl = _VALID_RED if team == "red" else _VALID_GREY
    sid = f"{team}_good_skill"
    params = {"sid": sid, "risk": "moderate", "confirm": "true"}
    params.update(kw)
    return tmpl.format(**params)


def test_reject_missing_frontmatter():
    for team in ("red", "grey"):
        _expect_value_error(
            f"{team}/no-frontmatter", team, "good-skill.md", "# No frontmatter\n"
        )


def test_reject_missing_key():
    for team in ("red", "grey"):
        body = _good(team).replace("version: 1.0.0\n", "")
        _expect_value_error(f"{team}/missing-key", team, "good-skill.md", body)


def test_reject_unknown_key():
    for team in ("red", "grey"):
        body = _good(team).replace("team: " + team, "team: " + team + "\nbogus: 1")
        _expect_value_error(f"{team}/unknown-key", team, "good-skill.md", body)


def test_reject_id_filename_mismatch():
    for team in ("red", "grey"):
        body = _good(team).replace(f"{team}_good_skill", f"{team}_other_slug")
        _expect_value_error(
            f"{team}/id-mismatch", team, "good-skill.md", body
        )


def test_reject_bad_id_form():
    body = _good("red").replace("skill_id: red_good_skill", "skill_id: blue_good_skill")
    _expect_value_error("red/bad-id-form", "red", "good-skill.md", body)
    body = _good("grey").replace("skill_id: grey_good_skill", "skill_id: grey-BAD")
    _expect_value_error("grey/bad-id-form", "grey", "good-skill.md", body)


def test_reject_wrong_team():
    body = _good("red").replace("team: red", "team: grey")
    _expect_value_error("red/wrong-team", "red", "good-skill.md", body)
    body = _good("grey").replace("team: grey", "team: red")
    _expect_value_error("grey/wrong-team", "grey", "good-skill.md", body)


def test_reject_bad_risk():
    for team in ("red", "grey"):
        body = _good(team).replace("risk: moderate", "risk: spicy")
        _expect_value_error(f"{team}/bad-risk", team, "good-skill.md", body)


def test_reject_confirmation_mismatch():
    # moderate must confirm; low must not.
    for team in ("red", "grey"):
        body = _good(team).replace("requires_confirmation: true", "requires_confirmation: false")
        _expect_value_error(
            f"{team}/confirm-mismatch-moderate", team, "good-skill.md", body
        )
        body = _good(team, risk="low", confirm="true")
        _expect_value_error(
            f"{team}/confirm-mismatch-low", team, "good-skill.md", body
        )


def test_reject_bad_tests_blue():
    body = _good("red").replace(
        "tests_blue: cyber_test_blue_skill", "tests_blue: not_a_blue_id"
    )
    _expect_value_error("red/bad-tests-blue", "red", "good-skill.md", body)
    body = _good("red").replace("tests_blue: cyber_test_blue_skill\n", "")
    _expect_value_error("red/missing-tests-blue", "red", "good-skill.md", body)


def test_reject_missing_footer():
    body = _good("red").replace("## Authorization guard.", "## No guard here.")
    _expect_value_error("red/missing-footer", "red", "good-skill.md", body)
    body = _good("grey").replace("## Exercise guard.", "## No guard here.")
    _expect_value_error("grey/missing-footer", "grey", "good-skill.md", body)


def test_reject_duplicate_ids():
    """good-skill.md and good_skill.md derive the same id -> must raise."""
    for team in ("red", "grey"):
        tmp = Path(tempfile.mkdtemp(prefix=f"dup-{team}-"))
        body = _good(team)
        (tmp / "good-skill.md").write_text(body, encoding="utf-8")
        dup_body = body.replace("name: Test Skill", "name: Dup Skill")
        (tmp / "good_skill.md").write_text(dup_body, encoding="utf-8")
        loader = (
            red_skills.load_red_skills
            if team == "red"
            else grey_skills.load_grey_skills
        )
        try:
            loader(tmp)
        except ValueError as exc:
            assert "duplicate skill id" in str(exc), f"{team}: {exc}"
        else:
            raise AssertionError(f"{team}: duplicate ids did not raise")


def test_reject_missing_and_empty_dir():
    for loader, label in (
        (red_skills.load_red_skills, "red"),
        (grey_skills.load_grey_skills, "grey"),
    ):
        try:
            loader(Path("/nonexistent-dir-xyz"))
            raise AssertionError(f"{label}: missing dir did not raise")
        except ValueError:
            pass
        empty = Path(tempfile.mkdtemp(prefix=f"empty-{label}-"))
        try:
            loader(empty)
            raise AssertionError(f"{label}: empty dir did not raise")
        except ValueError:
            pass


# ── Registry coverage ────────────────────────────────────────────


def test_registry_covers_red_and_grey():
    reg = SkillRegistry()
    red_ids = {s.id for s in red_skills.RED_SKILLS}
    grey_ids = {s.id for s in grey_skills.GREY_SKILLS}
    for sid in red_ids | grey_ids:
        assert reg.get(sid) is not None, f"registry missing {sid}"
    red_known = {
        "red_kerberoasting",
        "red_pass_the_hash_test",
        "red_golden_ticket_persistence",
        "red_lsass_dump_test",
        "red_dns_c2_test",
    }
    grey_known = {
        "grey_range_reset_procedure",
        "grey_detection_scoring",
        "grey_snapshot_lifecycle_cleanup",
    }
    assert red_known <= red_ids, f"missing red: {red_known - red_ids}"
    assert grey_known <= grey_ids, f"missing grey: {grey_known - grey_ids}"
    # Spot-check: a MODERATE and a HIGH red skill are confirmation-gated.
    s = reg.get("red_kerberoasting")
    assert s.risk_level == SkillRisk.MODERATE and s.requires_confirmation
    s = reg.get("red_adcs_escalation")
    assert s.risk_level == SkillRisk.HIGH and s.requires_confirmation
    # Invocation through the registry returns the playbook text.
    out = reg.invoke("grey_range_reset_procedure", {})
    assert "Full Range Reset Procedure" in out


def main() -> int:
    print("red/grey skill pack tests")
    for name, fn in sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")]
    ):
        check(name, fn)
    print(f"\n{len(FAILURES)} failure(s): {FAILURES}" if FAILURES else "\nall green")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
