"""LEVI utilities skill pack: data-driven registration tests.

``utility_skills.UTILITY_SKILLS`` is built by scanning
``core/levi/skill/playbooks/utilities/*.md`` and parsing each file's mandatory
frontmatter block. These tests assert:

- exactly 60 utility skills load;
- every .md file carries valid frontmatter (all required keys, valid risk,
  id scheme ``utility.<slug_with_underscores>`` matching the filename);
- every playbook body has the required sections;
- registered count == .md file count;
- safety invariants: unique ids, unique names, unique descriptions,
  risk within the SkillRisk enum, MODERATE skills confirmation-gated,
  nothing above MODERATE, category == "utilities".

Run:  python3 tests/test_utility_skills.py     (has a real __main__ runner)
      python3 -m pytest tests/test_utility_skills.py -q
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
from levi.skill import utility_skills  # noqa: E402

PLAYBOOK_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "utilities"

EXPECTED_COUNT = 60

# Required body sections (frontmatter stripped before checking).
REQUIRED_SECTIONS = [
    "## When to use",
    "## Steps",
    "## Honest limits",
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

VALID_RISKS = {"info", "low", "moderate", "high", "critical"}
ID_RE = re.compile(r"utility\.[a-z0-9_]+\Z")


def _md_files():
    return sorted(PLAYBOOK_DIR.glob("*.md"))


def _body(path: Path) -> str:
    """Playbook body with the frontmatter block stripped."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :]
    return text


def _utility_skills():
    return [s for s in SkillRegistry().list() if s.category == "utilities"]


_TESTS = []


def _test(fn):
    _TESTS.append(fn)
    return fn


@_test
def test_exactly_sixty_playbook_files():
    files = _md_files()
    assert len(files) == EXPECTED_COUNT, (
        f"expected {EXPECTED_COUNT} utility playbooks, found {len(files)}"
    )


@_test
def test_every_playbook_has_valid_frontmatter():
    bad = {}
    for path in _md_files():
        meta = utility_skills._parse_frontmatter(path)
        problems = []
        if meta is None:
            problems.append("no parseable frontmatter block")
        else:
            missing = [k for k in FRONTMATTER_KEYS if k not in meta]
            if missing:
                problems.append(f"missing keys: {missing}")
            sid = str(meta.get("skill_id", ""))
            expected = "utility." + path.stem.replace("-", "_")
            if not ID_RE.match(sid):
                problems.append(
                    f"skill_id {sid!r} violates utility_<slug_with_underscores>"
                )
            elif sid != expected:
                problems.append(f"skill_id {sid!r} != filename-derived {expected!r}")
            if str(meta.get("risk", "")).lower() not in VALID_RISKS:
                problems.append(f"invalid risk: {meta.get('risk')!r}")
            if not isinstance(meta.get("permissions"), list):
                problems.append("permissions is not a list")
            if not isinstance(meta.get("requires_confirmation"), bool):
                problems.append("requires_confirmation is not a bool")
            if not isinstance(meta.get("tags"), list) or not meta.get("tags"):
                problems.append("tags is not a non-empty list")
            if not str(meta.get("name", "")).strip():
                problems.append("empty name")
            if not str(meta.get("description", "")).strip():
                problems.append("empty description")
        if problems:
            bad[path.name] = problems
    assert not bad, f"playbooks with invalid frontmatter: {bad}"


@_test
def test_registered_count_matches_file_count_and_expected():
    skills = utility_skills._load_utility_skills()
    files = _md_files()
    assert len(skills) == len(files) == EXPECTED_COUNT, (
        f"registered {len(skills)} skills, {len(files)} files, "
        f"expected {EXPECTED_COUNT}"
    )
    via_registry = _utility_skills()
    assert len(via_registry) == EXPECTED_COUNT, (
        f"registry lists {len(via_registry)} utilities, expected {EXPECTED_COUNT}"
    )


@_test
def test_ids_unique_and_schemed():
    skills = _utility_skills()
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids)), "duplicate utility skill ids"
    for s in skills:
        assert ID_RE.match(s.id), f"id {s.id!r} violates utility_<slug_with_underscores>"


@_test
def test_no_duplicate_names_or_descriptions():
    skills = _utility_skills()
    names = [s.name for s in skills]
    descriptions = [s.description for s in skills]
    dup_names = sorted({n for n in names if names.count(n) > 1})
    dup_descs = sorted({d for d in descriptions if descriptions.count(d) > 1})
    assert not dup_names, f"duplicate skill names: {dup_names}"
    assert not dup_descs, f"duplicate skill descriptions: {dup_descs}"


@_test
def test_category_is_utilities():
    for s in _utility_skills():
        assert s.category == "utilities", f"{s.id}: category {s.category!r}"


@_test
def test_versions():
    for s in _utility_skills():
        assert s.version == "1.0.0", f"{s.id}: version {s.version!r}"


@_test
def test_risk_policy():
    valid = {r.value for r in SkillRisk}
    for s in _utility_skills():
        assert int(s.risk_level) in valid, f"{s.id}: risk {s.risk_level!r} outside enum"
        assert s.risk_level <= SkillRisk.MODERATE, (
            f"{s.id}: risk {s.risk_level!r} above MODERATE"
        )
        if s.risk_level == SkillRisk.MODERATE:
            assert s.requires_confirmation, (
                f"{s.id}: MODERATE without requires_confirmation"
            )
        else:
            assert not s.requires_confirmation, (
                f"{s.id}: {s.risk_level!r} should not require confirmation"
            )


@_test
def test_required_body_sections_present():
    bad = {}
    for path in _md_files():
        body = _body(path)
        lacking = [h for h in REQUIRED_SECTIONS if h not in body]
        if lacking:
            bad[path.name] = lacking
    assert not bad, f"playbooks missing required sections: {bad}"


@_test
def test_procedure_has_numbered_steps():
    bad = []
    for path in _md_files():
        body = _body(path)
        proc = (
            body.split("## Steps", 1)[1].split("## ", 1)[0]
            if "## Steps" in body
            else ""
        )
        steps = re.findall(r"(?m)^\s*\d+\.\s+\S", proc)
        if len(steps) < 4:
            bad.append((path.name, len(steps)))
    assert not bad, f"playbooks with < 4 numbered steps: {bad}"


@_test
def test_every_playbook_loads_via_registry_handler():
    reg = SkillRegistry()
    failures = []
    for s in _utility_skills():
        try:
            out = reg.invoke(s.id, {})
        except Exception as exc:  # noqa: BLE001
            failures.append((s.id, f"invoke raised: {exc}"))
            continue
        if not isinstance(out, str) or len(out) < 500:
            failures.append(
                (
                    s.id,
                    f"handler returned {type(out).__name__} len={len(out) if isinstance(out, str) else '?'}",
                )
            )
        elif s.name not in out:
            failures.append((s.id, "playbook title not in handler output"))
    assert not failures, f"handler load failures: {failures}"


@_test
def test_filenames_match_skill_load_convention():
    bad = [
        p.name for p in _md_files() if not re.fullmatch(r"[A-Za-z0-9_-]+\.md", p.name)
    ]
    assert not bad, f"filenames incompatible with skill_load: {bad}"


def main() -> int:
    failures = 0
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        except Exception:
            failures += 1
            print(f"ERROR {name}:")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
