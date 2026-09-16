"""WSB finance CLI tests — hermetic, no network, no real HOME writes.

Exercises the WSB expansion surface of ``levi.cli.main.cmd_finance``
(``levi finance bet|bets|settle|leaderboard|copytrade|broker-link``,
``--wsb`` / ``--source`` flags) in-process. Market data comes from the
seeded synthetic provider (``--source synth``); bet/broker-link state is
redirected to temp dirs.

Run:  python3 tests/test_finance_cli_wsb.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_cli_wsb.py -q
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import levi.cli.main as cli_main  # noqa: E402
from levi.finance import bets as bets_mod  # noqa: E402
from levi.finance import brokerlink as brokerlink_mod  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


class _patch_bets_home:
    """Redirect the paper-bet ledger to a temp directory."""

    def __init__(self, tmp_path):
        self.tmp_path = Path(tmp_path)
        self._orig = bets_mod.DEFAULT_BETS_PATH

    def __enter__(self):
        bets_mod.DEFAULT_BETS_PATH = self.tmp_path / "bets.json"
        return self

    def __exit__(self, *exc):
        bets_mod.DEFAULT_BETS_PATH = self._orig
        return False


class _patch_brokerlink_home:
    """Redirect broker-link config + drafts to a temp directory."""

    def __init__(self, tmp_path):
        self.tmp_path = Path(tmp_path)
        self._orig_link = brokerlink_mod.DEFAULT_LINK_PATH
        self._orig_drafts = brokerlink_mod.DEFAULT_DRAFTS_PATH

    def __enter__(self):
        brokerlink_mod.DEFAULT_LINK_PATH = self.tmp_path / "broker_link.json"
        brokerlink_mod.DEFAULT_DRAFTS_PATH = self.tmp_path / "drafts.json"
        return self

    def __exit__(self, *exc):
        brokerlink_mod.DEFAULT_LINK_PATH = self._orig_link
        brokerlink_mod.DEFAULT_DRAFTS_PATH = self._orig_drafts
        return False


def _run_finance(tmpdir, action, **kwargs):
    """Run cmd_finance in-process; return (exit_code, stdout)."""
    args = argparse.Namespace(
        finance_action=action,
        sym=None,
        qty=None,
        side=None,
        yes=False,
        live=False,
        amount=None,
        json=False,
        source="stooq",
        wsb=False,
        trader=None,
        horizon=30,
        bet_id=None,
        price=None,
        paper_hands=False,
        follow=None,
        capital=10000.0,
        all=False,
        broker_link_action=None,
        platform=None,
    )
    for key, value in kwargs.items():
        setattr(args, key, value)
    buf = io.StringIO()
    with _patch_bets_home(tmpdir), _patch_brokerlink_home(tmpdir):
        try:
            with redirect_stdout(buf):
                cli_main.cmd_finance(args)
        except SystemExit as exc:
            return exc.code, buf.getvalue()
    return 0, buf.getvalue()


def _tmpdir():
    return tempfile.mkdtemp(prefix="levi-wsb-cli-")


@finance_test
def test_signal_wsb_synth():
    code, out = _run_finance(_tmpdir(), "signal", sym="SYNTH", source="synth", wsb=True)
    assert code == 0, out
    assert "DD: SYNTH" in out
    assert "PAPER ONLY" in out
    assert "not financial advice" in out


@finance_test
def test_quote_synth_and_wsb():
    code, out = _run_finance(_tmpdir(), "quote", sym="SYNTH", source="synth")
    assert code == 0, out
    assert "SYNTH" in out and "close $" in out
    assert "synthetic" in out
    code, out = _run_finance(_tmpdir(), "quote", sym="SYNTH", source="synth", wsb=True)
    assert code == 0, out
    assert "🦍" in out and "PAPER ONLY" in out


@finance_test
def test_indicators_synth():
    code, out = _run_finance(_tmpdir(), "indicators", sym="SYNTHBTC", source="synth")
    assert code == 0, out
    assert "SMA20" in out


@finance_test
def test_crypto_symbol_hints_binance():
    code, out = _run_finance(_tmpdir(), "quote", sym="BTCUSDT", source="stooq")
    assert code == 1, out
    assert "--source binance" in out
    assert "close $" not in out  # honest failure: no fabricated numbers


@finance_test
def test_synth_symbol_hints_synth():
    code, out = _run_finance(_tmpdir(), "quote", sym="SYNTH", source="stooq")
    assert code == 1, out
    assert "--source synth" in out


@finance_test
def test_bet_needs_yes():
    tmp = _tmpdir()
    code, out = _run_finance(
        tmp, "bet", sym="SYNTH", qty=10, side="buy", source="synth"
    )
    assert code == 2, out
    assert "NOT placed" in out
    assert not (Path(tmp) / "bets.json").exists()


@finance_test
def test_bet_place_settle_flow():
    tmp = _tmpdir()
    code, out = _run_finance(
        tmp,
        "bet",
        sym="SYNTH",
        qty=10,
        side="buy",
        source="synth",
        trader="diamond_ape",
        yes=True,
    )
    assert code == 0, out
    assert "PAPER YOLO TICKET" in out
    assert "diamond_ape" in out
    ledger = bets_mod.BetLedger.load(Path(tmp) / "bets.json")
    assert len(ledger.bets) == 1
    bet_id = ledger.bets[0].id
    entry = ledger.bets[0].entry_price

    code, out = _run_finance(tmp, "bets")
    assert code == 0, out
    assert bet_id in out
    assert "win rate: n/a" in out

    code, out = _run_finance(tmp, "settle", bet_id=bet_id, price=entry * 1.1)
    assert code == 0, out
    assert "SETTLED" in out
    assert "💎 DIAMOND" in out

    code, out = _run_finance(tmp, "bets", json=True)
    assert code == 0, out
    payload = json.loads(out)
    assert payload["win_rate"]["bets"] == 1
    assert payload["win_rate"]["wins"] == 1
    assert payload["hands"]["diamond_hands"]["bets"] == 1


@finance_test
def test_bet_slur_trader_refused():
    tmp = _tmpdir()
    code, out = _run_finance(
        tmp,
        "bet",
        sym="SYNTH",
        qty=1,
        side="buy",
        source="synth",
        trader="retard_ape",
        yes=True,
    )
    assert code == 2, out
    assert "NOT placed" in out


@finance_test
def test_bet_paper_hands_settle():
    tmp = _tmpdir()
    _run_finance(
        tmp,
        "bet",
        sym="SYNTH",
        qty=5,
        side="sell",
        source="synth",
        trader="quick",
        yes=True,
    )
    ledger = bets_mod.BetLedger.load(Path(tmp) / "bets.json")
    bet_id = ledger.bets[0].id
    code, out = _run_finance(tmp, "settle", bet_id=bet_id, price=1.0, paper_hands=True)
    assert code == 0, out
    assert "🧻 PAPER" in out
    code, out = _run_finance(tmp, "bets")
    assert "paper hands:   1 bets" in out


@finance_test
def test_leaderboard_cli():
    tmp = _tmpdir()
    for _ in range(3):
        _run_finance(
            tmp,
            "bet",
            sym="SYNTH",
            qty=10,
            side="buy",
            source="synth",
            trader="guru",
            yes=True,
        )
    ledger = bets_mod.BetLedger.load(Path(tmp) / "bets.json")
    for bet in ledger.bets:
        _run_finance(tmp, "settle", bet_id=bet.id, price=bet.entry_price * 1.2)
    code, out = _run_finance(tmp, "leaderboard")
    assert code == 0, out
    assert "LEADERBOARD" in out
    assert "guru" in out
    assert "🥇" in out
    code, out = _run_finance(tmp, "leaderboard", json=True)
    assert code == 0, out
    assert json.loads(out)["rows"][0]["trader"] == "guru"


@finance_test
def test_copytrade_cli():
    tmp = _tmpdir()
    for _ in range(3):
        _run_finance(
            tmp,
            "bet",
            sym="SYNTH",
            qty=10,
            side="buy",
            source="synth",
            trader="guru",
            yes=True,
        )
    ledger = bets_mod.BetLedger.load(Path(tmp) / "bets.json")
    for bet in ledger.bets:
        _run_finance(tmp, "settle", bet_id=bet.id, price=bet.entry_price * 1.1)
    code, out = _run_finance(tmp, "copytrade", follow="guru", capital=5000.0)
    assert code == 0, out
    assert "COPY TRADE SIMULATION" in out
    assert "@guru" in out
    assert "fine print" in out
    code, out = _run_finance(tmp, "copytrade", all=True, json=True)
    assert code == 0, out
    payload = json.loads(out)
    assert payload["reports"][0]["follow"] == "guru"
    code, out = _run_finance(tmp, "copytrade", follow="nobody")
    assert code == 2, out
    assert "NOT run" in out


@finance_test
def test_broker_link_cli():
    tmp = _tmpdir()
    code, out = _run_finance(tmp, "broker-link", broker_link_action="status")
    assert code == 0, out
    assert "DRAFT ONLY" in out
    assert "STRUCTURALLY REFUSED" in out
    code, out = _run_finance(
        tmp, "broker-link", broker_link_action="configure", platform="binance"
    )
    assert code == 0, out
    assert "binance" in out
    assert "No keys requested" in out
    code, out = _run_finance(
        tmp,
        "broker-link",
        broker_link_action="draft",
        sym="BTCUSDT",
        qty=0.5,
        side="buy",
        price=67000.0,
    )
    assert code == 0, out
    assert "DRAFT ORDER — NOT SENT" in out
    assert "cannot send this" in out
    # draft without explicit price pulls the reference from market data
    code, out = _run_finance(
        tmp,
        "broker-link",
        broker_link_action="draft",
        sym="SYNTH",
        qty=10,
        side="sell",
        source="synth",
    )
    assert code == 0, out
    assert "reference price $" in out
    code, out = _run_finance(tmp, "broker-link", broker_link_action="status")
    assert "2 pending" in out


@finance_test
def test_broker_link_draft_needs_configure():
    tmp = _tmpdir()  # fresh dir, link never configured
    code, out = _run_finance(
        tmp,
        "broker-link",
        broker_link_action="draft",
        sym="AAPL",
        qty=1,
        side="buy",
        price=150.0,
    )
    assert code == 2, out
    assert "NOT prepared" in out


@finance_test
def test_portfolio_wsb():
    tmp = _tmpdir()
    code, out = _run_finance(tmp, "portfolio", wsb=True)
    assert code == 0, out
    assert "POSITIONS OR BAN" in out
    assert "not financial advice" in out


@finance_test
def test_live_still_refused_and_order_paper():
    code, out = _run_finance(
        _tmpdir(), "order", sym="SYNTH", qty=1, side="buy", yes=True, live=True
    )
    assert code == 2, out
    assert "NOT enabled" in out


def main() -> int:
    failures = 0
    print(f"finance cli wsb tests ({len(_TESTS)} tests)")
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        except Exception:
            failures += 1
            print(f"ERROR {name}:")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
