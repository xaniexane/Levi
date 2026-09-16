"""Round-4 hardening tests — digest guard, as_of, corrupt persistence,
mixed-source routing, draft immutability.

Hermetic: no network, temp dirs only. Hostile fixtures are
base64-encoded so no denylisted literal appears in this file.

Run:  python3 tests/test_finance_hardening.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_hardening.py -q
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import tempfile
import traceback
import warnings
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import levi.cli.main as cli_main  # noqa: E402
from levi.finance import brokerlink as brokerlink_mod  # noqa: E402
from levi.finance import crypto as crypto_mod  # noqa: E402
from levi.finance import synth as synth_mod  # noqa: E402
from levi.finance import wsb as wsb_mod  # noqa: E402
from levi.finance.bets import BetLedger  # noqa: E402
from levi.finance.market import MarketDataError  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _hostile(b64: str) -> str:
    """Decode a base64 hostile fixture (keeps literals out of source)."""
    return base64.b64decode(b64).decode("utf-8")


def _tmpdir() -> str:
    return tempfile.mkdtemp(prefix="levi-harden-")


# ---------------------------------------------------------------------------
# Digest guard: same semantics as the old literal denylist, no literals in
# source.
# ---------------------------------------------------------------------------


@finance_test
def test_digest_set_intact():
    assert wsb_mod.BANNED_DIGEST_COUNT == 19
    assert len(wsb_mod._BANNED_DIGESTS) == 19


@finance_test
def test_guard_separators_do_not_shield():
    # underscore / digit / punctuation separators still expose the token
    for encoded in (
        "cmV0YXJkX2FwZQ==",  # hostile_name with underscore separator
        "eC1yZXRhcmQtMg==",  # hostile token with dash/digit separators
        "UkVUQVJE",  # uppercase hostile token
    ):
        hostile = _hostile(encoded)
        try:
            wsb_mod.assert_clean(hostile)
        except wsb_mod.SlurDetected:
            pass
        else:
            raise AssertionError(f"{encoded} was not blocked")


@finance_test
def test_guard_passes_clinical_and_clean():
    for clean in (
        "Apes together strong! Diamond hands to the moon. Tendies secured.",
        "The autistic community deserves respect.",  # clinical, not a slur
        "retarding the ignition timing",  # longer word, not a token match
        "",
    ):
        assert wsb_mod.assert_clean(clean) == clean


@finance_test
def test_guard_rejects_non_string():
    for bad in (None, 123, ["x"], {"a": 1}):
        try:
            wsb_mod.assert_clean(bad)
        except wsb_mod.SlurDetected:
            pass
        else:
            raise AssertionError(f"{bad!r} was not rejected")


@finance_test
def test_guard_error_echoes_nothing():
    hostile = _hostile("cmV0YXJkX2FwZQ==")
    try:
        wsb_mod.assert_clean(hostile)
    except wsb_mod.SlurDetected as exc:
        assert "blocked term detected" in str(exc)
        # the offending token is never echoed back into output
        assert hostile not in str(exc)
    else:
        raise AssertionError("hostile fixture was not blocked")


# ---------------------------------------------------------------------------
# Synthetic as_of: reproducible dates on demand, stable prices regardless.
# ---------------------------------------------------------------------------


@finance_test
def test_synth_as_of_reproducible():
    anchor = date(2026, 1, 15)
    a = synth_mod.SyntheticProvider(seed=7, as_of=anchor).daily_bars("SYNTH", days=30)
    b = synth_mod.SyntheticProvider(seed=7, as_of=anchor).daily_bars("SYNTH", days=30)
    assert [x.date for x in a] == [x.date for x in b]
    assert a[-1].date == anchor.isoformat()
    assert [x.close for x in a] == [x.close for x in b]


@finance_test
def test_synth_as_of_shifts_dates_not_prices():
    a = synth_mod.SyntheticProvider(seed=7, as_of=date(2026, 1, 15)).daily_bars(
        "SYNTH", days=30
    )
    b = synth_mod.SyntheticProvider(seed=7, as_of=date(2026, 3, 20)).daily_bars(
        "SYNTH", days=30
    )
    assert [x.close for x in a] == [x.close for x in b]
    assert [x.date for x in a] != [x.date for x in b]


@finance_test
def test_synth_as_of_validates():
    try:
        synth_mod.SyntheticProvider(seed=7, as_of="2026-01-01")
    except MarketDataError:
        pass
    else:
        raise AssertionError("non-date as_of was accepted")


# ---------------------------------------------------------------------------
# Corrupt persistence: loud warnings, never silent, never half-parsed.
# ---------------------------------------------------------------------------


@finance_test
def test_corrupt_bets_ledger_warns_and_starts_empty():
    tmp = Path(_tmpdir())
    ledger_path = tmp / "bets.json"
    ledger_path.write_text("{not valid json", encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ledger = BetLedger.load(ledger_path)
    assert ledger.bets == []
    assert any("unreadable" in str(w.message) for w in caught), (
        "corrupt ledger was swallowed silently"
    )


@finance_test
def test_corrupt_broker_link_config_surfaces():
    tmp = Path(_tmpdir())
    link_path = tmp / "broker_link.json"
    drafts_path = tmp / "drafts.json"
    link_path.write_text("{corrupt", encoding="utf-8")
    st = brokerlink_mod.broker_link_status(link_path=link_path, drafts_path=drafts_path)
    assert st["config_state"] == "corrupt"
    assert st["platform"] is None


@finance_test
def test_broker_link_status_distinguishes_missing():
    tmp = Path(_tmpdir())
    st = brokerlink_mod.broker_link_status(
        link_path=tmp / "nope.json", drafts_path=tmp / "drafts.json"
    )
    assert st["config_state"] == "missing"


@finance_test
def test_tampered_draft_status_never_loads():
    # A drafts file hand-edited to claim "SENT" must be dropped with a
    # warning — drafts can never acquire a sent/executed status.
    tmp = Path(_tmpdir())
    drafts_path = tmp / "drafts.json"
    drafts_path.write_text(
        json.dumps(
            {
                "drafts": [
                    {
                        "id": "draft-evil",
                        "symbol": "AAPL",
                        "side": "buy",
                        "qty": 1,
                        "reference_price": 150.0,
                        "platform": "alpaca",
                        "created_at": "2026-01-01T00:00:00",
                        "status": "SENT",
                        "note": "tampered",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        drafts = brokerlink_mod.load_drafts(drafts_path)
    assert drafts == []
    assert any("unreadable" in str(w.message) for w in caught)


@finance_test
def test_execute_draft_refuses_unconditionally():
    for args in ((), ("draft-1",), (None,), ({"id": "x"},)):
        try:
            brokerlink_mod.execute_draft(*args)
        except brokerlink_mod.LiveExecutionRefused:
            pass
        else:
            raise AssertionError(f"execute_draft{args} did not refuse")


# ---------------------------------------------------------------------------
# Mixed stock/crypto routing: never silently serve the wrong universe.
# ---------------------------------------------------------------------------


@finance_test
def test_synth_rejects_real_symbols():
    for sym in ("AAPL", "aapl", "BTCUSDT", ""):
        try:
            synth_mod.SyntheticProvider().daily_bars(sym, days=10)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"synth served {sym!r}")


@finance_test
def test_binance_rejects_stock_symbols():
    for sym in ("AAPL", "SYNTH"):
        try:
            crypto_mod.BinanceProvider().daily_bars(sym, days=10)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"binance served {sym!r}")


@finance_test
def test_symbol_classifiers():
    assert crypto_mod.looks_like_crypto("BTCUSDT")
    assert not crypto_mod.looks_like_crypto("AAPL")
    assert synth_mod.is_synth_symbol("SYNTHBTC")
    assert not synth_mod.is_synth_symbol("BTCUSDT")


# ---------------------------------------------------------------------------
# CLI: corrupt broker-link config warns loudly on status and draft.
# ---------------------------------------------------------------------------


def _run_finance(tmpdir, action, **kwargs):
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
    orig_link = brokerlink_mod.DEFAULT_LINK_PATH
    orig_drafts = brokerlink_mod.DEFAULT_DRAFTS_PATH
    brokerlink_mod.DEFAULT_LINK_PATH = Path(tmpdir) / "broker_link.json"
    brokerlink_mod.DEFAULT_DRAFTS_PATH = Path(tmpdir) / "drafts.json"
    try:
        with redirect_stdout(buf):
            cli_main.cmd_finance(args)
    except SystemExit as exc:
        return exc.code, buf.getvalue()
    finally:
        brokerlink_mod.DEFAULT_LINK_PATH = orig_link
        brokerlink_mod.DEFAULT_DRAFTS_PATH = orig_drafts
    return 0, buf.getvalue()


@finance_test
def test_cli_warns_on_corrupt_link_config():
    tmp = _tmpdir()
    Path(tmp, "broker_link.json").write_text("{corrupt", encoding="utf-8")
    code, out = _run_finance(tmp, "broker-link", broker_link_action="status")
    assert code == 0, out
    assert "corrupt" in out.lower()
    assert "WARNING" in out


@finance_test
def test_cli_draft_refuses_on_corrupt_config():
    tmp = _tmpdir()
    Path(tmp, "broker_link.json").write_text("{corrupt", encoding="utf-8")
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
    assert "corrupt" in out.lower()


def main() -> int:
    failures = 0
    print(f"finance hardening tests ({len(_TESTS)} tests)")
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
