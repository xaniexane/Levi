"""Portfolio ledger tests — hand-worked accounting, persistence, guards.

Run:  python3 tests/test_finance_portfolio.py   (has a real __main__ runner)
      python3 -m pytest tests/test_finance_portfolio.py -q
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.portfolio import DEFAULT_PATH, Portfolio, load  # noqa: E402

try:
    import pytest  # noqa: F401

    _HAS_PYTEST = True
except ImportError:  # pragma: no cover
    _HAS_PYTEST = False


# ---------------------------------------------------------------------------
# Hand-worked example (arithmetic spelled out in comments).
#
#   deposit(10000.00)                      -> cash = 10000.00
#   buy  10 AAPL @ 150.00  -> cost 1500.00 -> cash =  8500.00
#                                         -> qty 10, avg 150.00
#   buy  10 AAPL @ 160.00  -> cost 1600.00 -> cash =  6900.00
#    avg = (10*150 + 10*160) / 20 = 3100/20 = 155.00 ; qty 20
#   sell  5 AAPL @ 170.00  -> proceeds 850 -> cash =  7750.00
#    realized = 5 * (170 - 155) = 75.00    ; qty 15
#   market value @180      -> 7750 + 15*180 = 7750 + 2700 = 10450.00
#   unrealized             -> 15 * (180 - 155) = 375.00
#   total pnl              -> 75.00 + 375.00 = 450.00
# ---------------------------------------------------------------------------


def _example_portfolio() -> Portfolio:
    p = Portfolio()
    p.deposit(10000.00)
    p.apply_fill("AAPL", "buy", 10, 150.00)
    p.apply_fill("AAPL", "buy", 10, 160.00)
    p.apply_fill("AAPL", "sell", 5, 170.00)
    return p


def test_buy_sell_accounting():
    p = _example_portfolio()
    pos = p.positions["AAPL"]
    assert p.cash == 7750.00, p.cash
    assert pos.qty == 15, pos.qty
    assert pos.avg_cost == 155.00, pos.avg_cost
    assert pos.realized_pnl == 75.00, pos.realized_pnl

    value, warnings = p.market_value({"AAPL": 180.00})
    assert value == 10450.00, value
    assert warnings == []

    per, total = p.unrealized_pnl({"AAPL": 180.00})
    assert per == {"AAPL": 375.00}, per
    assert total == 375.00, total

    s = p.summary({"AAPL": 180.00})
    assert s["cash"] == 7750.00
    assert s["realized_pnl"] == 75.00
    assert s["unrealized_pnl"] == 375.00
    assert s["total_pnl"] == 450.00
    assert s["market_value"] == 10450.00
    assert s["warnings"] == []
    assert s["positions"]["AAPL"]["unrealized_pnl"] == 375.00
    assert s["positions"]["AAPL"]["realized_pnl"] == 75.00
    assert s["timestamp"]  # present
    json.dumps(s)  # JSON-serializable

    # summary without prices: no valuation keys, still serializable
    s2 = p.summary()
    assert "market_value" not in s2
    assert s2["realized_pnl"] == 75.00
    json.dumps(s2)


def test_oversell_raises_and_mutates_nothing():
    p = _example_portfolio()
    before = (p.cash, p.positions["AAPL"].qty, p.positions["AAPL"].realized_pnl)
    try:
        p.apply_fill("AAPL", "sell", 16, 170.00)
    except ValueError:
        pass
    else:
        raise AssertionError("oversell did not raise ValueError")
    after = (p.cash, p.positions["AAPL"].qty, p.positions["AAPL"].realized_pnl)
    assert before == after, "failed sell must not mutate state"


def test_sell_unknown_symbol_raises():
    p = Portfolio()
    p.deposit(100.0)
    try:
        p.apply_fill("NOPE", "sell", 1, 10.0)
    except ValueError:
        pass
    else:
        raise AssertionError("sell of unknown symbol did not raise ValueError")


def test_invalid_fill_args_raise():
    p = Portfolio()
    p.deposit(1000.0)
    bad = [
        ("AAPL", "hold", 1, 10.0),  # bad side
        ("AAPL", "buy", 0, 10.0),  # zero qty
        ("AAPL", "buy", -1, 10.0),  # negative qty
        ("AAPL", "buy", 1, 0.0),  # zero price
        ("AAPL", "sell", 1, -5.0),  # negative price
    ]
    for args in bad:
        try:
            p.apply_fill(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"apply_fill{args} did not raise ValueError")


def test_deposit_rejects_non_positive():
    p = Portfolio()
    assert p.cash == 0.0  # no fake starting balance
    for amount in (0.0, -1.0, -100.5):
        try:
            p.deposit(amount)
        except ValueError:
            pass
        else:
            raise AssertionError(f"deposit({amount}) did not raise ValueError")
    assert p.cash == 0.0
    p.deposit(250.0)
    assert p.cash == 250.0


def test_save_load_round_trip(tmp_path):
    p = _example_portfolio()
    path = tmp_path / "portfolio.json"
    saved = p.save(path)
    assert saved == path
    assert path.exists()

    q = Portfolio.load(path)
    assert q.cash == p.cash
    assert set(q.positions) == set(p.positions)
    for symbol, pos in p.positions.items():
        got = q.positions[symbol]
        assert got.qty == pos.qty
        assert got.avg_cost == pos.avg_cost
        assert got.realized_pnl == pos.realized_pnl
        assert got.symbol == pos.symbol

    # module-level load alias agrees
    r = load(path)
    assert r.cash == p.cash

    # state still behaves after the round trip
    value, warnings = q.market_value({"AAPL": 180.00})
    assert value == 10450.00 and warnings == []


def test_save_creates_dir_with_0700(tmp_path):
    p = Portfolio()
    p.deposit(10.0)
    path = tmp_path / "nested" / "finance" / "portfolio.json"
    p.save(path)
    assert path.exists()
    mode = os.stat(path.parent).st_mode & 0o777
    assert mode == 0o700, oct(mode)


def test_missing_price_warns_and_uses_avg_cost_not_zero():
    p = Portfolio()
    p.deposit(5000.0)
    p.apply_fill("TSLA", "buy", 5, 200.00)  # cash = 5000 - 1000 = 4000
    value, warnings = p.market_value({})
    assert warnings == ["TSLA"], warnings
    # valued at avg_cost (200), never 0:
    assert value == 4000.00 + 5 * 200.00 == 5000.00, value

    per, total = p.unrealized_pnl({})
    assert per == {"TSLA": 0.00}, per
    assert total == 0.00

    s = p.summary({})
    assert s["warnings"] == ["TSLA"]
    assert s["market_value"] == 5000.00


def test_load_missing_file_returns_empty_portfolio(tmp_path):
    p = Portfolio.load(tmp_path / "does-not-exist.json")
    assert isinstance(p, Portfolio)
    assert p.cash == 0.0
    assert p.positions == {}
    # and the empty portfolio values sensibly
    value, warnings = p.market_value({"AAPL": 1.0})
    assert value == 0.0 and warnings == []


def test_default_path_shape():
    assert DEFAULT_PATH == Path.home() / ".levi" / "finance" / "portfolio.json"


def test_output_rounding_keeps_full_internal_precision():
    p = Portfolio()
    p.deposit(1000.0)
    p.apply_fill("XYZ", "buy", 3, 10.333)  # avg_cost internally 10.333
    pos = p.positions["XYZ"]
    assert pos.avg_cost == 10.333  # full precision kept internally
    s = p.summary({"XYZ": 10.333})
    assert s["positions"]["XYZ"]["avg_cost"] == 10.33  # rounded on output
    assert s["positions"]["XYZ"]["unrealized_pnl"] == 0.00


def test_sell_to_flat_keeps_realized_pnl():
    p = Portfolio()
    p.deposit(1000.0)
    p.apply_fill("AAPL", "buy", 4, 100.0)
    p.apply_fill("AAPL", "sell", 4, 110.0)  # realized = 4*10 = 40
    assert p.positions["AAPL"].qty == 0
    assert p.positions["AAPL"].realized_pnl == 40.0
    assert p.realized_pnl_total() == 40.0
    value, warnings = p.market_value({"AAPL": 999.0})
    assert value == 1040.00, value  # cash 1000-400+440; flat position adds 0


# ---------------------------------------------------------------------------
# Runner (blueprint §1.3: a real, executable runner block — not just asserts)
# ---------------------------------------------------------------------------


def test_load_corrupt_file_warns_and_returns_empty(tmp_path):
    import warnings

    path = tmp_path / "portfolio.json"
    path.write_text("{corrupt", encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        p = Portfolio.load(path)
    assert p.cash == 0.0 and p.positions == {}
    assert any("unreadable" in str(w.message) for w in caught)


def test_load_wrong_shape_warns_and_returns_empty(tmp_path):
    import warnings

    for bad in ('[1,2,3]', '{"cash": "lots"}', '{"cash": 1, "positions": {"A": "x"}}'):
        path = tmp_path / "p.json"
        path.write_text(bad, encoding="utf-8")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            p = Portfolio.load(path)
        assert p.cash == 0.0 and p.positions == {}, bad
        assert any("unreadable" in str(w.message) for w in caught), bad


def test_deposit_rejects_garbage_types():
    p = Portfolio()
    for bad in ("50", None, True, float("nan"), float("inf"), [50]):
        try:
            p.deposit(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"deposit({bad!r}) did not raise ValueError")
    assert p.cash == 0.0


def test_apply_fill_rejects_garbage():
    p = Portfolio()
    p.deposit(1000.0)
    for args in [
        ("", "buy", 1, 10.0),
        (123, "buy", 1, 10.0),
        ("AAPL", "buy", True, 10.0),
        ("AAPL", "buy", 1, float("nan")),
        ("AAPL", "buy", "1", 10.0),
        ("AAPL", "hold", 1, 10.0),
    ]:
        try:
            p.apply_fill(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"apply_fill{args} did not raise ValueError")
    assert p.positions == {}


def test_market_value_rejects_bad_price_map():
    p = Portfolio()
    p.deposit(100.0)
    p.apply_fill("AAPL", "buy", 1, 150.0)
    for bad in (None, [("AAPL", 1.0)], {"AAPL": "high"}, {"AAPL": float("inf")}, {"": 5.0}):
        try:
            p.market_value(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"market_value({bad!r}) did not raise ValueError")


def test_position_direct_construction_validated():
    from levi.finance.portfolio import Position

    for kwargs in [
        {"symbol": "", "qty": 1, "avg_cost": 10.0},
        {"symbol": "A", "qty": -1, "avg_cost": 10.0},
        {"symbol": "A", "qty": 1, "avg_cost": float("inf")},
        {"symbol": "A", "qty": True, "avg_cost": 10.0},
    ]:
        try:
            Position(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Position{kwargs} did not raise ValueError")


def _run_all():
    import inspect

    fns = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    passed = failed = 0
    for name, fn in fns:
        params = inspect.signature(fn).parameters
        kwargs = {}
        if "tmp_path" in params:
            import tempfile

            kwargs["tmp_path"] = Path(tempfile.mkdtemp(prefix="levi_pf_"))
        try:
            fn(**kwargs)
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            passed += 1
            print(f"ok   {name}")
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    if _HAS_PYTEST:
        raise SystemExit(__import__("pytest").main([__file__, "-q"]))
    raise SystemExit(_run_all())
