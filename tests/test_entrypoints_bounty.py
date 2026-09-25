"""Entrypoint tests: python -m levi.bounty (hermetic, no network)."""

import pytest

from levi.bounty.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_scope_list_empty(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["scope", "list"]) == 0
    assert "No scopes enrolled" in capsys.readouterr().out


def test_scope_add_invalid_domain_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["scope", "add", "not a domain!!"]) == 1
    assert "refused" in capsys.readouterr().err


def test_scope_add_and_remove_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["scope", "add", "example.com"]) == 0
    assert main(["scope", "list"]) == 0
    assert "example.com" in capsys.readouterr().out
    assert main(["scope", "remove", "example.com"]) == 0


def test_findings_empty(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["findings"]) == 0
    assert "No findings stored" in capsys.readouterr().out


def test_recon_outside_scope_refused(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["recon", "evil.example"]) == 1
    assert "SCOPE REFUSED" in capsys.readouterr().err


def test_recon_bad_ports_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["recon", "example.com", "--ports", "abc"]) == 2
    assert main(["recon", "example.com", "--ports", "99999"]) == 2


def test_unknown_subcommand_fails_closed():
    with pytest.raises(SystemExit) as e:
        main(["nope"])
    assert e.value.code != 0
