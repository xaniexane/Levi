"""Hermetic tests for the flagship cross-module workflows (Megazord axis 5).

Every workflow runs against a tmp LEVI home: HOME is monkeypatched to the
tmp dir, an explicit ``home`` path is always passed, and no network, daemon,
or model is touched. Growth cycles run with ``use_model=False``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.workflows import list_workflows, run_workflow


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _levi_home(monkeypatch, tmp_path: Path) -> Path:
    """Hermetic LEVI home: isolated HOME plus an explicit home path."""
    home = tmp_path / "levi-home"
    monkeypatch.setenv("HOME", str(tmp_path))
    return home


def _finding(n: int, **over) -> dict:
    base = {
        "id": "arch-test-%d" % n,
        "title": "Test System %d" % n,
        "era": "test era",
        "kind": "software",
        "summary": "a forgotten system revived for the test bench",
        "mechanism": "ahead-of-its-time mechanism %d" % n,
        "decline": "decline cause %d" % n,
        "revival_recipe": "revive with modern capability %d" % n,
        "levi_application": "concrete local-first application %d" % n,
        "rating": "useful-pattern",
        "status": "dead",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# registry contract
# ---------------------------------------------------------------------------

def test_list_workflows_contract():
    listed = list_workflows()
    names = [w["name"] for w in listed]
    assert names == ["hunt-archive-publish", "growth-memory-lifepack",
                     "archive-showcase", "forge-ci-export", "fleet-five"]
    for w in listed:
        assert isinstance(w["summary"], str) and w["summary"]
        assert isinstance(w["steps"], list) and w["steps"]
        assert set(w.keys()) == {"name", "summary", "steps"}


def test_factory_line_framing():
    wf = {w["name"]: w for w in list_workflows()}["hunt-archive-publish"]
    assert wf["steps"] == ["intake", "process", "stock", "manufacture", "distribute"]
    assert "factory line" in wf["summary"].lower()


def test_unknown_workflow_raises_valueerror(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        run_workflow("does-not-exist", home=home)


# ---------------------------------------------------------------------------
# hunt-archive-publish (the factory line)
# ---------------------------------------------------------------------------

def test_hunt_archive_publish_ok(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    # two buildable finds + one hard-route find (cost signal -> waymaker)
    # + one inspirational find (no standing build order -> waymaker)
    hard = _finding(3, revival_recipe="revive it via a paid api subscription")
    insp = _finding(4, rating="inspirational")
    findings = [_finding(1), _finding(2), hard, insp]
    result = run_workflow("hunt-archive-publish", home=home, findings=findings)

    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == [
        "intake", "process", "stock", "manufacture", "distribute"]
    assert all(s["ok"] for s in result["steps"])

    steps = {s["name"]: s for s in result["steps"]}
    assert steps["intake"]["detail"]["records"] == 4
    assert steps["stock"]["detail"]["added"] == 4
    assert steps["manufacture"]["detail"]["build_queued"] == 3
    assert steps["manufacture"]["detail"]["waymaker_jobs"] == 2

    # the waymaker law: no existing way is never a dead end
    jobs = result["waymaker_jobs"]
    assert len(jobs) == 2
    assert all(j["kind"] == "waymaker" for j in jobs)
    by_id = {j["finding"]: j for j in jobs}
    assert by_id["arch-test-4"]["note"] == "no existing way — queued to manufacture one"
    assert "clean-room" in by_id["arch-test-3"]["note"]
    assert "paid api" in by_id["arch-test-3"]["signals"]

    # ingest queue file exists and carries both records
    queue = Path(result["artifacts"]["queue_path"])
    assert queue.is_file()
    queued = [json.loads(l) for l in queue.read_text().splitlines() if l.strip()]
    assert len(queued) == 4

    # galaxy registry holds the published collection
    from levi.galaxy.registry import GalaxyRegistry
    reg = GalaxyRegistry(home)
    rec = reg.get(result["artifacts"]["package_id"])
    assert rec is not None
    assert rec["kind"] == "archive-collection"

    # idempotent re-run: intake re-validates, stock skips dupes, publish replaces
    rerun = run_workflow("hunt-archive-publish", home=home, findings=findings,
                         wave_id=result["artifacts"]["wave_id"])
    assert rerun["ok"] is True
    stock = {s["name"]: s for s in rerun["steps"]}["stock"]
    assert stock["detail"]["added"] == 0
    assert stock["detail"]["skipped_duplicates"] == 4


def test_hunt_archive_publish_no_findings_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("hunt-archive-publish", home=home)
    assert result["ok"] is False
    assert result["steps"][0]["name"] == "intake"
    assert result["steps"][0]["ok"] is False
    assert "reason" in result["steps"][0]
    # nothing was published on a failed run
    assert "package_id" not in result["artifacts"]


def test_hunt_archive_publish_bad_record_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    bad = _finding(9)
    bad["title"] = ""  # ArchiveRecord refuses empty titles
    result = run_workflow("hunt-archive-publish", home=home, findings=[bad])
    assert result["ok"] is False
    assert result["steps"][0]["ok"] is False


# ---------------------------------------------------------------------------
# growth-memory-lifepack
# ---------------------------------------------------------------------------

def test_growth_memory_lifepack_ok(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("growth-memory-lifepack", home=home,
                          use_model=False, dry_run=False)

    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == [
        "growth_cycle", "memory_consolidate", "lifepack_export"]
    steps = {s["name"]: s for s in result["steps"]}
    assert steps["growth_cycle"]["detail"]["cycle_id"]
    assert "accepted" in steps["memory_consolidate"]["detail"]

    # lifepack validated and written to the hermetic home
    pack_path = Path(result["artifacts"]["pack_path"])
    assert pack_path.is_file()
    pack = json.loads(pack_path.read_text())
    assert pack["sections"]["identity"] is not None
    assert str(home) in str(pack_path)
    # growth journal landed under the hermetic home, not the real one
    assert (home / "growth" / "journal.jsonl").is_file()


def test_growth_memory_lifepack_dry_run_writes_nothing(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("growth-memory-lifepack", home=home,
                          use_model=False, dry_run=True)
    assert result["ok"] is True
    assert result["artifacts"]["pack_path"] is None
    assert not list((home / "lifepacks").glob("*")) if (home / "lifepacks").exists() else True
    assert not (home / "growth" / "journal.jsonl").exists()


def test_growth_memory_lifepack_bad_store_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("growth-memory-lifepack", home=home,
                          use_model=False, store=object())
    assert result["ok"] is False
    assert result["steps"][0]["name"] == "growth_cycle"
    assert result["steps"][0]["ok"] is False
    assert "reason" in result["steps"][0]


# ---------------------------------------------------------------------------
# archive-showcase
# ---------------------------------------------------------------------------

def test_archive_showcase_ok(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    # seed the archive through the real factory line
    seeded = run_workflow("hunt-archive-publish", home=home,
                          findings=[_finding(1), _finding(2, title="Another Test Widget")])
    assert seeded["ok"] is True

    result = run_workflow("archive-showcase", home=home, query="Test System",
                          title="Test picks")
    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == [
        "archive_search", "assemble_collection", "galaxy_publish"]
    steps = {s["name"]: s for s in result["steps"]}
    assert steps["archive_search"]["detail"]["hits"] >= 1
    collection = result["artifacts"]["collection"]
    assert collection["title"] == "Test picks"
    assert collection["record_count"] >= 1

    from levi.galaxy.registry import GalaxyRegistry
    reg = GalaxyRegistry(home)
    assert reg.get(result["artifacts"]["package_id"]) is not None


def test_archive_showcase_no_hits_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("archive-showcase", home=home,
                          query="zzz-no-such-thing-zzz")
    assert result["ok"] is False
    assert result["steps"][0]["name"] == "archive_search"
    assert result["steps"][0]["ok"] is False


def test_archive_showcase_bad_filter_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("archive-showcase", home=home, query="test", kind="nope")
    assert result["ok"] is False
    assert result["steps"][0]["ok"] is False
    assert "reason" in result["steps"][0]


def test_emit_is_defensive():
    from levi.workflows import _common
    # never raises, whatever the bus situation is
    assert isinstance(_common.emit("workflow.done", {"ok": True}), bool)
    assert isinstance(_common.emit("workflow.done", None), bool)


def test_emit_publishes_on_real_bus():
    bus = pytest.importorskip("levi.bloodstream.bus")
    seen = []
    tok = bus.subscribe("levi.workflows.done", lambda t, p: seen.append(t))
    try:
        from levi.workflows import _common
        assert _common.emit("workflow.done", {"ok": True}) is True
        assert seen == ["levi.workflows.done"]
    finally:
        bus.unsubscribe(tok)


# ---------------------------------------------------------------------------
# forge-ci-export
# ---------------------------------------------------------------------------

def _seed_commit(repo_path: Path, tmp_path: Path) -> None:
    """Put one real commit into a forge bare repo (clone -> commit -> push)."""
    import subprocess

    work = tmp_path / "seedwork"
    subprocess.run(["git", "clone", "-q", str(repo_path), str(work)],
                   check=True, capture_output=True)
    (work / "hello.txt").write_text("hello from the forge test\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=work, check=True,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-qm", "seed"], cwd=work, check=True,
                   capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=work,
                   check=True, capture_output=True)


def test_forge_ci_export_ok(monkeypatch, tmp_path):
    import shutil

    from levi.forge import repos as _repos

    home = _levi_home(monkeypatch, tmp_path)
    fhome = home / "forge"
    _repos.create_repo(str(fhome), "demo", description="workflow test repo")
    _seed_commit(fhome / "repos" / "demo.git", tmp_path)

    result = run_workflow("forge-ci-export", home=home, repo="demo")
    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == ["init", "ci_run", "export"]
    assert all(s["ok"] for s in result["steps"])
    assert result["steps"][0]["detail"]["created"] is False  # reused, honestly

    export_path = Path(result["artifacts"]["export_path"])
    assert (export_path / "repo.bundle").is_file()
    assert (export_path / "ci" / "pipeline.json").is_file()
    assert str(home) in str(export_path)

    # re-run reuses the repo but picks a fresh unique export dest
    shutil.rmtree(tmp_path / "seedwork")
    rerun = run_workflow("forge-ci-export", home=home, repo="demo")
    assert rerun["ok"] is True
    assert rerun["artifacts"]["export_path"] != result["artifacts"]["export_path"]


def test_forge_ci_export_creates_repo(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    # the repo does not exist: the workflow creates it honestly (init reports
    # created=True); the default pipeline then fails on the empty repo —
    # an honest red build, which is exactly the workflow's gate
    result = run_workflow("forge-ci-export", home=home, repo="auto")
    assert result["ok"] is False
    assert result["steps"][0]["detail"]["created"] is True
    from levi.forge import repos as _repos
    assert _repos.repo_exists(str(home / "forge"), "auto")


def test_forge_ci_export_red_ci_fails_honestly(monkeypatch, tmp_path):
    from levi.forge import repos as _repos

    home = _levi_home(monkeypatch, tmp_path)
    # bare repo with no commits: the default pipeline's `git rev-parse HEAD`
    # fails -> honest red build, and no export is attempted
    _repos.create_repo(str(home / "forge"), "empty", description="no commits")

    result = run_workflow("forge-ci-export", home=home, repo="empty")
    assert result["ok"] is False
    assert [s["name"] for s in result["steps"]] == ["init", "ci_run"]
    assert result["steps"][1]["ok"] is False
    assert "reason" in result["steps"][1]
    assert "export_path" not in result["artifacts"]


def test_forge_ci_export_missing_repo_name_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("forge-ci-export", home=home)
    assert result["ok"] is False
    assert result["steps"][0]["name"] == "init"
    assert result["steps"][0]["ok"] is False
