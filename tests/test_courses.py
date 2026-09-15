"""Tests for the awesome-courses curriculum knowledge base.

Covers: catalog shape (11 subjects / 212 courses), per-subject field guides,
coverage.json accounting for every cataloged course, the course_brief /
course_search agent tools, and the data-driven skill registration.
"""

from __future__ import annotations

import json
from pathlib import Path


COURSES = (
    Path(__file__).resolve().parent.parent / "core" / "levi" / "knowledge" / "courses"
)


def _catalog() -> dict:
    return json.loads((COURSES / "catalog.json").read_text(encoding="utf-8"))


def _coverage() -> list[dict]:
    return json.loads((COURSES / "coverage.json").read_text(encoding="utf-8"))


def test_catalog_has_11_subjects_and_212_courses():
    catalog = _catalog()
    subjects = catalog["subjects"]
    assert len(subjects) == 11, f"expected 11 subjects, got {len(subjects)}"
    total = sum(len(s["courses"]) for s in subjects)
    assert total == 212, f"expected 212 courses, got {total}"
    slugs = [s["slug"] for s in subjects]
    assert "systems" in slugs and "machine-learning" in slugs
    for s in subjects:
        for c in s["courses"]:
            assert c["title"] and c["primary"], f"course missing fields: {c}"


def test_briefs_exist_and_are_nontrivial():
    catalog = _catalog()
    for s in catalog["subjects"]:
        brief = COURSES / "briefs" / f"{s['slug']}.md"
        assert brief.is_file(), f"missing brief for {s['slug']}"
        text = brief.read_text(encoding="utf-8")
        # statistics has only 1 cataloged course, so its brief is honestly short
        assert len(text) > 1000, f"brief too short for {s['slug']}: {len(text)} chars"
        assert s["name"].split()[0] in text  # sanity: brief is about the subject


def test_coverage_accounts_for_every_course():
    catalog = _catalog()
    recs = _coverage()
    by_id = {r["id"]: r for r in recs}
    missing = []
    for s in catalog["subjects"]:
        for c in s["courses"]:
            # id scheme must match ingest.py's slug()
            import re
            import unicodedata

            t = unicodedata.normalize("NFKD", c["code"] + "-" + c["title"])
            t = t.encode("ascii", "ignore").decode()
            cid = (
                s["slug"] + "/" + re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80]
            )
            if cid not in by_id:
                missing.append(cid)
    assert not missing, (
        f"{len(missing)} courses missing from coverage.json: {missing[:5]}"
    )
    valid = {"ok", "dead", "skipped-video", "skipped-binary"}
    for r in recs:
        assert r["status"] in valid, f"bad status {r['status']} for {r['id']}"
        if r["status"] == "ok":
            assert r.get("file"), f"ok record without file: {r['id']}"


def test_course_tools_execute():
    from levi.agent.tools import build_default_registry, ExecContext

    reg = build_default_registry()
    ctx = ExecContext()
    brief = reg.execute("course_brief", {"subject": "systems"}, ctx)
    assert brief.ok, brief.error
    assert "systems" in brief.output.lower() or "Systems" in brief.output
    bad = reg.execute("course_brief", {"subject": "nope"}, ctx)
    assert not bad.ok and "unknown subject" in bad.error
    search = reg.execute("course_search", {"query": "operating systems"}, ctx)
    assert search.ok, search.error
    assert "operating" in search.output.lower()
    empty = reg.execute("course_search", {"query": ""}, ctx)
    assert not empty.ok


def test_course_skills_registered():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()  # constructor registers builtin + course packs
    ids = set(reg._skills)
    assert "course_systems" in ids
    assert "course_machine_learning" in ids
    assert len([i for i in ids if i.startswith("course_")]) == 11


# ---------------------------------------------------------------------------
# Catalog-load hardening (monkeypatched COURSES_DIR)
# ---------------------------------------------------------------------------


def _load_with(monkeypatch, tmp_path, catalog_content):
    import levi.skill.course_skills as cs

    courses_dir = tmp_path / "courses"
    courses_dir.mkdir()
    if catalog_content is not None:
        (courses_dir / "catalog.json").write_text(catalog_content)
    monkeypatch.setattr(cs, "COURSES_DIR", courses_dir)
    monkeypatch.setattr(cs, "BRIEFS_DIR", courses_dir / "briefs")
    return cs._load()


def test_load_missing_catalog_is_empty(monkeypatch, tmp_path):
    assert _load_with(monkeypatch, tmp_path, None) == []


def test_load_corrupt_catalog_degrades_loudly(monkeypatch, tmp_path, capsys):
    skills = _load_with(monkeypatch, tmp_path, "{not json")
    assert skills == []
    assert "corrupt catalog" in capsys.readouterr().err


def test_load_non_object_catalog_degrades(monkeypatch, tmp_path, capsys):
    skills = _load_with(monkeypatch, tmp_path, '["a list"]')
    assert skills == []
    assert "not an object" in capsys.readouterr().err


def test_load_skips_bad_subjects_keeps_good(monkeypatch, tmp_path):
    import json

    catalog = {
        "subjects": [
            {"slug": "systems", "name": "Systems", "courses": [{"t": 1}]},
            {"slug": "../evil", "name": "Evil", "courses": []},  # bad slug
            {"slug": "noname", "courses": []},  # missing name
            {"slug": "nocourses", "name": "No Courses"},  # missing courses
            "not-a-dict",
            {"slug": "machine-learning", "name": "ML", "courses": []},
        ]
    }
    skills = _load_with(monkeypatch, tmp_path, json.dumps(catalog))
    ids = {s.id for s in skills}
    assert ids == {"course_systems", "course_machine_learning"}


def test_brief_for_rejects_bad_slug():
    from levi.skill.course_skills import _brief_for

    assert "Invalid subject slug" in _brief_for("../etc/passwd")
    assert "Invalid subject slug" in _brief_for("")


def test_brief_for_missing_file_is_honest(monkeypatch, tmp_path):
    import levi.skill.course_skills as cs

    monkeypatch.setattr(cs, "BRIEFS_DIR", tmp_path)
    assert "No field guide" in cs._brief_for("systems")
