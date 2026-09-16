"""Broker-link tests — draft-only, execution structurally refused.

Hermetic: config/drafts redirected to temp dirs, no network, no keys.

Run:  python3 tests/test_finance_brokerlink.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_brokerlink.py -q
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.brokerlink import (  # noqa: E402
    SUPPORTED_PLATFORMS,
    BrokerLinkConfig,
    DraftOrder,
    InvalidDraft,
    LiveExecutionRefused,
    configure_broker_link,
    execute_draft,
    load_drafts,
    prepare_drafts,
    broker_link_status,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


@finance_test
def test_platforms_declared_not_connected():
    assert set(SUPPORTED_PLATFORMS) == {"alpaca", "binance", "coinbase"}
    # no transport attributes anywhere on the config
    cfg = BrokerLinkConfig(platform="alpaca")
    assert not hasattr(cfg, "transport")
    assert cfg.mode == "draft-only"


@finance_test
def test_live_mode_rejected():
    try:
        BrokerLinkConfig(platform="alpaca", mode="live")
    except InvalidDraft as exc:
        assert "draft-only" in str(exc)
    else:
        raise AssertionError("live mode was accepted")


@finance_test
def test_unknown_platform_rejected():
    try:
        BrokerLinkConfig(platform="robinhood")
    except InvalidDraft:
        pass
    else:
        raise AssertionError("unknown platform was accepted")


@finance_test
def test_configure_needs_no_credentials():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "link.json"
        cfg = configure_broker_link("binance", path=path)
        assert cfg.platform == "binance"
        data = json.loads(path.read_text())
        assert data["platform"] == "binance"
        assert data["live"] == "STRUCTURALLY REFUSED"
        # nothing secret-shaped was written
        blob = path.read_text()
        assert "key" not in blob.lower() or "monkey" in blob.lower()


@finance_test
def test_prepare_drafts_labeled_not_sent():
    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / "link.json"
        drafts_p = Path(tmp) / "drafts.json"
        cfg = configure_broker_link("alpaca", path=link)
        drafts = prepare_drafts(
            [
                {"symbol": "AAPL", "side": "buy", "qty": 10, "reference_price": 150.0},
                {
                    "symbol": "BTCUSDT",
                    "side": "sell",
                    "qty": 0.5,
                    "reference_price": 67000.0,
                },
            ],
            cfg,
            path=drafts_p,
        )
        assert len(drafts) == 2
        for d in drafts:
            assert d.status == "DRAFT — NOT SENT"
            assert d.id.startswith("draft-")
        rendered = drafts[0].render()
        assert "DRAFT ORDER — NOT SENT" in rendered
        assert "cannot send this" in rendered
        assert "Not financial advice" in rendered
        # persisted and reloadable
        assert len(load_drafts(drafts_p)) == 2


@finance_test
def test_prepare_drafts_validates():
    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / "link.json"
        drafts_p = Path(tmp) / "drafts.json"
        cfg = configure_broker_link("coinbase", path=link)
        bad_lists = [
            [],
            "not a list",
            [{"symbol": "AAPL", "side": "buy", "qty": 1}],  # no price
            [{"symbol": "AAPL", "side": "buy", "qty": 1, "reference_price": -5}],
            [{"symbol": "AAPL", "side": "hold", "qty": 1, "reference_price": 5}],
        ]
        for bad in bad_lists:
            try:
                prepare_drafts(bad, cfg, path=drafts_p)
            except InvalidDraft:
                pass
            else:
                raise AssertionError(f"{bad!r} did not raise")
        # unconfigured platform refuses too
        try:
            prepare_drafts(
                [{"symbol": "AAPL", "side": "buy", "qty": 1, "reference_price": 5}],
                BrokerLinkConfig(platform=None),
                path=drafts_p,
            )
        except InvalidDraft as exc:
            assert "configure" in str(exc)
        else:
            raise AssertionError("unconfigured prepare did not raise")


@finance_test
def test_execute_draft_always_refused():
    for args in ((), ("draft-abc",), ("draft-abc", True)):
        try:
            execute_draft(*args)
        except LiveExecutionRefused as exc:
            assert "REFUSED" in str(exc)
        else:
            raise AssertionError(f"execute_draft{args} did not refuse")


@finance_test
def test_draft_status_immutable():
    try:
        DraftOrder(
            id="draft-x",
            symbol="AAPL",
            side="buy",
            qty=1,
            reference_price=10.0,
            platform="alpaca",
            status="SENT",
        )
    except InvalidDraft as exc:
        assert "never sent" in str(exc)
    else:
        raise AssertionError("SENT status was accepted")


@finance_test
def test_status_report():
    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / "link.json"
        drafts_p = Path(tmp) / "drafts.json"
        st = broker_link_status(link, drafts_p)
        assert st["platform"] is None
        assert st["live_execution"].startswith("STRUCTURALLY REFUSED")
        assert st["credentials_requested"].startswith("none")
        configure_broker_link("binance", path=link)
        st2 = broker_link_status(link, drafts_p)
        assert st2["platform"] == "binance"
        assert st2["drafts_pending"] == 0


@finance_test
def test_load_drafts_corrupt_warns():
    import warnings

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "drafts.json"
        path.write_text("{broken")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert load_drafts(path) == []
        assert any("unreadable" in str(w.message) for w in caught)


def main() -> int:
    failures = 0
    print(f"finance brokerlink tests ({len(_TESTS)} tests)")
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
