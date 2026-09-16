"""Hermetic tests for the LEVI Builder (core/levi/builder/).

No network, no providers, no pip: generation is stubbed, servers boot on
127.0.0.1 only, and the council is simulated via sys.modules patching.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

import pytest

from levi.builder import pipeline as pipeline_mod
from levi.builder.cli import cmd_build, register_builder_parser
from levi.builder.exporter import export_project
from levi.builder.generate import GenerationError, strip_fences, stub_generator
from levi.builder.pipeline import (
    _write_tree,
    plan_preview,
    run_build,
    smoke_test,
)
from levi.builder.quality import gate_python_file, static_gate
from levi.builder.scaffolds import list_scaffolds, render_scaffold
from levi.builder.scaffolds.spec import heuristic_spec


# ---------------------------------------------------------------------------
# Canned generator outputs
# ---------------------------------------------------------------------------

_PLANNER_JSON = json.dumps(
    {
        "name": "testapp",
        "title": "Test App",
        "description": "a test app",
        "stack": "fullstack",
        "entities": [{"name": "note", "fields": ["id", "body"]}],
        "api_routes": [
            {
                "method": "GET",
                "path": "/api/health",
                "handler": "health",
                "description": "liveness probe",
            },
        ],
        "pages": ["home"],
        "features": ["keeps notes", "runs offline"],
    }
)

_FRONTEND_HTML = (
    "<!DOCTYPE html><html><head><title>Test App</title></head>"
    "<body><h1>Test App</h1></body></html>"
)

_BACKEND_PY = '''"""Canned backend for builder tests."""

ROUTES = [
    ("GET", r"^/api/health$", "health"),
]


def health(request, db):
    return 200, {"Content-Type": "application/json"}, {"ok": True}
'''

_SCHEMA_SQL = "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT);\n"

_TESTER_JSON = json.dumps(
    [
        {"method": "GET", "path": "/", "expect_status": 200},
        {
            "method": "GET",
            "path": "/api/health",
            "expect_status": 200,
            "expect_contains": "ok",
        },
    ]
)


def _stub() -> "callable":
    return stub_generator(
        {
            "build spec": _PLANNER_JSON,
            "frontend": _FRONTEND_HTML,
            "handlers.py": _BACKEND_PY,
            "schema.sql": _SCHEMA_SQL,
            "assertions": _TESTER_JSON,
        }
    )


def _write_project(tmp_path: Path, stack: str = "fullstack") -> Path:
    spec = heuristic_spec("a notes app", stack, "notesapp")
    files = render_scaffold(stack, spec)
    project = tmp_path / "proj"
    project.mkdir()
    _write_tree(project, files)
    return project


# ---------------------------------------------------------------------------
# Scaffolds
# ---------------------------------------------------------------------------


def test_scaffold_choices():
    assert set(list_scaffolds()) == {"static", "fullstack"}


def test_static_scaffold_tree_and_content():
    spec = heuristic_spec("a guestbook", "static", "guestbook")
    files = render_scaffold("static", spec)
    assert set(files) == {"index.html", "README.md"}
    html = files["index.html"]
    assert "Guestbook" in html
    assert "<script>" in html and "</html>" in html
    for needle in ("npm", "pip install", "node_modules"):
        assert needle not in html
        assert needle not in files["README.md"]
    assert "python3 -m http.server" in files["README.md"]


def test_fullstack_scaffold_tree_and_compiles(tmp_path):
    spec = heuristic_spec("a notes app", "fullstack", "notesapp")
    files = render_scaffold("fullstack", spec)
    expected = {
        "app/__init__.py",
        "app/__main__.py",
        "app/server.py",
        "app/db.py",
        "app/handlers.py",
        "app/static/index.html",
        "schema.sql",
        "README.md",
    }
    assert expected <= set(files)
    project = _write_project(tmp_path, "fullstack")
    import py_compile

    for rel in expected:
        if rel.endswith(".py"):
            py_compile.compile(str(project / rel), doraise=True)


def test_fullstack_scaffold_boots_and_serves(tmp_path):
    project = _write_project(tmp_path, "fullstack")
    result = smoke_test(
        project,
        "fullstack",
        [
            {"method": "GET", "path": "/", "expect_status": 200},
            {
                "method": "GET",
                "path": "/api/health",
                "expect_status": 200,
                "expect_contains": "ok",
            },
        ],
    )
    assert result["failures"] == [], result
    assert result["passed"] == result["total"] == 2


def test_fullstack_api_roundtrip(tmp_path):
    """POST a note then GET it back — the default handlers really work."""
    import urllib.request

    project = _write_project(tmp_path, "fullstack")
    port = pipeline_mod._free_port()
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=str(project),
        env={"PORT": str(port), "HOST": "127.0.0.1", "PATH": "/usr/bin:/bin"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert pipeline_mod._wait_ready(port), "server did not start"
        payload = json.dumps({"name": "hello", "body": "world"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/notes",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 201
            created = json.loads(r.read())
            assert created["name"] == "hello"
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/notes", timeout=5
        ) as r:
            items = json.loads(r.read())
            assert any(i["name"] == "hello" for i in items)
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_static_scaffold_serves(tmp_path):
    project = _write_project(tmp_path, "static")
    result = smoke_test(
        project,
        "static",
        [
            {
                "method": "GET",
                "path": "/",
                "expect_status": 200,
                "expect_contains": "Notesapp",
            },
        ],
    )
    assert result["failures"] == [], result
    assert result["passed"] == 1


def test_unknown_stack_rejected():
    spec = heuristic_spec("x", "fullstack", "x")
    with pytest.raises(ValueError):
        render_scaffold("nope", spec)


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


def test_exporter_roundtrip_tarball(tmp_path):
    project = _write_project(tmp_path, "fullstack")
    (project / "data").mkdir(exist_ok=True)
    (project / "data" / "app.db").write_bytes(b"fake-db-bytes")
    (project / "app" / "__pycache__").mkdir(exist_ok=True)
    (project / "app" / "__pycache__" / "x.pyc").write_bytes(b"fake")
    archive = export_project(project, dest_dir=tmp_path / "out")
    assert archive.suffixes[-2:] == [".tar", ".gz"]
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert any(n.endswith("app/server.py") for n in names)
    assert not any(n.endswith("app.db") for n in names), "sqlite db must not ship"
    assert not any("__pycache__" in n for n in names)
    assert all(n.startswith("proj/") for n in names)


def test_exporter_zip_format(tmp_path):
    project = _write_project(tmp_path, "static")
    archive = export_project(project, dest_dir=tmp_path / "out", fmt="zip")
    assert archive.suffix == ".zip"


def test_exporter_rejects_bad_inputs(tmp_path):
    with pytest.raises(ValueError):
        export_project(tmp_path / "missing")
    project = _write_project(tmp_path, "static")
    with pytest.raises(ValueError):
        export_project(project, fmt="rar")


# ---------------------------------------------------------------------------
# Pipeline (stubbed generation — hermetic)
# ---------------------------------------------------------------------------


def test_pipeline_fullstack_with_stub(tmp_path):
    report = run_build(
        "a notes app",
        stack="fullstack",
        name="testapp",
        out_dir=tmp_path,
        generate=_stub(),
        quality="static",
    )
    assert report.ok, report.summary()
    assert report.spec_source == "planner"
    project = Path(report.project_dir)
    assert (project / "app" / "handlers.py").read_text().strip().startswith('"""Canned')
    assert (project / "levi-build.json").is_file()
    manifest = json.loads((project / "levi-build.json").read_text())
    assert manifest["name"] == "testapp"
    assert manifest["guarantees"]["no_training_data_harvesting"]
    assert manifest["run"]["stdlib_only"] is True
    assert report.smoke["passed"] == report.smoke["total"] == 2
    assert set(report.quality) >= {"app/__main__.py", "app/handlers.py"}
    assert all(v["passed"] for v in report.quality.values())


