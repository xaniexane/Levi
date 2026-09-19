"""Tests for INCOME BATCH C (audit-services, slots 41-52).

Hermetic: fixtures live under tmp_path; the generators' run() functions
are invoked directly with ctx["levi_home"] = tmp dir. Each generator gets:
  - dry-run: computes but writes NO report files under the work dir
  - real run: writes report.md + summary.json, findings reflect the fixture
Also: registry presence/kind/slot/price checks.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from levi.income import engine
from levi.income.engine import REGISTRY, WorkReport

import levi.income.gen_audits as gen_audits  # noqa: F401  (self-registers)


BATCH_C = [
    ("seo-basics-scanner", 41, 3.0),
    ("accessibility-spotter", 42, 3.0),
    ("broken-link-hunter", 43, 3.5),
    ("readme-health-auditor", 44, 2.0),
    ("dependency-hygiene-reporter", 45, 2.5),
    ("backup-readiness-auditor", 46, 3.0),
    ("secrets-surface-reporter", 47, 4.0),
    ("doc-coverage-reporter", 48, 3.0),
    ("todo-debt-collector", 49, 2.0),
    ("git-hygiene-reporter", 50, 3.5),
    ("license-header-auditor", 51, 2.5),
    ("perf-checklist-generator", 52, 3.0),
]


def _ctx(home: Path, target=None, dry: bool = False):
    return {"levi_home": home, "dry_run": dry,
            "params": {"target": str(target)} if target else {}}


def _workdir(home: Path, gid: str) -> Path:
    return home / ".levi" / "income" / "work" / gid


# --------------------------------------------------------------------------
# Registry-level tests
# --------------------------------------------------------------------------
def test_batch_c_registered_in_slots():
    assert REGISTRY.count() >= 12
    for gid, slot, price in BATCH_C:
        g = REGISTRY.get(gid)
        assert REGISTRY.slot_of(gid) == slot
        assert g.kind == "audit-service"
        assert g.entry_price_usd == price
        assert 1.0 <= g.entry_price_usd <= 5.0
        assert g.version == "1.0.0"
        assert callable(g.run)


def test_batch_c_slots_unique_and_bounded():
    slots = [REGISTRY.slot_of(gid) for gid, _, _ in BATCH_C]
    assert sorted(slots) == list(range(41, 53))
    assert len(set(slots)) == 12


def test_discover_registers_batch_c():
    found = engine.discover()
    assert found >= 1
    # all batch-C generators still resolve at their assigned slots
    for gid, slot, _ in BATCH_C:
        assert REGISTRY.slot_of(gid) == slot


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture()
def site(tmp_path: Path) -> Path:
    """A small static site with deliberate flaws."""
    d = tmp_path / "site"
    d.mkdir()
    (d / "index.html").write_text("""<!DOCTYPE html>
<html><head><title>Home</title></head>
<body>
<h1>Welcome</h1>
<h3>Skipped h2</h3>
<img src="big.png">
<a href="missing.html">dead</a>
<a href="#nope">dangling</a>
<form><input type="text" name="q"></form>
<button></button>
</body></html>""")
    (d / "about.html").write_text("""<!DOCTYPE html>
<html lang="en"><head><title>About</title>
<meta name="description" content="About us">
<meta name="viewport" content="width=device-width">
</head><body><h1>About</h1><h2>Team</h2>
<img src="ok.png" alt="team photo">
<a href="index.html">home</a>
<script src="app.js"></script>
</body></html>""")
    (d / "big.png").write_bytes(b"\x89PNG" + b"x" * (300 * 1024))
    (d / "ok.png").write_bytes(b"\x89PNG" + b"x" * 100)
    (d / "app.js").write_text("console.log('hi');")
    return d


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A small Python project with deliberate flaws."""
    d = tmp_path / "proj"
    d.mkdir()
    (d / "README.md").write_text(
        "# Demo\n\nA demo project.\n\n```python\nprint('hi')\n```\n")
    (d / "requirements.txt").write_text(
        "requests==2.31.0\nflask>=3.0\ndjango\n# comment\n-e .\n")
    (d / "mod.py").write_text(
        '"""Module docstring."""\n\n\n'
        'def documented():\n    """Does a thing."""\n    return 1\n\n\n'
        'def undocumented():\n    return 2\n\n\n'
        'class Widget:\n    def method(self):\n        return 3\n')
    (d / "secrets.env").write_text(
        'API_KEY=sk-live-abcdef1234567890\nDEBUG=true\n')
    (d / "notes.py").write_text(
        "# TODO: rewrite this\nx = 1  # FIXME: magic number\n"
        "# HACK: works for now\n")
    (d / "plain.py").write_text("x = 1\n")
    return d


@pytest.fixture()
def gitrepo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=d,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    (d / "f.txt").write_text("one")
    subprocess.run(["git", "add", "."], cwd=d, check=True)
    subprocess.run(["git", "commit", "-qm", "Add initial file"], cwd=d,
                   check=True)
    subprocess.run(["git", "checkout", "-qb", "stale-branch"], cwd=d,
                   check=True)
    return d


