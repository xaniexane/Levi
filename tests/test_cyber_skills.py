"""LEVI cybersecurity skill pack: original playbooks.

Asserts the cyber skill surface: the curated batch-1 set (100 skills),
unique ids, every playbook file present and non-trivial (100-160 line
quality bar), every playbook loads through the registry handler, required
markdown sections present, risk levels within the SkillRisk enum, and
confirmation gates on live-system-touching skills. Later batches drop
additional playbooks into the same directory; data-driven discovery
registers them, and the orphan/missing-file tests keep both directions
consistent.

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

REQUIRED_SECTIONS = [
    "## Purpose",
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Key tools & commands",
    "## Expected outputs",
    "## Pitfalls",
    "## References",
]

# Spot-check: batch-1 skills that touch live systems / acquire evidence /
# submit externally. Each must be MODERATE with requires_confirmation=True.
# (The policy test below generalizes this to every MODERATE cyber skill.)
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

MIN_PLAYBOOK_LINES = 100  # quality bar: 100-160 lines; below is a stub
MAX_PLAYBOOK_LINES = 170  # batch-1 ceiling (small overflow tolerated)

NEGATIONS = (
    "do not", "don't", "does not", "never", "not include", "not contain",
    "without", "avoid", "prohibit", "refrain", "no ", "non-", "against",
)


def _cyber_skills():
    return [s for s in SkillRegistry().list() if s.category == "cybersecurity"]


def _slug_of(skill_id: str) -> str:
    return skill_id[len("cyber_"):].replace("_", "-")


def _playbook_path(skill_id: str) -> Path:
    return PLAYBOOK_DIR / f"{_slug_of(skill_id)}.md"


def _body(path: Path) -> str:
    """Playbook markdown with any YAML frontmatter block stripped."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4:].lstrip("\n")
    return text


_TESTS = []


def _test(fn):
    _TESTS.append(fn)
    return fn


@_test
def test_curated_batch1_count():
    assert len(cyber_skills.CURATED_CYBER_SKILLS) == 100, (
        f"expected 100 curated batch-1 skills, got {len(cyber_skills.CURATED_CYBER_SKILLS)}"
    )


@_test
def test_registered_covers_curated():
    registered = {s.id for s in _cyber_skills()}
    missing = [s.id for s in cyber_skills.CURATED_CYBER_SKILLS if s.id not in registered]
    assert not missing, f"curated skills not registered: {missing}"


@_test
def test_no_orphan_playbook_files():
    # Every .md in the playbook dir (including later batches) must be
    # registered. Evaluated against a fresh discovery so files that land
    # while a batch is still writing are judged consistently.
    known = {s.id for s in cyber_skills.CURATED_CYBER_SKILLS}
    known |= {s.id for s in cyber_skills._discover_extra_playbooks()}
    orphans = []
    for path in sorted(PLAYBOOK_DIR.glob("*.md")):
        sid = "cyber_" + path.stem.replace("-", "_")
        if sid not in known:
            orphans.append(path.name)
    assert not orphans, f"playbook files with no registered skill: {orphans}"


@_test
def test_ids_unique_and_schemed():
    skills = _cyber_skills()
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids)), "duplicate cyber skill ids"
    for s in skills:
        assert s.id.startswith("cyber_"), f"id {s.id!r} missing cyber_ prefix"
        assert re.fullmatch(r"cyber_[a-z0-9_]+", s.id), f"id {s.id!r} not slug-shaped"


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
def test_every_playbook_file_exists_and_nontrivial():
    # Batch-1 quality bar (100-160 lines) applies to the curated set.
    # Later batches use their own format; they just must be non-trivial.
    missing, stubs, overweight, thin = [], [], [], []
    curated_ids = {s.id for s in cyber_skills.CURATED_CYBER_SKILLS}
    for s in _cyber_skills():
        path = _playbook_path(s.id)
        if not path.is_file():
            missing.append(s.id)
            continue
        n = len(path.read_text(encoding="utf-8").splitlines())
        if s.id in curated_ids:
            if n < MIN_PLAYBOOK_LINES:
                stubs.append((s.id, n))
            if n > MAX_PLAYBOOK_LINES:
                overweight.append((s.id, n))
        elif n < 20:
            thin.append((s.id, n))
    assert not missing, f"missing playbooks: {missing}"
    assert not stubs, f"batch-1 stub playbooks (< {MIN_PLAYBOOK_LINES} lines): {stubs}"
    assert not overweight, f"batch-1 playbooks over {MAX_PLAYBOOK_LINES} lines: {overweight}"
    assert not thin, f"later-batch playbooks under 20 lines: {thin}"


