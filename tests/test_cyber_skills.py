"""LEVI cybersecurity skill pack: data-driven registration tests.

``cyber_skills.CYBER_SKILLS`` is built by scanning
``core/levi/skill/playbooks/cyber/*.md`` and parsing each file's mandatory
frontmatter block. These tests assert:

- every .md file carries valid frontmatter (all required keys, valid risk,
  id scheme ``cyber_<slug_with_underscores>`` matching the filename);
- every playbook body has the required sections;
- registered count == .md file count (not a fixed number: later batches
  land in the same directory);
- all 100 batch-1 slugs from tests/fixtures/cyber_batch1_slugs.txt are
  registered, and all 718 batch-2 slugs from
  tests/fixtures/cyber_batch2_slugs.txt are registered (818 total);
- safety invariants: unique ids, risk within the SkillRisk enum,
  MODERATE skills confirmation-gated, defensive lens (no offensive
  tradecraft markers).

Run:  python3 tests/test_cyber_skills.py     (has a real __main__ runner)
      python3 -m pytest tests/test_cyber_skills.py -q
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
from levi.skill import cyber_skills  # noqa: E402

PLAYBOOK_DIR = ROOT / "core" / "levi" / "skill" / "playbooks" / "cyber"
# Batch slug lists live in the repo (tests/fixtures) so the suite is
# hermetic — it must not depend on files outside the checkout.
BATCH1_SLUGS = ROOT / "tests" / "fixtures" / "cyber_batch1_slugs.txt"
BATCH2_SLUGS = ROOT / "tests" / "fixtures" / "cyber_batch2_slugs.txt"

# Required body sections (frontmatter stripped before checking).
REQUIRED_SECTIONS = [
    "## Purpose",
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Expected outputs",
    "## Pitfalls",
    "## References",
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
ID_RE = re.compile(r"cyber_[a-z0-9_]+\Z")

# Spot-check: batch-1 skills that touch live systems / acquire evidence /
# submit externally. Each must be MODERATE with requires_confirmation=True.
GATED_IDS = {
    "cyber_acquiring_disk_image_with_dd_and_dcfldd",
    "cyber_auditing_aws_s3_bucket_permissions",
    "cyber_auditing_azure_active_directory_configuration",
    "cyber_auditing_cloud_with_cis_benchmarks",
    "cyber_auditing_entra_id_with_aadinternals",
    "cyber_auditing_gcp_iam_permissions",
    "cyber_auditing_kubernetes_cluster_rbac",
    "cyber_auditing_kubernetes_rbac_privilege_escalation",
    "cyber_auditing_uefi_firmware_with_chipsec",
    "cyber_benchmarking_kubernetes_with_kube_bench",
    "cyber_building_automated_malware_submission_pipeline",
}

MIN_BATCH1_LINES = 100  # batch-1 quality bar (100-160 lines)

NEGATIONS = (
    "do not", "don't", "does not", "never", "not include", "not contain",
    "without", "avoid", "prohibit", "refrain", "no ", "non-", "against",
)


def _md_files():
    return sorted(PLAYBOOK_DIR.glob("*.md"))


def _batch_ids(path):
    return {
        "cyber_" + slug.replace("-", "_")
        for slug in Path(path).read_text(encoding="utf-8").split()
        if slug.strip()
    }


def _batch1_ids():
    return _batch_ids(BATCH1_SLUGS)


def _cyber_skills():
    return [s for s in SkillRegistry().list() if s.category == "cybersecurity"]


_TESTS = []


def _test(fn):
    _TESTS.append(fn)
    return fn


@_test
def test_every_playbook_has_valid_frontmatter():
    bad = {}
    for path in _md_files():
        meta = cyber_skills._parse_frontmatter(path)
        problems = []
        if meta is None:
            problems.append("no parseable frontmatter block")
        else:
            missing = [k for k in FRONTMATTER_KEYS if k not in meta]
            if missing:
                problems.append(f"missing keys: {missing}")
            sid = str(meta.get("skill_id", ""))
            expected = "cyber_" + path.stem.replace("-", "_")
            if not ID_RE.match(sid):
                problems.append(f"skill_id {sid!r} violates cyber_<slug_with_underscores>")
            elif sid != expected:
                problems.append(f"skill_id {sid!r} != filename-derived {expected!r}")
            if str(meta.get("risk", "")).lower() not in VALID_RISKS:
                problems.append(f"invalid risk: {meta.get('risk')!r}")
            if not isinstance(meta.get("permissions"), list):
                problems.append("permissions is not a list")
            if not isinstance(meta.get("requires_confirmation"), bool):
                problems.append("requires_confirmation is not a bool")
            if not isinstance(meta.get("tags"), list):
                problems.append("tags is not a list")
            if not str(meta.get("name", "")).strip():
                problems.append("empty name")
            if not str(meta.get("description", "")).strip():
                problems.append("empty description")
        if problems:
            bad[path.name] = problems
    assert not bad, f"playbooks with invalid frontmatter: {bad}"


@_test
def test_required_body_sections_present():
    bad = {}
    for path in _md_files():
        body = cyber_skills._playbook_body(path)
        lacking = [h for h in REQUIRED_SECTIONS if h not in body]
        if lacking:
            bad[path.name] = lacking
    assert not bad, f"playbooks missing required sections: {bad}"


@_test
def test_registered_count_matches_file_count():
    # Fresh load vs fresh glob so files landing mid-batch are judged together.
    skills = cyber_skills._load_cyber_skills()
    files = _md_files()
    assert len(skills) == len(files), (
        f"registered {len(skills)} skills but found {len(files)} playbook files"
    )


@_test
def test_batch1_slugs_all_registered():
    want = _batch1_ids()
    assert len(want) == 100, f"batch1 list has {len(want)} slugs, expected 100"
    registered = {s.id for s in _cyber_skills()}
    missing = sorted(want - registered)
    assert not missing, f"batch-1 skills not registered: {missing}"


@_test
def test_batch2_slugs_all_registered():
    want = _batch_ids(BATCH2_SLUGS)
    assert len(want) == 718, f"batch2 list has {len(want)} slugs, expected 718"
    registered = {s.id for s in _cyber_skills()}
    missing = sorted(want - registered)
    assert not missing, f"batch-2 skills not registered: {missing}"
    # Full library: every slug from both batches registered, no extras lost.
    assert len(registered) == 818, f"expected 818 cyber skills, got {len(registered)}"


@_test
def test_ids_unique_and_schemed():
    skills = _cyber_skills()
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids)), "duplicate cyber skill ids"
    for s in skills:
        assert ID_RE.match(s.id), f"id {s.id!r} violates cyber_<slug_with_underscores>"


@_test
def test_versions():
    for s in _cyber_skills():
        assert s.version == "1.0.0", f"{s.id}: version {s.version!r}"


@_test
def test_risk_levels_within_enum():
    valid = {r.value for r in SkillRisk}
    for s in _cyber_skills():
        assert int(s.risk_level) in valid, f"{s.id}: risk {s.risk_level!r} outside enum"


@_test
def test_gated_skills_require_confirmation():
    by_id = {s.id: s for s in _cyber_skills()}
    for gid in GATED_IDS:
        assert gid in by_id, f"gated skill {gid} not registered"
        s = by_id[gid]
        assert s.risk_level == SkillRisk.MODERATE, f"{gid}: risk is not MODERATE"
        assert s.requires_confirmation, f"{gid}: requires_confirmation not set"
    # Policy generalization: every MODERATE cyber skill must be gated.
    ungated = [s.id for s in _cyber_skills()
               if s.risk_level == SkillRisk.MODERATE and not s.requires_confirmation]
    assert not ungated, f"MODERATE skills without confirmation gate: {ungated}"


@_test
def test_batch1_playbooks_meet_line_bar_and_footer():
    batch1 = _batch1_ids()
    thin, no_footer = [], []
    for s in _cyber_skills():
        if s.id not in batch1:
            continue
        path = PLAYBOOK_DIR / f"{s.id[len('cyber_'):].replace('_', '-')}.md"
        text = path.read_text(encoding="utf-8")
        if len(text.splitlines()) < MIN_BATCH1_LINES:
            thin.append(s.id)
        if "Original work authored for LEVI" not in text:
            no_footer.append(s.id)
    assert not thin, f"batch-1 playbooks under {MIN_BATCH1_LINES} lines: {thin}"
    assert not no_footer, f"batch-1 playbooks missing provenance footer: {no_footer}"


@_test
def test_procedure_has_numbered_steps():
    bad = []
    for path in _md_files():
        body = cyber_skills._playbook_body(path)
        proc = body.split("## Procedure", 1)[1].split("## ", 1)[0] if "## Procedure" in body else ""
        steps = re.findall(r"(?m)^\s*\d+\.\s+\S", proc)
        if len(steps) < 5:
            bad.append((path.name, len(steps)))
    assert not bad, f"playbooks with < 5 numbered procedure steps: {bad}"


@_test
def test_every_playbook_loads_via_registry_handler():
    reg = SkillRegistry()
    failures = []
    for s in _cyber_skills():
        try:
            out = reg.invoke(s.id, {})
        except Exception as exc:  # noqa: BLE001
            failures.append((s.id, f"invoke raised: {exc}"))
            continue
        if not isinstance(out, str) or len(out) < 1000:
            failures.append((s.id, f"handler returned {type(out).__name__} len={len(out) if isinstance(out, str) else '?'}"))
        elif s.name not in out:
            failures.append((s.id, "playbook title not in handler output"))
    assert not failures, f"handler load failures: {failures}"


@_test
def test_filenames_match_skill_load_convention():
    # agent skill_load sanitizes names to [A-Za-z0-9_-] + ".md"
    bad = [p.name for p in _md_files()
           if not re.fullmatch(r"[A-Za-z0-9_-]+\.md", p.name)]
    assert not bad, f"filenames incompatible with skill_load: {bad}"


@_test
def test_no_attack_howto_markers():
    # Defensive lens: flag offensive-tradecraft markers, but ignore lines
    # that mention them in a prohibition ("do not include exploit code").
    # ("weaponize" is deliberately excluded: it appears routinely in
    # defensive prose such as "before the domains are weaponized".)
    markers = ["exploit code", "payload generator", "step-by-step attack",
               "zero-day exploit"]
    bad = []
    for path in _md_files():
        hits = []
        for line in cyber_skills._playbook_body(path).lower().splitlines():
            for m in markers:
                if m in line and not any(n in line for n in NEGATIONS):
                    hits.append((m, line.strip()[:100]))
        if hits:
            bad.append((path.name, hits))
    assert not bad, f"offensive markers found: {bad}"


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
