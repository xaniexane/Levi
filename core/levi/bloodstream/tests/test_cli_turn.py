"""CLI smoke for ``levi turn`` — in-process, hermetic.

HOME is redirected to a tmp dir so the turn's memory/traces/factory
writes never touch the real user home.
"""
import io
import os
from contextlib import redirect_stdout

import pytest

from levi.cli.main import main


@pytest.fixture
def clean_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    return home


def _run(argv):
    import sys
    old = sys.argv
    sys.argv = ["levi", *argv]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            main()
        return buf.getvalue()
    finally:
        sys.argv = old


def test_turn_prints_reply_and_receipt(clean_home):
    out = _run(["turn", "what is recursion in one sentence"])
    assert "[model]" in out
    assert "receipt" in out and "risk 1" in out
    assert (clean_home / ".levi" / "traces").exists()


def test_turn_factory_dry_run_receipts_without_executing(clean_home):
    out = _run(["turn", "--yes", "--dry-run", "build me a todo app"])
    assert "[factory]" in out
    assert "risk 2" in out
    assert "dry-run" in out
    # dry run must not create a factory project record
    factory_dir = clean_home / ".levi" / "factory"
    projects = list(factory_dir.glob("*.json")) if factory_dir.exists() else []
    assert projects == []


def test_turn_requires_text(clean_home):
    out = _run(["turn"])
    assert "Usage: levi turn" in out
