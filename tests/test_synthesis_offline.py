"""Offline-first, proved: the synthesis path touches no network.

``OfflineGuard`` disables socket creation for a block; status + ask must
complete inside it. ``assert_no_network_imports`` pins the synthesis
package's own sources to zero network-library imports.
"""

import importlib.util
import socket

import pytest

from levi.synthesis import mind
from levi.synthesis import offline as offline_mod
from levi.synthesis import status as status_mod


def test_guard_blocks_socket_creation():
    real_socket = socket.socket
    real_create = socket.create_connection
    real_gai = socket.getaddrinfo
    with offline_mod.OfflineGuard():
        with pytest.raises(offline_mod.OfflineViolation):
            socket.socket()
        with pytest.raises(offline_mod.OfflineViolation):
            socket.create_connection(("example.com", 80))
        with pytest.raises(offline_mod.OfflineViolation):
            socket.getaddrinfo("example.com", 80)
    assert socket.socket is real_socket
    assert socket.create_connection is real_create
    assert socket.getaddrinfo is real_gai


def test_guard_restores_on_error():
    real_socket = socket.socket
    with pytest.raises(RuntimeError, match="boom"):
        with offline_mod.OfflineGuard():
            raise RuntimeError("boom")
    assert socket.socket is real_socket


def test_no_network_imports_in_synthesis_package():
    assert offline_mod.assert_no_network_imports() == []


def test_ask_and_status_complete_inside_guard():
    with offline_mod.OfflineGuard():
        out = mind.ask(
            "offline self-check: state your substrate", brain_policy="rules-only"
        )
        assert out["substrate"] == "rules-engine"
        st = status_mod.collect_status()
        assert "brain" in st and "finance" in st


def test_prove_offline_command(tmp_path, monkeypatch, capsys):
    from levi.synthesis.cli import cmd_synthesis
    import argparse
    from levi.synthesis.cli import add_synthesis_arguments

    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    parser = argparse.ArgumentParser(prog="levi synthesis")
    add_synthesis_arguments(parser)
    ns = parser.parse_args(["prove-offline"])
    assert cmd_synthesis(ns) == 0
    out = capsys.readouterr().out
    assert "OFFLINE PROOF PASSED" in out


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None, reason="torch not installed"
)
def test_brain_path_inside_guard_when_torch_present():
    # When torch IS available the auto policy must still report honestly
    # under the guard — hybrid or rules-only, never an exception.
    with offline_mod.OfflineGuard():
        out = mind.ask("offline self-check", brain_policy="auto")
    assert out["substrate"] in ("rules-engine", "rules-engine + native-brain")
    assert out["limits"]