def test_pipeline_static_stack_with_stub(tmp_path):
    report = run_build(
        "a landing page",
        stack="static",
        name="landing",
        out_dir=tmp_path,
        generate=_stub(),
        quality="off",
    )
    assert report.ok, report.summary()
    project = Path(report.project_dir)
    assert (project / "index.html").is_file()
    assert not (project / "app").exists()


def test_pipeline_planner_fallback_is_honest(tmp_path):
    def _boom(prompt: str, system: str) -> str:
        raise GenerationError("no provider")

    report = run_build(
        "a notes app",
        stack="fullstack",
        name="fallbackapp",
        out_dir=tmp_path,
        generate=_boom,
        quality="off",
    )
    assert report.ok, report.summary()
    assert report.spec_source == "heuristic"
    manifest = json.loads((Path(report.project_dir) / "levi-build.json").read_text())
    assert manifest["spec"]["spec_source"] == "heuristic"


def test_pipeline_with_export(tmp_path):
    report = run_build(
        "a notes app",
        stack="static",
        name="expapp",
        out_dir=tmp_path,
        generate=_stub(),
        quality="off",
        export=True,
    )
    assert report.ok, report.summary()
    assert report.export_path is not None
    assert Path(report.export_path).is_file()


def test_plan_preview_lists_stages():
    full = plan_preview("an app", "fullstack", "myapp")
    assert "planner" in full and "tester" in full and "packager" in full
    static = plan_preview("an app", "static", "myapp")
    assert "backend" not in static and "frontend" in static


