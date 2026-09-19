"""Tests for levi.revival.omega.materialize — the safe Alpha artifact writer.

All disk work uses ``tmp_path``; nothing escapes the sandbox.
"""

import hashlib
import os

import pytest

from levi.revival.omega import materialize as mz

FILES = {
    "myapp/index.html": "<!DOCTYPE html>\n<html>\n</html>\n",
    "myapp/app.js": "console.log('hello');\n",
}


# ---- module identity ----


def test_origin():
    assert mz.ORIGIN == "levi-revival-omega/materialize"


# ---- preview: pure, no I/O ----


def test_preview_shows_paths_and_snippets():
    text = mz.preview(FILES)
    for path in FILES:
        assert path in text
    assert "<!DOCTYPE html>" in text
    assert "console.log('hello');" in text


def test_preview_truncates_to_max_lines():
    files = {"big.py": "\n".join(f"line {i}" for i in range(10))}
    text = mz.preview(files, max_lines=3)
    assert "line 0" in text and "line 2" in text
    assert "line 3" not in text
    assert "more line" in text


def test_preview_empty_files_is_gentle():
    assert "empty" in mz.preview({}).lower()


def test_preview_rejects_bad_input():
    with pytest.raises(ValueError):
        mz.preview(["not", "a", "dict"])
    with pytest.raises(ValueError):
        mz.preview({"ok.py": 123})


# ---- plan ----


def test_plan_marks_new_files_for_write(tmp_path):
    result = mz.plan(FILES, str(tmp_path))
    assert result["dest"] == os.path.realpath(str(tmp_path))
    actions = {e["path"]: e["action"] for e in result["entries"]}
    assert actions == {p: "write" for p in FILES}
    # every entry carries path/action/reason
    for entry in result["entries"]:
        assert set(entry) == {"path", "action", "reason"}


def test_plan_marks_existing_files_skip_existing(tmp_path):
    target = tmp_path / "myapp" / "app.js"
    target.parent.mkdir()
    target.write_text("already here")
    actions = {e["path"]: e["action"] for e in mz.plan(FILES, str(tmp_path))["entries"]}
    assert actions["myapp/app.js"] == "skip-existing"
    assert actions["myapp/index.html"] == "write"


def test_plan_blocks_traversal(tmp_path):
    nasty = {
        "../evil.py": "x",
        "/abs/path.py": "x",
        "sub/../../escape.py": "x",
        "ok.py": "x",
    }
    actions = {e["path"]: e["action"] for e in mz.plan(nasty, str(tmp_path))["entries"]}
    assert actions["../evil.py"] == "blocked"
    assert actions["/abs/path.py"] == "blocked"
    assert actions["sub/../../escape.py"] == "blocked"
    assert actions["ok.py"] == "write"


def test_plan_blocks_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "dest" / "link"
    link.parent.mkdir()
    link.symlink_to(outside, target_is_directory=True)
    actions = {
        e["path"]: e["action"]
        for e in mz.plan({"link/evil.py": "x"}, str(tmp_path / "dest"))["entries"]
    }
    assert actions["link/evil.py"] == "blocked"


def test_plan_honest_errors(tmp_path):
    with pytest.raises(ValueError):
        mz.plan({}, str(tmp_path))
    with pytest.raises(ValueError):
        mz.plan("nope", str(tmp_path))
    with pytest.raises(ValueError):
        mz.plan({"ok.py": {"not": "a string"}}, str(tmp_path))
    with pytest.raises(ValueError):
        mz.plan(FILES, None)
    with pytest.raises(ValueError):
        mz.plan(FILES, "")
    with pytest.raises(ValueError):
        mz.plan(FILES, str(tmp_path / "does-not-exist"))
    with pytest.raises(ValueError):
        mz.plan(FILES, str(tmp_path / "a-file-not-dir.txt"))
    (tmp_path / "a-file-not-dir.txt").write_text("x")
    with pytest.raises(ValueError):
        mz.plan(FILES, str(tmp_path / "a-file-not-dir.txt"))


# ---- write: the gated writer ----


def test_write_requires_explicit_approval(tmp_path):
    with pytest.raises(PermissionError):
        mz.write(FILES, str(tmp_path))
    with pytest.raises(PermissionError):
        mz.write(FILES, str(tmp_path), approve=False)


