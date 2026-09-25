"""Hermetic tests for ``levi.sandbox`` (Linux host sandbox).

No real bwrap/unshare/subprocess execution: ``shutil.which`` is stubbed,
``subprocess.run`` is monkeypatched, and command construction is asserted on
the argv lists. These tests pin the honesty contract: backend selection order,
no silent downgrades, isolation-level reporting, and the degraded-backend
acknowledgement gate.
"""

from __future__ import annotations

import argparse

import pytest

from levi.sandbox import backends as B
from levi.sandbox import runner as R
from levi.sandbox.cli import cmd_sandbox, register_sandbox


def _which(mapping):
    def which(name):
        return mapping.get(name)

    return which


ALL = {"bwrap": "/usr/bin/bwrap", "unshare": "/usr/bin/unshare"}
NO_BWRAP = {"unshare": "/usr/bin/unshare"}
NOTHING = {}


# --- backend selection -----------------------------------------------------


def test_select_prefers_bubblewrap_when_present():
    spec = B.select_backend(which=_which(ALL))
    assert spec.name == "bubblewrap"
    assert spec.isolation_level == B.STRONG
    assert spec.available


def test_select_falls_back_to_unshare():
    spec = B.select_backend(which=_which(NO_BWRAP))
    assert spec.name == "unshare"
    assert spec.isolation_level == B.BASIC


def test_select_falls_back_to_subprocess_when_nothing_present():
    spec = B.select_backend(which=_which(NOTHING))
    assert spec.name == "subprocess"
    assert spec.isolation_level == B.NONE
    # subprocess is always available: the chain never dead-ends
    assert spec.available


def test_forced_unavailable_backend_raises_no_silent_downgrade():
    with pytest.raises(ValueError, match="not found"):
        B.select_backend("bubblewrap", which=_which(NOTHING))
    # forcing subprocess explicitly is allowed (CLI still gates it)
    spec = B.select_backend("subprocess", which=_which(ALL))
    assert spec.name == "subprocess"


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="unknown backend"):
        B.select_backend("docker", which=_which(ALL))


def test_describe_reports_availability_in_preference_order():
    specs = B.describe_backends(which=_which(NO_BWRAP))
    assert [s.name for s in specs] == ["bubblewrap", "unshare", "subprocess"]
    assert [s.available for s in specs] == [False, True, True]


# --- isolation honesty -----------------------------------------------------


def test_every_backend_has_nonempty_contract():
    for spec in B.describe_backends(which=_which(ALL)):
        assert spec.isolation_level in (B.STRONG, B.BASIC, B.NONE)
        assert spec.guarantees, spec.name
        assert spec.limitations, spec.name


def test_subprocess_never_claims_isolation():
    spec = B.select_backend("subprocess", which=_which(ALL))
    assert spec.isolation_level == B.NONE
    joined = " ".join(spec.guarantees + spec.limitations).lower()
    assert "no isolation" in joined


def test_bubblewrap_limitations_mention_kernel_sharing():
    spec = B.select_backend("bubblewrap", which=_which(ALL))
    joined = " ".join(spec.limitations).lower()
    assert "kernel" in joined


def test_unshare_limitations_admit_writable_filesystem():
    spec = B.select_backend("unshare", which=_which(ALL))
    joined = " ".join(spec.limitations).lower()
    assert "writable" in joined
    assert "network" in joined


def test_isolation_report_lists_both_sides():
    spec = B.select_backend("bubblewrap", which=_which(ALL))
    report = B.isolation_report(spec)
    assert "guarantees:" in report
    assert "limitations:" in report
    assert "strong" in report


# --- argv construction (no execution) --------------------------------------


def test_bwrap_argv_defaults_to_no_network():
    spec = B.select_backend("bubblewrap", which=_which(ALL))
    argv = R.build_argv(spec, ["pytest", "-x"])
    assert argv[0] == "bwrap"
    assert "--unshare-net" in argv  # network OFF by default
    assert "--ro-bind" in argv and "/" in argv
    assert "--die-with-parent" in argv
    assert argv[-2:] == ["pytest", "-x"]


def test_bwrap_argv_with_net_omits_netns_flag():
    spec = B.select_backend("bubblewrap", which=_which(ALL))
    argv = R.build_argv(spec, ["curl", "https://example.com"], net=True)
    assert "--unshare-net" not in argv


def test_unshare_argv_is_minimal():
    spec = B.select_backend("unshare", which=_which(ALL))
    argv = R.build_argv(spec, ["make", "-C", "/tmp/x"])
    assert argv == ["unshare", "-Ur", "--", "make", "-C", "/tmp/x"]