def test_heuristic_spec_labeled():
    spec = heuristic_spec("track my books", "fullstack", "books")
    assert spec.spec_source == "heuristic"
    assert spec.api_routes and spec.entities


def test_strip_fences():
    assert strip_fences("```python\nprint(1)\n```") == "print(1)"
    assert strip_fences("plain") == "plain"


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------


def test_static_gate_passes_clean_code():
    result = static_gate("x.py", "def f(a):\n    return a + 1\n")
    assert result.passed and result.method == "static"


def test_static_gate_rejects_syntax_error():
    result = static_gate("x.py", "def broken(:\n")
    assert not result.passed


def test_static_gate_rejects_giant_function():
    body = "\n".join(f"    x{i} = {i}" for i in range(200))
    result = static_gate("x.py", f"def big():\n{body}\n    return 1\n")
    assert not result.passed
    assert "too long" in result.notes[0]


def test_quality_fallback_when_council_missing(monkeypatch):
    """Unfinished council → graceful static-only degradation, seam noted."""
    monkeypatch.setitem(sys.modules, "levi.council.cli", None)
    code = "def f(a):\n    return a\n"
    shipped, result = gate_python_file("x.py", code, quality="auto")
    assert shipped == code
    assert result.passed and result.method == "static"
    assert any("council unavailable" in n for n in result.notes)


def test_council_gate_adopts_winner(monkeypatch):
    """Council CLI contract: winner code replaces the draft."""
    improved = '"""Improved."""\n\nROUTES = []\n'

    class _FakeCouncil:
        @staticmethod
        def cmd_council(args):
            Path(args.write).write_text(improved, encoding="utf-8")
            return 0

    monkeypatch.setitem(sys.modules, "levi.council.cli", _FakeCouncil())
    shipped, result = gate_python_file(
        "x.py", "def f():\n    pass\n", quality="council"
    )
    assert result.method == "council"
    assert shipped == improved


def test_quality_off_skips_everything():
    shipped, result = gate_python_file("x.py", "def broken(:\n", quality="off")
    assert result.passed and result.method == "off"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_builder_parser(sub)
    return parser.parse_args(argv)


def test_cli_parser_registers():
    args = _parse(
        [
            "build",
            "a notes app",
            "--stack",
            "static",
            "--name",
            "n",
            "--export",
            "--quality",
            "static",
        ]
    )
    assert args.command == "build"
    assert args.description == "a notes app"
    assert args.stack == "static"
    assert args.export is True
    assert args.quality == "static"


def test_cli_preview_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    args = _parse(["build", "a notes app", "--preview"])
    assert cmd_build(args) == 0
    out = capsys.readouterr().out
    assert "PLAN" in out and "nothing was written" in out
    assert list(tmp_path.iterdir()) == []


def test_cli_rejects_unknown_stack():
    with pytest.raises(SystemExit):
        _parse(["build", "x", "--stack", "rails"])
