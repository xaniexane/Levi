"""Tests for the SQLite skill library (core/levi/skill/skilldb.py).

Fast unit tests run on tmp databases and synthetic zips. The full 258k-row
production seed is verified separately as a one-off run (counts, timing and
DB size are reported in the worker's final report, not asserted here).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from levi.skill import skilldb
from levi.skill.registry import SkillRegistry, SkillRisk

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_minimal(path: Path) -> None:
    skilldb.init_db(path)
    with skilldb.connect(path) as con:
        skilldb.upsert_skill(
            con,
            {
                "id": "s.alpha",
                "name": "Alpha Skill",
                "description": "does alpha things well",
                "category": "test",
                "status": "real",
                "instructions": "run the alpha procedure",
                "source": "test",
            },
        )
        skilldb.upsert_skill(
            con,
            {
                "id": "s.beta",
                "name": "Beta Skill",
                "description": "does beta things well",
                "category": "test",
                "status": "candidate",
                "instructions": "run the beta procedure",
                "source": "omega-bulk",
            },
        )


# ── 1. the revert held: registry is real-skills-only + one query skill ─────


def test_registry_has_no_stubs_and_one_query_skill():
    # Lazy import like registry.py: cyber_skills imports Skill/SkillRisk
    # from the registry module, so import it only after the registry.
    from levi.skill.cyber_skills import CYBER_SKILLS

    reg = SkillRegistry()
    ids = [s.id for s in reg.list()]
    assert not any(i.startswith("omega-bulk.") for i in ids)
    # Composition (batch-3, 2026-09-25): the cyber playbook pack —
    # 100,823 skills, derived from the same CYBER_SKILLS the registry
    # registers, so a future batch-4 won't rot this — plus the pre-cyber
    # base (real skills + the skilldb query skill + the 3 DDD daily-daemon
    # runner skills; 418 at batch-3 landing, grows as siblings build).
    # Derived/floored, never hardcoded: the tripwire's job is to catch a
    # shrunken base or an incompletely registered cyber pack.
    cyber_ids = {s.id for s in CYBER_SKILLS}
    assert cyber_ids <= set(ids), (
        f"cyber pack incomplete: {len(cyber_ids - set(ids))} ids missing"
    )
    n_base = len(ids) - len(cyber_ids)
    assert n_base >= 418, f"base skill set shrank unexpectedly: {n_base}"
    q = reg.get("skilldb.search")
    assert q is not None
    assert q.risk_level == SkillRisk.INFO
    assert q.permissions == []
    assert not q.requires_confirmation


# ── 2. real-skill seeding mirrors the registry ─────────────────────────────


def test_seed_real_skills_matches_registry(tmp_path):
    p = tmp_path / "t.db"
    skilldb.init_db(p)
    n = skilldb.seed_real_skills(p)
    reg = SkillRegistry()
    # Seeding mirrors the registry exactly; the total is derived from the
    # registry itself (see test_registry_has_no_stubs_and_one_query_skill
    # for the composition), never hardcoded.
    assert n == len(reg.list())
    rows = skilldb.list_by_status("real", path=p)
    assert len(rows) == n
    got = skilldb.get("status", path=p)
    assert got is not None and got["status"] == "real"
    assert got["source"] == "levi-registry"
    assert skilldb.list_by_status("candidate", path=p) == []


# ── 3. dedupe rule on synthetic data ───────────────────────────────────────


def _synth_entries(n_clones: int, n_unique: int):
    entries = [
        {
            "name": f"clone-{i:02d}",
            "description": "shared desc",
            "instructions": "SHARED INSTRUCTIONS BLOCK",
            "path": "bulk:clone",
        }
        for i in range(n_clones)
    ]
    entries += [
        {
            "name": f"uniq-{i}",
            "description": f"unique desc {i}",
            "instructions": f"unique instructions {i}",
            "path": "bulk:uniq",
        }
        for i in range(n_unique)
    ]
    return entries


def test_select_candidates_dedupe_synthetic():
    rows = skilldb._select_candidates(
        _synth_entries(30, 5),
        expected_clone_count=30,
        expected_reps=3,
        check_prefix=False,
    )
    assert len(rows) == 5 + 3
    reps = [r for r in rows if r["family"].startswith("clone-block-")]
    assert len(reps) == 3
    # stride-sampled over name-sorted clones: clone-00, clone-10, clone-20
    assert sorted(r["name"] for r in reps) == ["clone-00", "clone-10", "clone-20"]
    assert all("30-entry" in r["notes"] for r in reps)
    assert all(r["status"] == "candidate" and r["source"] == "omega-bulk" for r in rows)


def test_select_candidates_rejects_changed_archive():
    with pytest.raises(AssertionError):
        skilldb._select_candidates(
            _synth_entries(31, 5),
            expected_clone_count=30,
            expected_reps=3,
            check_prefix=False,
        )


# ── 4. end-to-end omega seed from a synthetic zip ──────────────────────────


def _write_synth_zip(zip_path: Path, n_clones: int, n_unique: int) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "omega/skills_bulk.json",
            json.dumps(_synth_entries(n_clones, n_unique)),
        )


def test_seed_omega_candidates_synthetic_zip(tmp_path):
    zp = tmp_path / "mini.zip"
    _write_synth_zip(zp, 20, 6)
    prio_jsonl = tmp_path / "prio.jsonl"
    # clone reps for 20 clones / 4 reps, stride 5, name-sorted: -00, -05, -10, -15
    prio_jsonl.write_text(
        '{"id": "omega-bulk.clone-05"}\n{"id": "omega-bulk.uniq-2"}\n'
    )
    p = tmp_path / "t.db"
    skilldb.init_db(p)
    rep = skilldb.seed_omega_candidates(
        p,
        zip_path=zp,
        priority_jsonl=prio_jsonl,
        expected_clone_count=20,
        expected_reps=4,
        check_prefix=False,
    )
    assert rep["archive_entries"] == 26
    assert rep["candidate_rows"] == 6 + 4
    assert rep["priority_matched"] == 2
    assert rep["priority_missing"] == []
    got = skilldb.get("omega-bulk.clone-05", path=p)
    assert got["priority"] == 1 and got["status"] == "candidate"
    assert skilldb.get("omega-bulk.uniq-0", path=p)["priority"] == 0
    st = skilldb.stats(path=p)
    assert st["by_status"] == {"candidate": 10}
    assert st["priority_candidates"] == 2


# ── 5. promote workflow ────────────────────────────────────────────────────


def test_promote_workflow(tmp_path):
    p = tmp_path / "t.db"
    _seed_minimal(p)
    r = skilldb.promote("s.beta", "refining", note="triage pass", path=p)
    assert r["status"] == "refining"
    assert "candidate->refining" in r["notes"] and "triage pass" in r["notes"]
    r = skilldb.promote("s.beta", "real", path=p)
    assert r["status"] == "real"
    with pytest.raises(ValueError):
        skilldb.promote("s.beta", "candidate", path=p)  # no downgrade
    r = skilldb.promote("s.beta", "candidate", path=p, force=True)
    assert r["status"] == "candidate"
    with pytest.raises(KeyError):
        skilldb.promote("nope", "real", path=p)
    with pytest.raises(ValueError):
        skilldb.promote("s.alpha", "bogus", path=p)


# ── 6. search + stats ──────────────────────────────────────────────────────


def test_search_fts_and_stats(tmp_path):
    p = tmp_path / "t.db"
    _seed_minimal(p)
    hits = skilldb.search("alpha procedure", path=p)
    assert [h["id"] for h in hits] == ["s.alpha"]
    hits = skilldb.search("beta", path=p, status="candidate")
    assert [h["id"] for h in hits] == ["s.beta"]
    assert skilldb.search("beta", path=p, status="real") == []
    assert skilldb.search("   ", path=p) == []
    st = skilldb.stats(path=p)
    assert st["total"] == 2
    assert st["by_status"] == {"real": 1, "candidate": 1}
    assert st["by_source"] == {"test": 1, "omega-bulk": 1}
    cats = skilldb.list_by_category("test", path=p)
    assert len(cats) == 2


# ── 7. the live query skill ────────────────────────────────────────────────


def test_skilldb_search_handler_seeded(tmp_path, monkeypatch):
    p = tmp_path / "t.db"
    _seed_minimal(p)
    monkeypatch.setenv("LEVI_SKILLDB_PATH", str(p))
    reg = SkillRegistry()
    out = reg.invoke("skilldb.search", {"query": "alpha procedure"})
    assert "s.alpha" in out and "[real]" in out
    out = reg.invoke("skilldb.search", {"query": "nothinglike this"})
    assert "No skill-library hits" in out
    out = reg.invoke("skilldb.search", {})
    assert "Provide query text" in out


def test_skilldb_search_handler_unseeded(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SKILLDB_PATH", str(tmp_path / "missing.db"))
    reg = SkillRegistry()
    out = reg.invoke("skilldb.search", {"query": "alpha"})
    assert "not seeded yet" in out


# ── 8. fresh-process open ──────────────────────────────────────────────────


def test_fresh_process_reopen(tmp_path):
    p = tmp_path / "t.db"
    _seed_minimal(p)
    script = (
        "import sys; sys.path.insert(0, 'core');"
        "from levi.skill import skilldb;"
        f"print(skilldb.stats({str(p)!r})['total'])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "LEVI_SKILLDB_PATH": str(p)},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "2"
