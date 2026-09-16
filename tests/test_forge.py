"""LEVI Forge tests — hermetic.

All forge state goes to a tmp dir via the ``LEVI_FORGE_HOME`` env var
(resolved lazily at call time, so no module patching is needed) or via the
explicit ``home=`` parameter on the CLI ``main()``. Tests that need the
real ``git`` binary are skipped gracefully when it is absent.
"""

import json
import os
import subprocess
import threading
import urllib.error
import urllib.request

import pytest

from levi.forge import browse as _browse
from levi.forge import ci as _ci
from levi.forge import export as _export
from levi.forge import issues as _issues
from levi.forge import prs as _prs
from levi.forge import repos as _repos
from levi.forge import server as _server
from levi.forge import stars as _stars
from levi.forge.__main__ import main as forge_main
from levi.forge.gitx import GitError, git_available, run_git
from levi.forge.home import forge_home, validate_name

needs_git = pytest.mark.skipif(not git_available(), reason="git binary not found")


@pytest.fixture
def fh(monkeypatch, tmp_path):
    """Hermetic forge home: LEVI_FORGE_HOME -> tmp dir."""
    monkeypatch.setenv("LEVI_FORGE_HOME", str(tmp_path / "forgehome"))
    return tmp_path / "forgehome"


@pytest.fixture
def git_env():
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Forge Test",
        GIT_AUTHOR_EMAIL="test@forge.local",
        GIT_COMMITTER_NAME="Forge Test",
        GIT_COMMITTER_EMAIL="test@forge.local",
    )
    return env


def _git(args, cwd, env, timeout=60):
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=env,
        timeout=timeout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


# -- home / names -------------------------------------------------------


def test_home_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_FORGE_HOME", str(tmp_path / "x"))
    assert forge_home() == tmp_path / "x"