def test_subprocess_argv_is_bare_command():
    spec = B.select_backend("subprocess", which=_which(ALL))
    argv = R.build_argv(spec, ["echo", "hi"])
    assert argv == ["echo", "hi"]


def test_build_argv_rejects_empty_command():
    spec = B.select_backend(which=_which(ALL))
    with pytest.raises(ValueError, match="no command"):
        R.build_argv(spec, [])


# --- run_command gating (subprocess.run mocked) -----------------------------


def test_run_command_degraded_backend_requires_ack(monkeypatch):
    monkeypatch.setattr(B.shutil, "which", _which(NOTHING))
    with pytest.raises(PermissionError, match="--i-understand"):
        R.run_command(["echo", "hi"])


def test_run_command_degraded_with_ack_executes(monkeypatch):
    monkeypatch.setattr(B.shutil, "which", _which(NOTHING))
    calls = []

    class _Proc:
        returncode = 3

    def fake_run(argv, env=None):
        calls.append((argv, env))
        return _Proc()

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    result = R.run_command(["echo", "hi"], allow_degraded=True)
    assert result.backend == "subprocess"
    assert result.isolation_level == B.NONE
    assert result.returncode == 3  # child exit code propagates
    assert result.degraded_acknowledged is True
    assert calls and calls[0][0] == ["echo", "hi"]


def test_run_command_uses_strongest_backend(monkeypatch):
    monkeypatch.setattr(B.shutil, "which", _which(ALL))
    seen = {}

    class _Proc:
        returncode = 0

    def fake_run(argv, env=None):
        seen["argv"] = argv
        return _Proc()

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    result = R.run_command(["true"])
    assert result.backend == "bubblewrap"
    assert result.isolation_level == B.STRONG
    assert seen["argv"][0] == "bwrap"


# --- CLI wiring ------------------------------------------------------------


def _sandbox_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_sandbox(sub)
    return parser


def test_cli_registers_sandbox_subcommands():
    parser = _sandbox_parser()
    args = parser.parse_args(["sandbox", "info"])
    assert args.sandbox_cmd == "info"
    args = parser.parse_args(["sandbox", "run", "--net", "--", "echo", "hi"])
    assert args.sandbox_cmd == "run"
    assert args.net is True
    assert args.cmd == ["--", "echo", "hi"]


def test_cli_sandbox_info_runs_readonly(capsys):
    parser = _sandbox_parser()
    cmd_sandbox(parser.parse_args(["sandbox", "info"]))
    out = capsys.readouterr().out
    assert "bubblewrap" in out and "unshare" in out and "subprocess" in out
    assert "isolation level" in out


def test_cli_run_with_no_command_exits_2_without_executing(capsys, monkeypatch):
    parser = _sandbox_parser()
    monkeypatch.setattr(B.shutil, "which", _which(ALL))
    with pytest.raises(SystemExit) as exc:
        cmd_sandbox(parser.parse_args(["sandbox", "run", "--"]))
    assert exc.value.code == 2


def test_cli_run_degraded_without_ack_refuses(capsys, monkeypatch):
    parser = _sandbox_parser()
    monkeypatch.setattr(B.shutil, "which", _which(NOTHING))
    with pytest.raises(SystemExit) as exc:
        cmd_sandbox(parser.parse_args(["sandbox", "run", "--", "echo", "hi"]))
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "DEGRADED SANDBOX" in err


def test_cli_unknown_action_exits_2(capsys):
    # Bare `levi sandbox` (no subcommand) is the legacy syntax+smoke command
    # owned by another region — it delegates, it does not exit 2.
    import levi.cli.main as main_mod

    called = {}

    def fake_legacy(args):
        called["args"] = args

    import unittest.mock as mock

    with mock.patch.object(main_mod, "cmd_sandbox", fake_legacy):
        parser = _sandbox_parser()
        cmd_sandbox(parser.parse_args(["sandbox"]))
    assert "args" in called


def test_register_attaches_to_preexisting_sandbox_parser():
    # Mirrors core/levi/cli/main.py: a legacy `sandbox` parser (syntax+smoke,
    # `levi sandbox --path`) is registered by another region first. Our
    # registration must attach `run`/`info` to it, not raise.
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    legacy = sub.add_parser("sandbox", help="legacy syntax+smoke")
    legacy.add_argument("--path", default=".")
    register_sandbox(sub)  # must not raise ArgumentError
    args = parser.parse_args(["sandbox", "info"])
    assert args.sandbox_cmd == "info"
    args = parser.parse_args(["sandbox", "run", "--", "echo", "hi"])
    assert args.sandbox_cmd == "run"
    # legacy invocation still parses
    args = parser.parse_args(["sandbox", "--path", "."])
    assert args.sandbox_cmd is None
    assert args.path == "."
