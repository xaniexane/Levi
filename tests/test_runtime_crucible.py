"""Crucible hardening tests (hermetic, stdlib-only).

Covers the path-traversal and input-validation fixes in
``levi.runtime.crucible``: caller-controlled file names must stay inside
the chamber, and oversized / non-string inputs are refused before any
disk write.
"""

from __future__ import annotations

import pytest

from levi.runtime import crucible as crucible_mod
from levi.runtime.crucible import Crucible


@pytest.fixture()
def chamber_root(tmp_path, monkeypatch):
    root = tmp_path / "crucible"
    monkeypatch.setattr(crucible_mod, "DEFAULT_ROOT", root)
    return root


def test_file_smoke_traversal_is_rejected(chamber_root):
    c = Crucible()
    for evil in ("../escape.txt", "../../etc/evil", "sub/../../x", ".."):
        r = c.file_smoke(evil, "x = 1")
        assert r.ok is False
        assert "chamber" in r.detail
    # Nothing escaped the crucible root: no files outside it were created.
    assert list(chamber_root.parent.glob("escape.txt")) == []
    assert list(chamber_root.parent.glob("etc")) == []


def test_file_smoke_absolute_path_is_rejected(chamber_root):
    c = Crucible()
    r = c.file_smoke("/tmp/absolutely_not.txt", "x = 1")
    assert r.ok is False
    assert "relative" in r.detail


def test_file_smoke_valid_relative_path_still_works(chamber_root):
    c = Crucible()
    r = c.file_smoke("nested/dir/probe.py", "x = 1\n")
    assert r.ok is True
    written = list(chamber_root.rglob("probe.py"))
    assert len(written) == 1
    assert written[0].read_text() == "x = 1\n"


def test_file_smoke_rejects_bad_inputs(chamber_root):
    c = Crucible()
    for bad in ("", "   ", None, 123):
        r = c.file_smoke(bad, "x = 1")  # type: ignore[arg-type]
        assert r.ok is False
    r = c.file_smoke("ok.py", 123)  # type: ignore[arg-type]
    assert r.ok is False and "string" in r.detail
    r = c.file_smoke("big.py", "x" * (crucible_mod._MAX_SMOKE_CONTENT + 1))
    assert r.ok is False and "exceeds" in r.detail


def test_syntax_probe_rejects_bad_inputs(chamber_root):
    c = Crucible()
    r = c.syntax_probe("def f(:")  # genuinely invalid syntax
    assert r.ok is False and "SyntaxError" in r.detail
    r = c.syntax_probe(123)  # type: ignore[arg-type]
    assert r.ok is False and "string" in r.detail
    r = c.syntax_probe("x" * (crucible_mod._MAX_SMOKE_CONTENT + 1))
    assert r.ok is False and "exceeds" in r.detail
    r = c.syntax_probe("x = 1")
    assert r.ok is True
