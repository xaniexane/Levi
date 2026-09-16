"""Hermetic tests for the WriteBuild fusion pipeline.

Pure file ops on tmp_path; no HOME writes, no network, no randomness.
"""

from levi.factory.writebuild import (
    WriteBuildPipeline,
    analyze_text,
    fix_pass,
    format_pass,
    scaffold_module,
)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_analyze_text_stats():
    a = analyze_text("def f():\n    pass\n# TODO: x\n")
    assert a["lines"] == 4
    assert a["non_empty"] == 3
    assert a["looks_python"] is True
    assert a["todo_count"] == 1


def test_format_pass_whitespace_only():
    out = format_pass("x = 1   \n\n\n\ny = 2\n")
    assert "   \n" not in out
    assert "\n\n\n\n" not in out
    assert "x = 1\n" in out


def test_fix_pass_none_style_and_tabs():
    out = fix_pass("if x == None:\n\tpass\n")
    assert "x is None" in out
    assert "\t" not in out


def test_scaffold_module_shape():
    code = scaffold_module("parse feeds", "feedparse")
    assert "feedparse" in code
    assert "parse feeds" in code
    assert 'if __name__ == "__main__":' in code
    assert "NotImplementedError" in code


def test_scaffold_module_sanitizes_name():
    code = scaffold_module("x", "../../evil")
    assert ".." not in code.split('"""')[0]


def test_run_full_pipeline_report_only(tmp_path):
    p = _write(tmp_path, "m.py", "def f():\n\tif x == None:\n\t\tpass   \n")
    pipe = WriteBuildPipeline()
    rep = pipe.run(p, steps=("analyze", "format", "fix", "sandbox"))
    assert rep.error == ""
    assert [s["name"] for s in rep.steps] == ["analyze", "format", "fix", "sandbox"]
    assert all(s["ok"] for s in rep.steps)
    assert "x is None" in rep.output
    assert rep.applied is False
    # source file untouched without confirmation
    assert "\t" in p.read_text()


def test_run_apply_requires_confirmation(tmp_path):
    p = _write(tmp_path, "m.py", "x = 1   \n")
    pipe = WriteBuildPipeline()
    rep = pipe.run(p, steps=("format",), apply=True, confirmed=False)
    assert rep.applied is False
    assert "   \n" in p.read_text()  # unchanged
    assert any(s["name"] == "apply" and not s["ok"] for s in rep.steps)


def test_run_apply_with_confirmation(tmp_path):
    p = _write(tmp_path, "m.py", "x = 1   \n")
    pipe = WriteBuildPipeline()
    rep = pipe.run(p, steps=("format",), apply=True, confirmed=True)
    assert rep.applied is True
    assert p.read_text() == "x = 1\n"


def test_run_empty_file_reports_error(tmp_path):
    p = _write(tmp_path, "empty.py", "   \n")
    rep = WriteBuildPipeline().run(p)
    assert "empty" in rep.error


def test_run_missing_file_reports_error(tmp_path):
    rep = WriteBuildPipeline().run(tmp_path / "nope.py")
    assert "cannot read" in rep.error


def test_run_unknown_step(tmp_path):
    p = _write(tmp_path, "m.py", "x = 1\n")
    rep = WriteBuildPipeline().run(p, steps=("analyze", "teleport"))
    bad = [s for s in rep.steps if s["name"] == "teleport"]
    assert bad and bad[0]["ok"] is False


def test_run_scaffold_step(tmp_path):
    p = _write(tmp_path, "m.py", "x = 1\n")
    rep = WriteBuildPipeline().run(p, steps=("scaffold",), goal="demo mod")
    sc = [s for s in rep.steps if s["name"] == "scaffold"][0]
    assert sc["ok"] is True
    assert "demo mod" in sc["module"]


def test_format_report(tmp_path):
    p = _write(tmp_path, "m.py", "x = 1\n")
    pipe = WriteBuildPipeline()
    rep = pipe.run(p)
    text = pipe.format_report(rep)
    assert "WriteBuild Fusion" in text
    assert "analyze" in text


def test_format_report_no_report():
    assert "No WriteBuild report" in WriteBuildPipeline().format_report(None)