def test_home_lazy_home_env(monkeypatch, tmp_path):
    # Path.home() is read at CALL time, so patching HOME works —
    # this is the lesson from test_entrypoints_finance.py, done right.
    monkeypatch.delenv("LEVI_FORGE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert forge_home() == tmp_path / ".levi" / "forge"


def test_validate_name():
    assert validate_name("hello-world_2.0") == "hello-world_2.0"
    assert validate_name("demo.git") == "demo"  # .git suffix stripped
    for bad in ("", "../evil", "a b", "-lead", "a" * 101, "semi;colon"):
        with pytest.raises(ValueError):
            validate_name(bad)


# -- repos --------------------------------------------------------------


@needs_git
def test_repo_crud(fh):
    r = _repos.create_repo(None, "demo", description="a demo")
    assert r["name"] == "demo"
    assert _repos.repo_exists(None, "demo")
    assert any(x["name"] == "demo" for x in _repos.list_repos(None))
    with pytest.raises(GitError):
        _repos.create_repo(None, "demo")  # duplicate refused
    _repos.delete_repo(None, "demo")
    assert not _repos.repo_exists(None, "demo")
    with pytest.raises(GitError):
        _repos.delete_repo(None, "demo")


@needs_git
def test_delete_removes_metadata(fh):
    _repos.create_repo(None, "gone")
    _issues.open_issue(None, "gone", "t")
    _prs_path = fh / "prs" / "gone.jsonl"
    _repos.delete_repo(None, "gone")
    assert not (fh / "issues" / "gone.jsonl").exists()
    assert not _prs_path.exists()


# -- issues -------------------------------------------------------------


@needs_git
def test_issues_lifecycle(fh):
    _repos.create_repo(None, "iss")
    i = _issues.open_issue(
        None, "iss", "Bug: frobnicate", body="details", labels=["bug"]
    )
    assert i["id"] == 1 and i["state"] == "open"
    j = _issues.open_issue(None, "iss", "Second")
    assert j["id"] == 2
    assert len(_issues.list_issues(None, "iss")) == 2
    assert len(_issues.list_issues(None, "iss", state="open")) == 2
    _issues.comment_issue(None, "iss", 1, "reproduced")
    got = _issues.get_issue(None, "iss", 1)
    assert len(got["comments"]) == 1
    _issues.close_issue(None, "iss", 1)
    assert _issues.get_issue(None, "iss", 1)["state"] == "closed"
    _issues.reopen_issue(None, "iss", 1)
    assert _issues.get_issue(None, "iss", 1)["state"] == "open"
    with pytest.raises(ValueError):
        _issues.open_issue(None, "iss", "   ")
    with pytest.raises(ValueError):
        _issues.open_issue(None, "nosuchrepo", "t")


# -- pull requests ------------------------------------------------------


@needs_git
def test_pr_open_merge(fh, tmp_path, git_env):
    _repos.create_repo(None, "prj")
    work = tmp_path / "work"
    _git(["clone", "-q", str(fh / "repos" / "prj.git"), str(work)], tmp_path, git_env)
    (work / "a.txt").write_text("hello\n")
    _git(["add", "a.txt"], work, git_env)
    _git(["commit", "-qm", "init"], work, git_env)
    _git(["push", "-q", "origin", "main"], work, git_env)
    _git(["checkout", "-qb", "feature"], work, git_env)
    (work / "b.txt").write_text("feature\n")
    _git(["add", "b.txt"], work, git_env)
    _git(["commit", "-qm", "feat"], work, git_env)
    _git(["push", "-q", "origin", "feature"], work, git_env)

    p = _prs.open_pr(None, "prj", "Add feature", head="feature", base="main")
    assert p["id"] == 1 and p["state"] == "open"
    with pytest.raises(ValueError):
        _prs.open_pr(None, "prj", "bad", head="nope", base="main")
    merged = _prs.merge_pr(None, "prj", 1)
    assert merged["state"] == "merged" and merged["merge_commit"]
    # base now contains the feature file
    out = run_git(["show", "main:b.txt"], cwd=fh / "repos" / "prj.git").stdout.decode()
    assert out == "feature\n"
    with pytest.raises(ValueError):
        _prs.merge_pr(None, "prj", 1)  # already merged


@needs_git
def test_pr_merge_conflict_leaves_open(fh, tmp_path, git_env):
    _repos.create_repo(None, "conf")
    work = tmp_path / "work"
    _git(["clone", "-q", str(fh / "repos" / "conf.git"), str(work)], tmp_path, git_env)
    (work / "f.txt").write_text("base\n")
    _git(["add", "f.txt"], work, git_env)
    _git(["commit", "-qm", "init"], work, git_env)
    _git(["push", "-q", "origin", "main"], work, git_env)
    _git(["checkout", "-qb", "side"], work, git_env)
    (work / "f.txt").write_text("side\n")
    _git(["commit", "-qam", "side change"], work, git_env)
    _git(["push", "-q", "origin", "side"], work, git_env)
    _git(["checkout", "-q", "main"], work, git_env)
    (work / "f.txt").write_text("main\n")
    _git(["commit", "-qam", "main change"], work, git_env)
    _git(["push", "-q", "origin", "main"], work, git_env)

    _prs.open_pr(None, "conf", "Conflicting", head="side", base="main")
    with pytest.raises(GitError):
        _prs.merge_pr(None, "conf", 1)
    assert _prs.get_pr(None, "conf", 1)["state"] == "open"


# -- stars --------------------------------------------------------------


def test_stars(fh):
    assert not _stars.is_starred(None, "x")
    _stars.star(None, "x")
    assert _stars.is_starred(None, "x")
    assert "x" in _stars.starred(None)
    assert _stars.unstar(None, "x")
    assert not _stars.is_starred(None, "x")
    assert not _stars.unstar(None, "x")


# -- browse / markdown --------------------------------------------------


@needs_git
def test_browse_tree_log(fh, tmp_path, git_env):
    _repos.create_repo(None, "brw")
    work = tmp_path / "work"
    _git(["clone", "-q", str(fh / "repos" / "brw.git"), str(work)], tmp_path, git_env)
    (work / "README.md").write_text("# Title\n\nhello **world**\n")
    (work / "src").mkdir()
    (work / "src" / "main.py").write_text("print('x')\n")
    _git(["add", "."], work, git_env)
    _git(["commit", "-qm", "first commit"], work, git_env)
    _git(["push", "-q", "origin", "main"], work, git_env)

    entries = _browse.tree(None, "brw")
    names = {e["name"]: e["type"] for e in entries}
    assert names == {"README.md": "blob", "src": "tree"}
    assert _browse.read_file(None, "brw", path="src/main.py") == "print('x')\n"
    assert _browse.find_readme(None, "brw") == "README.md"
    commits = _browse.log(None, "brw")
    assert len(commits) == 1 and commits[0]["subject"] == "first commit"
    with pytest.raises(GitError):
        _browse.read_file(None, "brw", path="nope.txt")


def test_markdown_render():
    html = _browse.render_markdown(
        "# Head\n\npara with **bold**, *em*, `code`, [link](https://x.y)\n\n"
        "- a\n- b\n\n```py\nprint(1)\n```\n\n> quote\n"
    )
    assert "<h1>Head</h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>em</em>" in html
    assert "<code>code</code>" in html
    assert '<a href="https://x.y">link</a>' in html
    assert "<ul>" in html and "<li>a</li>" in html
    assert "<pre><code" in html and "print(1)" in html
    assert "<blockquote>quote</blockquote>" in html
    # HTML in source is escaped, not injected
    assert "<script>" not in _browse.render_markdown("<script>alert(1)</script>")


# -- smart HTTP server --------------------------------------------------


@needs_git
def test_smart_http_clone_and_push(fh, tmp_path, git_env):
    _repos.create_repo(None, "srv")
    srv = _server.serve(home=None, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        port = srv.server_address[1]
        base = "http://127.0.0.1:%d" % port
        work = tmp_path / "clone"
        _git(["clone", "-q", base + "/srv.git", str(work)], tmp_path, git_env)
        _git(["checkout", "-qb", "main"], work, git_env)  # empty clone: no branch yet
        (work / "hello.txt").write_text("via http\n")
        _git(["add", "hello.txt"], work, git_env)
        _git(["commit", "-qm", "http commit"], work, git_env)
        _git(["push", "-q", "origin", "main"], work, git_env)
        # round-trip: fresh clone sees the pushed commit
        work2 = tmp_path / "clone2"
        _git(["clone", "-q", base + "/srv.git", str(work2)], tmp_path, git_env)
        assert (work2 / "hello.txt").read_text() == "via http\n"
        log = _git(["log", "--oneline"], work2, git_env).stdout.decode()
        assert "http commit" in log
    finally:
        srv.shutdown()
        srv.server_close()


@needs_git
def test_web_ui_pages(fh, tmp_path, git_env):
    _repos.create_repo(None, "web", description="web demo")
    _issues.open_issue(None, "web", "An issue")
    srv = _server.serve(home=None, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        port = srv.server_address[1]

        def get(path):
            with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (port, path), timeout=10
            ) as r:
                return r.status, r.read().decode("utf-8")

        status, body = get("/forge/")
        assert status == 200 and "web" in body and "LEVI Forge" in body
        status, body = get("/forge/web/")
        assert status == 200 and "issues" in body
        status, body = get("/forge/web/issues")
        assert status == 200 and "An issue" in body
        status, body = get("/forge/web/log")
        assert status == 200
        try:
            get("/forge/nosuchrepo/")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_serve_refuses_non_localhost(fh):
    with pytest.raises(ValueError):
        _server.serve(home=None, bind="0.0.0.0", port=0)


# -- CI -----------------------------------------------------------------


@needs_git
def test_ci_init_run(fh, tmp_path, git_env):
    _repos.create_repo(None, "cip")
    _git(
        ["clone", "-q", str(fh / "repos" / "cip.git"), str(tmp_path / "w")],
        tmp_path,
        git_env,
    )
    w = tmp_path / "w"
    (w / "x.txt").write_text("x\n")
    _git(["add", "x.txt"], w, git_env)
    _git(["commit", "-qm", "c1"], w, git_env)
    _git(["push", "-q", "origin", "main"], w, git_env)

    pipe = _ci.init_pipeline(None, "cip")
    assert len(pipe["steps"]) == 2
    rec = _ci.run_pipeline(None, "cip")
    assert rec["ok"] and rec["commit"]
    assert all(s["rc"] == 0 for s in rec["steps"])
    run_dir = fh / "ci" / "cip" / "runs" / rec["id"]
    assert (run_dir / "run.json").is_file()
    logs = list(run_dir.glob("step-*.log"))
    assert len(logs) == 2
    assert len(_ci.list_runs(None, "cip")) == 1


@needs_git
def test_ci_failing_step(fh, tmp_path, git_env):
    _repos.create_repo(None, "cif")
    _git(
        ["clone", "-q", str(fh / "repos" / "cif.git"), str(tmp_path / "w")],
        tmp_path,
        git_env,
    )
    w = tmp_path / "w"
    (w / "x.txt").write_text("x\n")
    _git(["add", "x.txt"], w, git_env)
    _git(["commit", "-qm", "c1"], w, git_env)
    _git(["push", "-q", "origin", "main"], w, git_env)
    _ci.init_pipeline(
        None,
        "cif",
        {
            "version": 1,
            "name": "t",
            "steps": [
                {"name": "ok-step", "run": "git rev-parse HEAD"},
                {"name": "bad-step", "run": "git rev-parse NOPE"},
            ],
        },
    )
    rec = _ci.run_pipeline(None, "cif")
    assert not rec["ok"]
    assert [s["rc"] for s in rec["steps"]] == [0, 128]
    assert forge_main(["ci", "cif", "run"], home=None) == 1


@needs_git
def test_ci_no_pipeline(fh):
    _repos.create_repo(None, "cin")
    with pytest.raises(ValueError):
        _ci.run_pipeline(None, "cin")


# -- export / import ----------------------------------------------------


@needs_git
def test_export_import_roundtrip(fh, tmp_path, git_env):
    _repos.create_repo(None, "exp", description="export me")
    work = tmp_path / "work"
    _git(["clone", "-q", str(fh / "repos" / "exp.git"), str(work)], tmp_path, git_env)
    (work / "README.md").write_text("# exp\n")
    _git(["add", "README.md"], work, git_env)
    _git(["commit", "-qm", "c1"], work, git_env)
    _git(["push", "-q", "origin", "main"], work, git_env)
    _issues.open_issue(None, "exp", "Export issue", labels=["x"])
    _stars.star(None, "exp")
    _ci.init_pipeline(None, "exp")
    _ci.run_pipeline(None, "exp")

    dest = tmp_path / "exported"
    out = _export.export_repo(None, "exp", dest)
    assert (out / "repo.bundle").is_file()
    assert (out / "FORGE-EXPORT.md").is_file()
    assert (out / "SHA256SUMS").is_file()
    assert (out / "contrib.json").is_file()
    lines = [
        json.loads(l)
        for l in (out / "issues.jsonl").read_text().splitlines()
        if l.strip()
    ]
    assert lines[0]["title"] == "Export issue"
    assert json.loads((out / "stars.json").read_text())["starred"] is True
    assert (out / "ci" / "pipeline.json").is_file()

    # import into a FRESH forge home
    fresh = tmp_path / "fresh"
    r = _export.import_repo(str(fresh), dest, name="exp2")
    assert r["name"] == "exp2"
    assert _repos.repo_exists(str(fresh), "exp2")
    assert _browse.read_file(str(fresh), "exp2", path="README.md") == "# exp\n"
    assert len(_issues.list_issues(str(fresh), "exp2")) == 1
    assert _stars.is_starred(str(fresh), "exp2")
    assert len(_ci.list_runs(str(fresh), "exp2")) == 1
    # duplicate import refused
    with pytest.raises(GitError):
        _export.import_repo(str(fresh), dest, name="exp2")


@needs_git
def test_import_rejects_tampered_export(fh, tmp_path, git_env):
    _repos.create_repo(None, "tam")
    dest = tmp_path / "tamexp"
    _export.export_repo(None, "tam", dest)
    with open(dest / "issues.jsonl", "a", encoding="utf-8") as fh2:
        fh2.write('{"id": 999, "evil": true}\n')
    with pytest.raises(GitError):
        _export.import_repo(str(tmp_path / "fresh2"), dest)


# -- CLI entrypoint -----------------------------------------------------


@needs_git
def test_cli_repos_create_list(fh, capsys):
    assert forge_main(["repos", "create", "cli1", "--desc", "d"], home=None) == 0
    assert "cli1" in capsys.readouterr().out
    assert forge_main(["repos"], home=None) == 0
    assert "cli1" in capsys.readouterr().out


def test_cli_help_states_ownership(capsys):
    with pytest.raises(SystemExit) as e:
        forge_main(["--help"])
    assert e.value.code == 0
    assert "never transmits your code anywhere" in capsys.readouterr().out


def test_cli_requires_repo_name(fh):
    with pytest.raises(SystemExit) as e:  # argparse: missing positional
        forge_main(["browse"], home=None)
    assert e.value.code == 2
    assert forge_main(["issue", "x", "open"], home=None) == 2  # missing --title


@needs_git
def test_cli_issue_pr_flow(fh, tmp_path, git_env, capsys):
    assert forge_main(["repos", "create", "flow"], home=None) == 0
    assert forge_main(["issue", "flow", "open", "--title", "T1"], home=None) == 0
    assert forge_main(["issue", "flow", "list"], home=None) == 0
    assert "T1" in capsys.readouterr().out
    assert forge_main(["star", "flow"], home=None) == 0
    assert forge_main(["stars"], home=None) == 0
    assert "flow" in capsys.readouterr().out
    assert forge_main(["export", "flow", "--out", str(tmp_path / "e")], home=None) == 0
    assert (tmp_path / "e" / "FORGE-EXPORT.md").is_file()
    assert (
        forge_main(["import", str(tmp_path / "e"), "--name", "flow2"], home=None) == 0
    )
    assert forge_main(["repos"], home=None) == 0
    assert "flow2" in capsys.readouterr().out