# --------------------------------------------------------------------------
# Per-generator run tests
# --------------------------------------------------------------------------
def _run(gid: str, home: Path, target, dry: bool = False) -> WorkReport:
    return REGISTRY.get(gid).run(_ctx(home, target, dry=dry))


def _artifacts(home: Path, gid: str):
    wdir = _workdir(home, gid)
    files = sorted(wdir.glob("*")) if wdir.exists() else []
    return wdir, files


def test_seo_scanner(site, tmp_path):
    rep = _run("seo-basics-scanner", tmp_path, site, dry=True)
    assert rep.generator_id == "seo-basics-scanner"
    assert rep.quoted_amount_usd == 3.0
    wdir, files = _artifacts(tmp_path, "seo-basics-scanner")
    assert files == []  # dry run writes nothing
    rep = _run("seo-basics-scanner", tmp_path, site)
    wdir, files = _artifacts(tmp_path, "seo-basics-scanner")
    assert len(files) == 2
    md = next(f for f in files if f.suffix == ".md").read_text()
    assert "missing meta description" in md
    assert "Skipped h2" not in md  # heading text not echoed
    assert "heading level skip" in md
    assert "<img> without alt text" in md
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["files_scanned"] == 2
    assert data["findings"] > 0


def test_a11y_spotter(site, tmp_path):
    rep = _run("accessibility-spotter", tmp_path, site)
    assert rep.generator_id == "accessibility-spotter"
    wdir, files = _artifacts(tmp_path, "accessibility-spotter")
    md = next(f for f in files if f.suffix == ".md").read_text()
    assert "missing alt text" in md
    assert "unlabelled" in md
    assert "no visible text" in md
    assert "heading skips" in md
    assert "missing lang attribute" in md


def test_broken_link_hunter(site, tmp_path):
    rep = _run("broken-link-hunter", tmp_path, site)
    wdir, files = _artifacts(tmp_path, "broken-link-hunter")
    md = next(f for f in files if f.suffix == ".md").read_text()
    assert "missing.html" in md
    assert "#nope" in md
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["broken"] == 2
    # about.html's good link must not be flagged
    assert "about.html" not in md


def test_readme_auditor(project, tmp_path):
    rep = _run("readme-health-auditor", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "readme-health-auditor")
    md = next(f for f in files if f.suffix == ".md").read_text()
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["readme_found"] is True
    assert 0 < data["score"] < 100  # sparse fixture README
    assert "installation section" in data["missing"]
    assert "Health score" in md


