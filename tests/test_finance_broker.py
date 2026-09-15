"""Tests for the finance brokerage layer (blueprint §1, §1.5).

Hermetic: no network, no credentials on disk. The Alpaca connector's
transport is unwired by design, so the "live" path can only ever return
honest not-wired results here.
"""

import os
import sys

import pytest

from levi.finance.broker import (
    AlpacaConnector,
    Fill,
    InvalidOrder,
    LiveBrokerUnavailable,
    NoReferencePrice,
    Order,
    OrderNotConfirmed,
    PaperBroker,
    get_broker,
    live_enabled,
)


@pytest.fixture()
def paper():
    return PaperBroker()


def _order(**kwargs):
    base = {"symbol": "AAPL", "qty": 10.0, "side": "buy"}
    base.update(kwargs)
    return Order(**base)


@pytest.fixture()
def clean_broker_env(monkeypatch):
    """No live flag, no Alpaca credentials."""
    monkeypatch.delenv("LEVI_BROKER_LIVE", raising=False)
    monkeypatch.delenv("LEVI_ALPACA_KEY", raising=False)
    monkeypatch.delenv("LEVI_ALPACA_SECRET", raising=False)


# -- PaperBroker: HITL gate --------------------------------------------------


def test_unconfirmed_order_raises_order_not_confirmed(paper):
    with pytest.raises(OrderNotConfirmed):
        paper.place_order(_order(), confirm=False, reference_price=100.0)


def test_confirm_defaults_to_false(paper):
    # Calling without the confirm kwarg must also refuse.
    with pytest.raises(OrderNotConfirmed):
        paper.place_order(_order(), reference_price=100.0)


# -- PaperBroker: validation -------------------------------------------------


@pytest.mark.parametrize("qty", [0, -1, -0.5, float("nan"), float("inf")])
def test_invalid_qty_raises_invalid_order(paper, qty):
    with pytest.raises(InvalidOrder):
        Order(symbol="AAPL", qty=qty, side="buy")


def test_invalid_side_raises_invalid_order(paper):
    with pytest.raises(InvalidOrder):
        Order(symbol="AAPL", qty=1, side="hold")


def test_non_market_order_type_rejected():
    with pytest.raises(InvalidOrder):
        Order(symbol="AAPL", qty=1, side="buy", order_type="limit")


# -- PaperBroker: fills ------------------------------------------------------


def test_confirmed_order_fills_simulated(paper):
    fill = paper.place_order(_order(), confirm=True, reference_price=172.50)
    assert isinstance(fill, Fill)
    assert fill.simulated is True
    assert fill.broker == "paper"
    assert fill.fill_price == 172.50
    assert fill.symbol == "AAPL"
    assert fill.qty == 10.0
    assert fill.side == "buy"
    assert "SIMULATED" in str(fill)
    assert "paper" in str(fill)


def test_fill_str_labels_real_as_real():
    fill = Fill(
        symbol="AAPL",
        qty=1.0,
        side="sell",
        order_type="market",
        created_at="2026-09-15T00:00:00+00:00",
        fill_price=100.0,
        filled_at="2026-09-15T00:00:01+00:00",
        simulated=False,
        broker="alpaca",
    )
    assert "SIMULATED" not in str(fill)
    assert "REAL" in str(fill)


def test_missing_reference_price_raises_no_invented_price(paper):
    with pytest.raises(NoReferencePrice) as exc_info:
        paper.place_order(_order(), confirm=True)
    assert "reference_price" in str(exc_info.value)


@pytest.mark.parametrize("price", [0, -5.0, float("nan"), float("inf"), "abc"])
def test_bad_reference_price_raises(paper, price):
    with pytest.raises(NoReferencePrice):
        paper.place_order(_order(), confirm=True, reference_price=price)


# -- Registry contract: AlpacaConnector --------------------------------------


def test_requires_confirmation_is_forced():
    # Forced by the registry's __init_subclass__ because the connector
    # exposes a write capability/operation — no opt-out possible.
    assert AlpacaConnector.requires_confirmation is True
    assert AlpacaConnector().requires_confirmation is True


def test_write_without_confirm_is_rejected(clean_broker_env):
    result = AlpacaConnector().execute(
        "place_order",
        {"symbol": "AAPL", "qty": 1, "side": "buy"},
        confirm=False,
    )
    assert result.ok is False
    assert result.status == "confirmation_required"
    assert result.request_made is False