def test_write_receipt_verified_with_correct_sha256(tmp_path):
    receipt = mz.write(FILES, str(tmp_path), approve=True)
    assert receipt["verified"] is True
    assert receipt["mismatches"] == []
    assert receipt["skipped"] == []
    assert receipt["timestamp"]
    assert receipt["dest"] == os.path.realpath(str(tmp_path))
    by_path = {w["path"]: w for w in receipt["written"]}
    assert set(by_path) == set(FILES)
    for path, content in FILES.items():
        entry = by_path[path]
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert entry["sha256"] == expected
        assert entry["bytes"] == len(content.encode("utf-8"))
        assert (tmp_path / path).read_text() == content


def test_write_creates_nested_directories(tmp_path):
    mz.write({"deep/nested/file.txt": "hi\n"}, str(tmp_path), approve=True)
    assert (tmp_path / "deep" / "nested" / "file.txt").read_text() == "hi\n"


def test_write_refuses_overwrite_by_default(tmp_path):
    original = "original content\n"
    (tmp_path / "keep.py").write_text(original)
    receipt = mz.write({"keep.py": "new content\n"}, str(tmp_path), approve=True)
    assert receipt["verified"] is True
    assert receipt["written"] == []
    assert len(receipt["skipped"]) == 1
    assert receipt["skipped"][0]["path"] == "keep.py"
    assert "overwrite" in receipt["skipped"][0]["reason"]
    assert (tmp_path / "keep.py").read_text() == original


def test_write_overwrite_true_replaces(tmp_path):
    (tmp_path / "keep.py").write_text("original content\n")
    receipt = mz.write(
        {"keep.py": "new content\n"}, str(tmp_path), approve=True, overwrite=True
    )
    assert receipt["verified"] is True
    assert receipt["skipped"] == []
    assert (tmp_path / "keep.py").read_text() == "new content\n"


def test_write_blocks_traversal_and_writes_the_rest(tmp_path):
    receipt = mz.write(
        {"../evil.py": "x", "/abs.py": "y", "good.py": "z\n"},
        str(tmp_path),
        approve=True,
    )
    assert receipt["verified"] is True
    assert [w["path"] for w in receipt["written"]] == ["good.py"]
    assert [s["path"] for s in receipt["skipped"]] == ["../evil.py", "/abs.py"]
    assert all("blocked" in s["reason"] for s in receipt["skipped"])
    assert not (tmp_path.parent / "evil.py").exists()


def test_write_accepts_a_plan(tmp_path):
    result = mz.plan(FILES, str(tmp_path))
    receipt = mz.write(result, str(tmp_path), approve=True)
    assert receipt["verified"] is True
    assert {w["path"] for w in receipt["written"]} == set(FILES)


def test_write_honest_errors(tmp_path):
    with pytest.raises(ValueError):
        mz.write({}, str(tmp_path), approve=True)
    with pytest.raises(ValueError):
        mz.write(FILES, str(tmp_path / "missing"), approve=True)


# ---- verify: tamper detection ----


def test_verify_receipt_after_clean_write(tmp_path):
    receipt = mz.write(FILES, str(tmp_path), approve=True)
    result = mz.verify(receipt, str(tmp_path))
    assert result["verified"] is True
    assert result["checked"] == len(FILES)
    assert result["mismatches"] == []


def test_verify_detects_tamper_after_write(tmp_path):
    receipt = mz.write(FILES, str(tmp_path), approve=True)
    (tmp_path / "myapp" / "app.js").write_text("console.log('pwned');\n")
    result = mz.verify(receipt, str(tmp_path))
    assert result["verified"] is False
    mismatched = [m["path"] for m in result["mismatches"]]
    assert mismatched == ["myapp/app.js"]


def test_verify_detects_missing_file(tmp_path):
    receipt = mz.write(FILES, str(tmp_path), approve=True)
    os.remove(tmp_path / "myapp" / "index.html")
    result = mz.verify(receipt, str(tmp_path))
    assert result["verified"] is False
    assert result["mismatches"][0]["path"] == "myapp/index.html"
    assert "missing" in result["mismatches"][0]["reason"]


def test_verify_accepts_files_map(tmp_path):
    mz.write(FILES, str(tmp_path), approve=True)
    result = mz.verify(FILES, str(tmp_path))
    assert result["verified"] is True
    assert result["checked"] == len(FILES)


def test_verify_files_map_detects_tamper(tmp_path):
    result = mz.verify({"ghost.py": "print(1)\n"}, str(tmp_path))
    assert result["verified"] is False


def test_verify_rejects_unknown_dest(tmp_path):
    with pytest.raises(ValueError):
        mz.verify(FILES, str(tmp_path / "nope"))