def test_readme_auditor_missing(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    rep = _run("readme-health-auditor", tmp_path, d)
    assert rep.quoted_amount_usd == 2.0
    wdir, files = _artifacts(tmp_path, "readme-health-auditor")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["readme_found"] is False
    assert data["score"] == 0


def test_dependency_hygiene(project, tmp_path):
    rep = _run("dependency-hygiene-reporter", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "dependency-hygiene-reporter")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["pinned"] == 1  # requests==2.31.0
    assert data["floating"] == 2  # flask>=3.0, django
    md = next(f for f in files if f.suffix == ".md").read_text()
    assert "non-reproducible" in md


def test_backup_readiness(project, tmp_path):
    big = project / "data.bin"
    big.write_bytes(b"0" * (11 * 1024 * 1024))
    rep = _run("backup-readiness-auditor", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "backup-readiness-auditor")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert any("data.bin" in lf["path"] for lf in data["large_files"])
    assert data["score"] < 100
    assert data["gaps"]


def test_secrets_surface(project, tmp_path):
    rep = _run("secrets-surface-reporter", tmp_path, project)
    assert rep.quoted_amount_usd == 4.0
    wdir, files = _artifacts(tmp_path, "secrets-surface-reporter")
    md = next(f for f in files if f.suffix == ".md").read_text()
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["findings"] >= 1
    assert "secrets.env" in md
    # the actual secret value must NEVER appear in the report
    assert "sk-live-abcdef1234567890" not in md
    assert "sk-live-abcdef1234567890" not in json.dumps(data)
    assert "Defensive scan" in md


def test_doc_coverage(project, tmp_path):
    rep = _run("doc-coverage-reporter", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "doc-coverage-reporter")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    mod = next(r for r in data["rows"] if r["file"] == "mod.py")
    assert "undocumented" in mod["undocumented"]
    assert "Widget.method" in mod["undocumented"]
    assert "documented" not in mod["undocumented"]
    assert 0 < data["coverage_pct"] < 100


def test_todo_debt(project, tmp_path):
    rep = _run("todo-debt-collector", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "todo-debt-collector")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["items"] == 3
    assert data["by_priority"] == {"P1": 1, "P2": 2}
    kinds = {i["kind"] for i in data["detail"]}
    assert kinds == {"TODO", "FIXME", "HACK"}


def test_git_hygiene(gitrepo, tmp_path):
    rep = _run("git-hygiene-reporter", tmp_path, gitrepo)
    assert rep.generator_id == "git-hygiene-reporter"
    wdir, files = _artifacts(tmp_path, "git-hygiene-reporter")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["commits_analyzed"] == 1
    assert any(b["branch"] == "stale-branch" for b in data["branches"])
    assert data["score"] == 100 - 2 * max(0, len(data["branches"]) - 5)


def test_git_hygiene_not_a_repo(tmp_path):
    d = tmp_path / "notrepo"
    d.mkdir()
    rep = _run("git-hygiene-reporter", tmp_path, d)
    assert rep.produced == []
    assert "No git repository" in rep.notes


def test_license_auditor(project, tmp_path):
    (project / "good.py").write_text(
        "# Copyright 2026 Example Corp\n"
        "# SPDX-License-Identifier: MIT\nx = 1\n")
    rep = _run("license-header-auditor", tmp_path, project)
    wdir, files = _artifacts(tmp_path, "license-header-auditor")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["spdx_kinds"] == {"MIT": 1}
    assert "good.py" not in data["missing"]
    assert "mod.py" in data["missing"]
    assert 0 < data["coverage_pct"] < 100


def test_perf_checklist(site, tmp_path):
    rep = _run("perf-checklist-generator", tmp_path, site)
    wdir, files = _artifacts(tmp_path, "perf-checklist-generator")
    data = json.loads(next(f for f in files if f.suffix == ".json")
                      .read_text())
    assert data["pages"] == 2
    assert data["oversized_images"] == 1  # big.png is 300KB
    assert data["render_blocking"] == 1  # app.js without defer/async
    md = next(f for f in files if f.suffix == ".md").read_text()
    assert "big.png" in md
    assert "loading=lazy" in md


# --------------------------------------------------------------------------
# Cross-cutting honesty / safety tests
# --------------------------------------------------------------------------
def test_no_target_gives_advice_not_artifacts(tmp_path):
    for gid, _, _ in BATCH_C:
        if gid == "git-hygiene-reporter":
            continue  # needs a repo; missing-target path still tested below
        rep = REGISTRY.get(gid).run(_ctx(tmp_path))
        assert rep.generator_id == gid
        assert rep.produced == []
        assert "params['target']" in rep.notes
        assert _workdir(tmp_path, gid).exists() is False


def test_git_hygiene_no_target(tmp_path):
    rep = REGISTRY.get("git-hygiene-reporter").run(_ctx(tmp_path))
    assert rep.produced == []
    assert "params['target']" in rep.notes


def test_dry_run_never_writes_reports(tmp_path, site):
    for gid, _, _ in BATCH_C:
        target = site
        rep = REGISTRY.get(gid).run(_ctx(tmp_path, target, dry=True))
        assert isinstance(rep, WorkReport)
        assert rep.generator_id == gid
        wdir = _workdir(tmp_path, gid)
        assert not wdir.exists(), f"{gid} wrote files during dry_run"
        if gid == "git-hygiene-reporter":
            # the fixture site is not a git repo; it reports honestly
            # with no would-be artifacts
            continue
        # dry run still reports what WOULD be produced
        assert rep.produced, f"{gid} dry-run produced list is empty"


def test_real_run_writes_two_artifacts(tmp_path, site, project, gitrepo):
    targets = {
        "seo-basics-scanner": site,
        "accessibility-spotter": site,
        "broken-link-hunter": site,
        "readme-health-auditor": project,
        "dependency-hygiene-reporter": project,
        "backup-readiness-auditor": project,
        "secrets-surface-reporter": project,
        "doc-coverage-reporter": project,
        "todo-debt-collector": project,
        "git-hygiene-reporter": gitrepo,
        "license-header-auditor": project,
        "perf-checklist-generator": site,
    }
    for gid, _, _ in BATCH_C:
        rep = REGISTRY.get(gid).run(_ctx(tmp_path, targets[gid]))
        assert rep.generator_id == gid
        assert len(rep.produced) == 2
        wdir, files = _artifacts(tmp_path, gid)
        assert len(files) == 2
        names = {f.name for f in files}
        assert any(n.endswith("-report.md") for n in names)
        assert any(n.endswith("-summary.json") for n in names)
        # summary.json is valid JSON and names the target
        data = json.loads(next(f for f in files
                               if f.suffix == ".json").read_text())
        assert "target" in data


def test_quoted_amounts_within_doctrine():
    for gid, _, price in BATCH_C:
        assert 1.0 <= price <= 5.0


def test_missing_target_path(tmp_path):
    rep = REGISTRY.get("seo-basics-scanner").run(
        _ctx(tmp_path, tmp_path / "does-not-exist"))
    assert rep.produced == []
    assert "does not exist" in rep.notes