def test_confirmed_without_credential_names_key(clean_broker_env):
    result = AlpacaConnector().execute(
        "place_order",
        {"symbol": "AAPL", "qty": 1, "side": "buy"},
        confirm=True,
    )
    assert result.ok is False
    assert result.status == "missing_credential"
    assert "LEVI_ALPACA_KEY" in result.message
    assert result.request_made is False


def test_confirmed_with_credential_but_no_transport(monkeypatch):
    monkeypatch.setenv("LEVI_ALPACA_KEY", "test-key")
    monkeypatch.setenv("LEVI_ALPACA_SECRET", "test-secret")
    result = AlpacaConnector().execute(
        "place_order",
        {"symbol": "AAPL", "qty": 1, "side": "buy"},
        confirm=True,
    )
    assert result.ok is False
    assert result.status == "transport_not_wired"
    assert result.request_made is False


def test_key_alone_is_not_enough_for_credential(monkeypatch):
    monkeypatch.setenv("LEVI_ALPACA_KEY", "test-key")
    monkeypatch.delenv("LEVI_ALPACA_SECRET", raising=False)
    result = AlpacaConnector().execute(
        "quote", {"symbol": "AAPL"}, confirm=True
    )
    assert result.ok is False
    assert result.status == "missing_credential"


# -- Live gate + factory -----------------------------------------------------


def test_live_enabled_requires_flag_and_both_credentials(monkeypatch):
    monkeypatch.delenv("LEVI_BROKER_LIVE", raising=False)
    monkeypatch.delenv("LEVI_ALPACA_KEY", raising=False)
    monkeypatch.delenv("LEVI_ALPACA_SECRET", raising=False)
    assert live_enabled() is False

    monkeypatch.setenv("LEVI_BROKER_LIVE", "1")
    assert live_enabled() is False  # keys still missing

    monkeypatch.setenv("LEVI_ALPACA_KEY", "k")
    assert live_enabled() is False  # secret still missing

    monkeypatch.setenv("LEVI_ALPACA_SECRET", "s")
    assert live_enabled() is True


def test_live_flag_must_be_exactly_one(monkeypatch):
    monkeypatch.setenv("LEVI_ALPACA_KEY", "k")
    monkeypatch.setenv("LEVI_ALPACA_SECRET", "s")
    monkeypatch.setenv("LEVI_BROKER_LIVE", "true")
    assert live_enabled() is False
    monkeypatch.setenv("LEVI_BROKER_LIVE", "0")
    assert live_enabled() is False


def test_get_broker_paper_returns_paper_broker():
    result = get_broker("paper")
    assert isinstance(result, PaperBroker)


def test_get_broker_default_is_paper():
    assert isinstance(get_broker(), PaperBroker)


def test_get_broker_alpaca_without_env_raises(clean_broker_env):
    with pytest.raises(LiveBrokerUnavailable) as exc_info:
        get_broker("alpaca")
    message = str(exc_info.value)
    assert "LEVI_BROKER_LIVE" in message
    assert "LEVI_ALPACA_KEY" in message
    assert "LEVI_ALPACA_SECRET" in message


def test_get_broker_alpaca_partial_env_still_raises(monkeypatch):
    monkeypatch.setenv("LEVI_BROKER_LIVE", "1")
    monkeypatch.setenv("LEVI_ALPACA_KEY", "k")
    monkeypatch.delenv("LEVI_ALPACA_SECRET", raising=False)
    with pytest.raises(LiveBrokerUnavailable) as exc_info:
        get_broker("alpaca")
    assert "LEVI_ALPACA_SECRET" in str(exc_info.value)


def test_get_broker_alpaca_with_full_env_returns_connector(monkeypatch):
    monkeypatch.setenv("LEVI_BROKER_LIVE", "1")
    monkeypatch.setenv("LEVI_ALPACA_KEY", "k")
    monkeypatch.setenv("LEVI_ALPACA_SECRET", "s")
    result = get_broker("alpaca")
    assert isinstance(result, AlpacaConnector)


def test_get_broker_unknown_name_raises():
    with pytest.raises(ValueError):
        get_broker("robinhood")


def test_package_init_does_not_import_broker():
    # The kernel import chain stays clean: importing the package alone
    # must not pull in the broker module. Checked in a fresh interpreter
    # because this test process already imports the broker above.
    import subprocess

    root = os.path.join(os.path.dirname(__file__), "..")
    code = (
        "import sys; "
        "sys.path.insert(0, 'core'); "
        "import levi.finance; "
        "assert 'levi.finance.broker' not in sys.modules, "
        "'broker leaked into package import'; "
        "assert not hasattr(levi.finance, 'PaperBroker'); "
        "print('package import clean')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "package import clean" in proc.stdout


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
