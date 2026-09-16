"""Entrypoint tests: python -m levi.finance (hermetic; paper-only, no network).

Market-data subcommands (quote/indicators/signal) need Stooq and are
not exercised here — only the offline paper ledger paths.
"""

import pytest

from levi.finance import portfolio as _portfolio
from levi.finance.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    # NOTE: _portfolio.DEFAULT_PATH is bound at import time from Path.home(),
    # so patching HOME alone does not move it. Point it at the tmp dir so
    # these tests never touch the real ~/.levi ledger.
    monkeypatch.setattr(
        _portfolio,
        "DEFAULT_PATH",
        tmp_path / ".levi" / "finance" / "portfolio.json",
    )


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_portfolio_and_deposit(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["portfolio"]) == 0
    assert "Paper portfolio" in capsys.readouterr().out
    assert main(["deposit", "500"]) == 0
    assert "PAPER portfolio" in capsys.readouterr().out
    assert main(["portfolio"]) == 0
    assert "$500.00" in capsys.readouterr().out


def test_order_without_yes_refused(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        main(["order", "AAPL", "1", "--side", "buy"])
    assert e.value.code == 2
    assert "HITL" in capsys.readouterr().out


def test_live_refused(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        main(["order", "AAPL", "1", "--side", "buy", "--yes", "--live"])
    assert e.value.code == 2
    assert "structurally impossible" in capsys.readouterr().out


def test_no_action_shows_help(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main([]) == 2