@_test
def test_playbook_sections_present():
    # The 8-section contract + provenance footer is the batch-1 format.
    bad = {}
    curated_ids = {s.id for s in cyber_skills.CURATED_CYBER_SKILLS}
    for s in _cyber_skills():
        if s.id not in curated_ids:
            continue
        path = _playbook_path(s.id)
        if not path.is_file():
            continue
        text = _body(path)
        lacking = [h for h in REQUIRED_SECTIONS if h not in text]
        if not text.startswith("# "):
            lacking.append("# <Title>")
        if "Original work authored for LEVI" not in text:
            lacking.append("provenance footer")
        if lacking:
            bad[s.id] = lacking
    assert not bad, f"batch-1 playbooks missing sections: {bad}"


@_test
def test_procedure_has_numbered_steps():
    bad = []
    for s in _cyber_skills():
        path = _playbook_path(s.id)
        if not path.is_file():
            continue
        text = _body(path)
        proc = text.split("## Procedure", 1)[1].split("## ", 1)[0] if "## Procedure" in text else ""
        steps = re.findall(r"(?m)^\s*\d+\.\s+\S", proc)
        if len(steps) < 5:
            bad.append((s.id, len(steps)))
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
    bad = []
    for s in _cyber_skills():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", _slug_of(s.id)):
            bad.append(s.id)
    assert not bad, f"slugs incompatible with skill_load: {bad}"


@_test
def test_no_attack_howto_markers():
    # Defensive lens: flag offensive-tradecraft markers, but ignore lines
    # that mention them in a prohibition ("do not include exploit code").
    # ("weaponize" is deliberately excluded: it appears routinely in
    # defensive prose such as "before the domains are weaponized".)
    markers = ["exploit code", "payload generator", "step-by-step attack",
               "zero-day exploit"]
    bad = []
    for s in _cyber_skills():
        path = _playbook_path(s.id)
        if not path.is_file():
            continue
        hits = []
        for line in _body(path).lower().splitlines():
            for m in markers:
                if m in line and not any(n in line for n in NEGATIONS):
                    hits.append((m, line.strip()[:100]))
        if hits:
            bad.append((s.id, hits))
    assert not bad, f"offensive markers found: {bad}"


@_test
def test_discovery_parses_frontmatter_and_falls_back():
    # Data-driven registration: frontmatter overrides; missing frontmatter
    # derives name/description from the markdown with safe defaults.
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "zz-front.md").write_text(
        "---\nname: ZZ Front\ndescription: Frontmatter test.\nrisk: moderate\n"
        "permissions: [evidence.read]\nrequires_confirmation: true\n"
        "tags: [test]\nversion: 1.0.0\n---\n# ZZ Front\n\n## Purpose\n\nX.\n",
        encoding="utf-8",
    )
    (d / "zz-plain.md").write_text(
        "# Plain Skill\n\n## Purpose\n\nPlain purpose line.\n", encoding="utf-8")
    old = cyber_skills.PLAYBOOK_DIR
    cyber_skills.PLAYBOOK_DIR = d
    try:
        extra = {s.id: s for s in cyber_skills._discover_extra_playbooks()}
    finally:
        cyber_skills.PLAYBOOK_DIR = old
    fm = extra["cyber_zz_front"]
    assert fm.name == "ZZ Front"
    assert fm.risk_level == SkillRisk.MODERATE and fm.requires_confirmation
    assert fm.permissions == ["evidence.read"] and fm.tags == ["test"]
    plain = extra["cyber_zz_plain"]
    assert plain.name == "Plain Skill"
    assert plain.description == "Plain purpose line."
    assert plain.risk_level == SkillRisk.LOW and not plain.requires_confirmation


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
