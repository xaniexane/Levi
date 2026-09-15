"""LEVI cybersecurity skill pack: 100 original playbooks.

Asserts the full cyber skill surface: exactly 100 registered skills,
unique ids, every playbook file present and non-trivial, every playbook
loads through the registry handler, required markdown sections present,
risk levels within the SkillRisk enum, and confirmation gates on
live-system-touching skills.

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

# Skills that touch live systems / acquire evidence / submit externally.
# Each must be MODERATE with requires_confirmation=True.
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

MIN_PLAYBOOK_LINES = 60  # below this a playbook counts as a stub


def _cyber_skills():
    return [s for s in SkillRegistry().list() if s.category == "cybersecurity"]


_TESTS = []


def _test(fn):
    _TESTS.append(fn)
    return fn


@_test
def test_exactly_100_cyber_skills():
    skills = _cyber_skills()
    assert len(skills) == 100, f"expected 100 cyber skills, got {len(skills)}"


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


@_test
def test_every_playbook_file_exists_and_nontrivial():
    missing, stubs = [], []
    for s in _cyber_skills():
        slug = s.id[len("cyber_"):].replace("_", "-")
        path = PLAYBOOK_DIR / f"{slug}.md"
        if not path.is_file():
            missing.append(s.id)
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) < MIN_PLAYBOOK_LINES:
            stubs.append((s.id, len(lines)))
    assert not missing, f"missing playbooks: {missing}"
    assert not stubs, f"stub playbooks (< {MIN_PLAYBOOK_LINES} lines): {stubs}"


@_test
def test_playbook_sections_present():
    bad = {}
    for s in _cyber_skills():
        slug = s.id[len("cyber_"):].replace("_", "-")
        path = PLAYBOOK_DIR / f"{slug}.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lacking = [h for h in REQUIRED_SECTIONS if h not in text]
        if not text.startswith("# "):
            lacking.append("# <Title>")
        if "Original work authored for LEVI" not in text:
            lacking.append("provenance footer")
        if lacking:
            bad[s.id] = lacking
    assert not bad, f"playbooks missing sections: {bad}"


@_test
def test_procedure_has_numbered_steps():
    bad = []
    for s in _cyber_skills():
        slug = s.id[len("cyber_"):].replace("_", "-")
        path = PLAYBOOK_DIR / f"{slug}.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
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
        slug = s.id[len("cyber_"):].replace("_", "-")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
            bad.append(s.id)
    assert not bad, f"slugs incompatible with skill_load: {bad}"


@_test
def test_no_attack_howto_markers():
    # Defensive lens: playbooks must not contain offensive tradecraft markers.
    markers = ["exploit code", "payload generator", "step-by-step attack"]
    bad = []
    for s in _cyber_skills():
        slug = s.id[len("cyber_"):].replace("_", "-")
        path = PLAYBOOK_DIR / f"{slug}.md"
        if not path.is_file():
            continue
        low = path.read_text(encoding="utf-8").lower()
        hits = [m for m in markers if m in low]
        if hits:
            bad.append((s.id, hits))
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
