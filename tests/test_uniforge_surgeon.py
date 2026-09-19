"""UniForge surgeon tests: parity with the Omega Triple Threat Elite plugin.

Every quick-cleanup case below is hand-computed from the plugin's
``surgeonCleanup`` JavaScript semantics (``~/workspace/user/files/main.js``):
trailing-whitespace per line, tabs->4 spaces, 4+ newlines collapsed to 3,
``== None``/``!= None`` rewrites, trailing-newline preservation.
"""

import datetime
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from levi.uniforge.surgeon import (  # noqa: E402
    diagnose,
    operate,
    quick_cleanup,
    stamp_header,
    surgeon_file,
)


def _zero():
    return {
        "trailing_whitespace": 0,
        "tabs": 0,
        "blank_lines": 0,
        "eq_none": 0,
        "ne_none": 0,
    }


def test_trailing_whitespace_per_line():
    text, fixes = quick_cleanup("x = 1  \ny = 2\t\n")
    assert text == "x = 1\ny = 2\n"
    assert fixes["trailing_whitespace"] == 2
    assert fixes["tabs"] == 0  # tab was trailing, already stripped


def test_tabs_to_spaces():
    text, fixes = quick_cleanup("a\tb\n")
    assert text == "a    b\n"
    assert fixes["tabs"] == 1


def test_blank_line_collapse():
    text, fixes = quick_cleanup("a\n\n\n\nb\n")
    assert text == "a\n\n\nb\n"
    assert fixes["blank_lines"] == 1


def test_five_blank_lines_collapse_once():
    text, fixes = quick_cleanup("a\n\n\n\n\nb\n")
    assert text == "a\n\n\nb\n"
    assert fixes["blank_lines"] == 1


def test_eq_none_rewrite():
    text, fixes = quick_cleanup("if x == None:\n")
    assert text == "if x is None:\n"
    assert fixes["eq_none"] == 1


def test_ne_none_rewrite():
    text, fixes = quick_cleanup("if x != None:\n")
    assert text == "if x is not None:\n"
    assert fixes["ne_none"] == 1


def test_none_rewrites_combined():
    text, fixes = quick_cleanup("if x == None and y != None:\n")
    assert text == "if x is None and y is not None:\n"
    assert fixes["eq_none"] == 1
    assert fixes["ne_none"] == 1


def test_none_word_boundary():
    # "Nonexistent" must not be rewritten; "None" mid-word stays.
    text, fixes = quick_cleanup("Nonexistent = 1\n")
    assert text == "Nonexistent = 1\n"
    assert fixes == _zero()


def test_clean_file_zero_fixes():
    text, fixes = quick_cleanup("x = 1\n")
    assert text == "x = 1\n"
    assert fixes == _zero()


def test_trailing_newline_preserved():
    text, fixes = quick_cleanup("a\n")
    assert text == "a\n"
    text, fixes = quick_cleanup("a")
    assert text == "a"


def test_stamp_header_fresh():
    year = datetime.date.today().year
    out = stamp_header("x = 1\n", "Chauncey")
    assert out == (
        "# CLOSED SOURCE – All Rights Reserved\n"
        "# Copyright (c) %d Chauncey\n"
        "# Confidential property.\n\nx = 1\n" % year
    )


def test_stamp_header_replaces_existing():
    year = datetime.date.today().year
    out = stamp_header("# Copyright (c) 2020 Someone\nx = 1\n", "Chauncey")
    assert out.startswith("# CLOSED SOURCE – All Rights Reserved\n")
    assert "# Copyright (c) %d Chauncey\n" % year in out
    assert "2020 Someone" not in out
    assert out.endswith("x = 1\n")


def test_stamp_header_strips_leading_blank_lines():
    out = stamp_header("\n\nx = 1\n", "Chauncey")
    assert out.endswith("\n\nx = 1\n")
    assert not out.split("property.\n\n", 1)[1].startswith("\n")


def test_stamp_header_keeps_non_copyright_comments():
    out = stamp_header("# MIT License\nx = 1\n", "Chauncey")
    assert "# MIT License\n" in out


def test_diagnose_finds_cleanup():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("x = 1  \n")
        path = fh.name
    try:
        findings = diagnose(path)
        assert any(f.kind == "cleanup" for f in findings)
        assert not any(f.kind == "syntax" for f in findings)
    finally:
        os.unlink(path)


def test_diagnose_finds_syntax_error():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("def broken(:\n")
        path = fh.name
    try:
        findings = diagnose(path)
        assert any(f.kind == "syntax" for f in findings)
        assert findings[0].line == 1 or any(
            f.kind == "syntax" and f.line == 1 for f in findings
        )
    finally:
        os.unlink(path)


def test_diagnose_clean_file():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("x = 1\n")
        path = fh.name
    try:
        assert diagnose(path) == []
    finally:
        os.unlink(path)


def test_surgeon_file_dry_run_changes_nothing():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("x = 1  \n")
        path = fh.name
    try:
        receipt = surgeon_file(path)
        assert receipt["decision"] == "dry-run"
        assert receipt["total_fixes"] == 1
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == "x = 1  \n"
    finally:
        os.unlink(path)


def test_surgeon_file_apply_writes():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("x = 1  \nif x == None:\n")
        path = fh.name
    try:
        receipt = surgeon_file(path, apply=True)
        assert receipt["decision"] == "executed"
        assert receipt["total_fixes"] == 2
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == "x = 1\nif x is None:\n"
    finally:
        os.unlink(path)


def test_operate_full_cycle_verified():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("x = 1  \nif x == None:\n    pass\n")
        path = fh.name
    try:
        dry = operate(path)
        assert dry["decision"] == "dry-run"
        assert dry["findings_before"]
        assert not dry["verified"]
        live = operate(path, apply=True)
        assert live["decision"] == "executed"
        assert live["verified"] is True
        assert live["findings_after"] == []
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == "x = 1\nif x is None:\n    pass\n"
    finally:
        os.unlink(path)


def test_operate_syntax_error_not_verified():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("def broken(:\n")
        path = fh.name
    try:
        receipt = operate(path, apply=True)
        assert receipt["decision"] == "executed-with-findings"
        assert receipt["verified"] is False
        assert any(f["kind"] == "syntax" for f in receipt["findings_after"])
    finally:
        os.unlink(path)


def test_surgeon_file_missing_raises():
    with pytest.raises((FileNotFoundError, OSError)):
        surgeon_file("/tmp/does-not-exist-uniforge-test.py")
