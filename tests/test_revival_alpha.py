"""Tests for Alpha's completed generator registry: automation + LEVI skill.

Covers the two new generators, every generated Python file compiling,
invalid-blueprint refusal, and generator failure isolation. Does not
touch tests/test_revival_omega.py.
"""

import json
import sys

import pytest

from levi.revival.omega import blueprint as bp
from levi.revival.omega import generators as gen


def _py_files(result):
    return {p: c for p, c in result["files"].items() if p.endswith(".py")}


def test_registry_has_six_generators():
    assert set(gen.registered()) == {
        "webpage",
        "cli",
        "api",
        "mcp_server",
        "automation",
        "skill",
    }


def test_automation_blueprint_compiles_to_workflow_and_readme():
    b = bp.build_blueprint(
        "automation that backs up my notes nightly", product_types=["automation"]
    )
    assert b["product_types"] == ["automation"]
    assert b["name"].endswith("-flow")
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    assert f"{b['name']}/workflow.py" in result["files"]
    assert f"{b['name']}/README.md" in result["files"]
    src = result["files"][f"{b['name']}/workflow.py"]
    assert "WORKFLOW" in src
    assert "'trigger'" in src and "'steps'" in src and "'receipt'" in src
    compile(src, "<generated-workflow>", "exec")


def test_generated_workflow_actually_runs(tmp_path, monkeypatch):
    b = bp.build_blueprint("nightly backup automation", product_types=["automation"])
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    src = result["files"][f"{b['name']}/workflow.py"]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["workflow.py"])
    with pytest.raises(SystemExit) as exc:
        exec(compile(src, "workflow.py", "exec"), {"__name__": "__main__"})
    assert exc.value.code == 0
    assert (tmp_path / f"{b['name']}.receipts.jsonl").exists()
    assert (tmp_path / f"{b['name']}.ran.txt").exists()


def test_skill_blueprint_compiles_to_skill_md_and_py():
    b = bp.build_blueprint(
        "a skill for summarizing meeting notes", product_types=["skill"]
    )
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    assert f"{b['name']}/SKILL.md" in result["files"]
    assert f"{b['name']}/skill.py" in result["files"]
    md = result["files"][f"{b['name']}/SKILL.md"]
    # LEVI skill format: YAML frontmatter + Purpose/Steps/Operating rules body
    assert md.startswith("---\n")
    assert "skill_id:" in md and 'risk: "info"' in md
    assert "## Purpose" in md and "## Steps" in md
    assert "## Operating rules" in md
    compile(result["files"][f"{b['name']}/skill.py"], "<generated-skill>", "exec")


def test_generated_skill_runs(tmp_path, monkeypatch, capsys):
    b = bp.build_blueprint("skill that triages my inbox", product_types=["skill"])
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    src = result["files"][f"{b['name']}/skill.py"]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["skill.py", "triage inbox", "--json"])
    with pytest.raises(SystemExit) as exc:
        exec(compile(src, "skill.py", "exec"), {"__name__": "__main__"})
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill"] == b["name"] and payload["ok"] is True


def test_skill_is_detection_fallback():
    b = bp.build_blueprint("something utterly unrelated xyzzy")
    assert b["product_types"] == ["skill"]
    result = gen.compile_blueprint(b)
    assert result["ok"], result["errors"]
    assert f"{b['name']}/SKILL.md" in result["files"]


def test_all_generated_python_compiles():
    cases = [
        ("landing page for my bakery", ["webpage"]),
        ("command line tool to rename photos", ["cli"]),
        ("rest api backend for notes", ["api"]),
        ("mcp server exposing my notes", ["mcp_server"]),
        ("nightly backup automation", ["automation"]),
        ("skill that triages my inbox", ["skill"]),
    ]
    for prompt, ptypes in cases:
        b = bp.build_blueprint(prompt, product_types=ptypes)
        result = gen.compile_blueprint(b)
        assert result["ok"], result["errors"]
        for path, src in _py_files(result).items():
            compile(src, path, "exec")  # raises SyntaxError on failure


def test_invalid_blueprint_still_refused():
    result = gen.compile_blueprint({"name": "broken"})
    assert not result["ok"] and result["files"] == {}


def test_generator_failure_isolation():
    def boom(blueprint):
        raise RuntimeError("deliberate failure")

    gen.register(
        gen.Generator(
            name="boom",
            title="boom",
            description="boom",
            product_types=["skill"],
            generate=boom,
        )
    )
    try:
        b = bp.build_blueprint("skill that triages my inbox", product_types=["skill"])
        result = gen.compile_blueprint(b)
        assert any("boom" in e for e in result["errors"])
        # the real skill generator still ran despite the failure
        assert f"{b['name']}/SKILL.md" in result["files"]
        assert f"{b['name']}/skill.py" in result["files"]
    finally:
        gen.unregister("boom")
