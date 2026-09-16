"""Hermetic tests for levi.sweeps — safe auto-fix, unsafe never auto-run.

All sweeps run against tmp dirs the tests create. The dangerous-root
guards ("/", real HOME, repo root) are exercised without touching them.
"""

import os
import time
from pathlib import Path

import pytest

from levi.sweeps.sweeps import (
    SweepRefusedError,
    SweepSpec,
    builtin_specs,
    list_specs,
    register,
    run_sweep,
    unregister,
)


def _age(path: Path, days: float) -> None:
    old = time.time() - days * 86400.0
    os.utime(path, (old, old))


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "sweep-target"
    root.mkdir()
    return root


def test_builtins_registered():
    ids = {s.id for s in builtin_specs()}
    assert {"stale-pycache", "empty-dirs", "stale-tmp-files"} <= ids
    assert all(s.safe for s in builtin_specs())


def test_custom_spec_appears_in_registry(tree):
    register(
        SweepSpec(
            id="test-listed",
            area="demo",
            description="d",
            check=lambda r, m: [],
            fix=lambda r, i: True,
            safe=True,
        )
    )
    try:
        assert "test-listed" in {s.id for s in list_specs()}
    finally:
        unregister("test-listed")
    assert "test-listed" not in {s.id for s in list_specs()}


def test_stale_pycache_fixed_old_kept_fresh(tree):
    stale = tree / "pkg" / "__pycache__"
    stale.mkdir(parents=True)
    (stale / "mod.pyc").write_text("x")
    _age(stale, 10)
    _age(stale / "mod.pyc", 10)
    fresh = tree / "other" / "__pycache__"
    fresh.mkdir(parents=True)
    report = run_sweep(tree, max_age_days=7)
    assert not stale.exists()
    assert fresh.exists()  # fresh bytecode survives
    assert any("__pycache__" in f for f in report.fixed)


def test_empty_dirs_removed_root_never(tree):
    empty = tree / "a" / "b" / "c"
    empty.mkdir(parents=True)
    nonempty = tree / "data"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("data")
    run_sweep(tree)
    assert not (tree / "a").exists()
    assert (nonempty / "keep.txt").exists()
    assert tree.exists()  # the root itself is never removed


def test_stale_tmp_files_removed_fresh_kept(tree):
    old_tmp = tree / "scratch.tmp"
    old_tmp.write_text("junk")
    _age(old_tmp, 10)
    fresh_tmp = tree / "active.tmp"
    fresh_tmp.write_text("work")
    old_bak = tree / "notes.bak"
    old_bak.write_text("junk")
    _age(old_bak, 10)
    real = tree / "report.txt"
    real.write_text("important")
    _age(real, 30)  # old, but not a tmp file — must survive
    run_sweep(tree, max_age_days=7)
    assert not old_tmp.exists()
    assert not old_bak.exists()
    assert fresh_tmp.exists()
    assert real.exists()


def test_unsafe_spec_reported_never_run(tree):
    ran = []

    def check(root, max_age_days):
        return ["would-delete-everything"]

    def fix(root, issue):
        ran.append(issue)
        return True

    spec = SweepSpec(
        id="test-unsafe-demo",
        area="demo",
        description="unsafe demo",
        check=check,
        fix=fix,
        safe=False,
    )
    register(spec)
    try:
        report = run_sweep(tree, only=["test-unsafe-demo"])
    finally:
        unregister("test-unsafe-demo")
    assert ran == []  # fix never executed
    assert len(report.skipped_unsafe) == 1
    assert report.skipped_unsafe[0]["id"] == "test-unsafe-demo"
    assert report.skipped_unsafe[0]["issues"] == ["would-delete-everything"]
    assert report.fixed == []


def test_safe_custom_spec_auto_fixes(tree):
    marker = tree / "stale-marker.txt"
    marker.write_text("x")

    def check(root, max_age_days):
        return ["stale-marker.txt"] if (root / "stale-marker.txt").exists() else []

    def fix(root, issue):
        (root / issue).unlink()
        return True

    register(
        SweepSpec(
            id="test-safe-demo",
            area="demo",
            description="safe demo",
            check=check,
            fix=fix,
            safe=True,
        )
    )
    try:
        report = run_sweep(tree, only=["test-safe-demo"])
    finally:
        unregister("test-safe-demo")
    assert not marker.exists()
    assert report.fixed == ["stale-marker.txt"]


def test_failed_fix_lands_in_remaining(tree):
    def check(root, max_age_days):
        return ["ghost.txt"]

    def fix(root, issue):
        return False  # could not repair

    register(
        SweepSpec(
            id="test-fail-demo",
            area="demo",
            description="failing demo",
            check=check,
            fix=fix,
            safe=True,
        )
    )
    try:
        report = run_sweep(tree, only=["test-fail-demo"])
    finally:
        unregister("test-fail-demo")
    assert report.remaining == ["ghost.txt"]
    assert report.fixed == []


def test_path_escape_is_refused_not_followed(tree):
    outside = tree.parent / "outside.txt"
    outside.write_text("do not touch")

    def check(root, max_age_days):
        return ["../outside.txt"]

    def fix(root, issue):  # pragma: no cover — must never be reached
        raise AssertionError("escape path must not reach fix")

    register(
        SweepSpec(
            id="test-escape-demo",
            area="demo",
            description="escape demo",
            check=check,
            fix=fix,
            safe=True,
        )
    )
    try:
        report = run_sweep(tree, only=["test-escape-demo"])
    finally:
        unregister("test-escape-demo")
    assert outside.exists()  # untouched
    assert any(e["issue"] == "../outside.txt" for e in report.errors)


def test_dangerous_roots_refused():
    with pytest.raises(SweepRefusedError):
        run_sweep("/")
    with pytest.raises(SweepRefusedError):
        run_sweep(Path.home())
    with pytest.raises(SweepRefusedError):
        run_sweep(Path(__file__).resolve().parents[1])  # the repo root


def test_missing_root_refused(tmp_path):
    with pytest.raises(SweepRefusedError):
        run_sweep(tmp_path / "does-not-exist")


def test_report_format(tree):
    report = run_sweep(tree)
    text = report.format()
    assert "fixed:" in text and "remaining:" in text
    assert "skipped_unsafe:" in text


def test_cli_smoke(tree, capsys):
    from levi.sweeps.__main__ import main

    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "stale-pycache" in out
    assert main(["run", str(tree), "--max-age-days", "7"]) == 0
    assert main(["run", "/"]) == 2  # refused, clean exit code
